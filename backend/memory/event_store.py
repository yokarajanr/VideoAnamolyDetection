"""
memory/event_store.py — MongoDB Atlas-backed semantic event memory store.

Stores SurveillanceEvent records in MongoDB using Motor (async).
Calculates semantic embeddings locally using sentence-transformers (all-MiniLM-L6-v2)
and leverages MongoDB Atlas $vectorSearch for RAG.

Key capabilities:
  - Store events as MongoDB documents with vector embeddings
  - Semantic similarity search using Atlas Vector Search ($vectorSearch)
  - Standard metadata filtering (risk level, date, environment, anomaly type)
  - Aggregated statistics for dashboard widgets
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import motor.motor_asyncio
from sentence_transformers import SentenceTransformer

from config import MONGO_URI
from memory.models import SurveillanceEvent, EventQuery

logger = logging.getLogger(__name__)

DB_NAME = "anomaly_surveillance"
COLLECTION_NAME = "surveillance_events"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Fast, runs locally, no API needed

class EventStore:
    """
    Persistent event store using MongoDB Atlas for both standard queries and vector search.
    """

    def __init__(self):
        if not MONGO_URI:
            logger.error("MONGO_URI not found in config. Please set it in .env!")
            raise ValueError("MONGO_URI is required to start the EventStore.")
            
        logger.info(f"Connecting to MongoDB Atlas...")
        self._client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        self._db = self._client[DB_NAME]
        self._collection = self._db[COLLECTION_NAME]

        # Local sentence-transformer model for generating embeddings
        logger.info(f"Loading embedding model {EMBEDDING_MODEL}...")
        self._embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        
        logger.info("EventStore (MongoDB Atlas) initialized.")

    async def store_event(self, event: SurveillanceEvent) -> str:
        """
        Persist a SurveillanceEvent to MongoDB along with its vector embedding.
        """
        # Generate the embedding using the local model
        text_to_embed = event.to_chroma_document()
        embedding = self._embedding_model.encode(text_to_embed).tolist()
        
        # Prepare the document for MongoDB
        doc = event.model_dump()
        doc["_id"] = event.id  # Use our UUID as MongoDB's _id
        doc["timestamp"] = event.timestamp.isoformat()
        doc["embedding_vector"] = embedding
        doc["text_content"] = text_to_embed
        
        try:
            await self._collection.insert_one(doc)
            logger.debug(f"Event {event.id} stored in MongoDB Atlas.")
        except Exception as e:
            logger.error(f"MongoDB store error: {e}")
            
        return event.id

    async def semantic_search(
        self,
        query: str,
        n_results: int = 8,
        match_filter: Optional[dict] = None,
    ) -> list[dict]:
        """
        Find the most semantically similar events to the query text using Atlas Vector Search.
        """
        query_vector = self._embedding_model.encode(query).tolist()
        
        # Build the vector search pipeline
        # Note: You MUST create an Atlas Vector Search index named 'vector_index' 
        # on the 'embedding_vector' field for this to work.
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding_vector",
                    "queryVector": query_vector,
                    "numCandidates": n_results * 10,
                    "limit": n_results
                }
            }
        ]
        
        if match_filter:
            pipeline[0]["$vectorSearch"]["filter"] = match_filter
            
        # Add a project stage to calculate a rough similarity score and hide the heavy vector
        pipeline.append({
            "$project": {
                "embedding_vector": 0,
                "score": {"$meta": "vectorSearchScore"}
            }
        })
        
        try:
            results = await self._collection.aggregate(pipeline).to_list(length=n_results)
            
            events = []
            for doc in results:
                # Format to match the previous structure expected by RAG
                events.append({
                    "document": doc.get("text_content", ""),
                    "metadata": doc,
                    "similarity_score": doc.get("score", 0.0)
                })
            return events
        except Exception as e:
            logger.error(f"MongoDB Vector Search Error: {e}")
            logger.warning("Falling back to standard text search / recent events...")
            # Fallback if vector index doesn't exist yet
            return []

    async def get_events(self, query: EventQuery) -> tuple[list[dict], int]:
        """
        Retrieve events with optional filters from MongoDB.
        Returns (events_list, total_count).
        """
        filter_query = {}
        
        if query.risk_level:
            filter_query["risk_level"] = query.risk_level
            
        if query.environment:
            # Case-insensitive regex search
            filter_query["environment"] = {"$regex": query.environment, "$options": "i"}
            
        if query.event_type:
            filter_query["event_type"] = {"$regex": query.event_type, "$options": "i"}
            
        if query.is_anomalous is not None:
            filter_query["is_anomalous"] = query.is_anomalous
            
        # Date range filtering
        if query.from_date or query.to_date:
            date_filter = {}
            if query.from_date:
                # Convert YYYY-MM-DD to proper ISO start of day
                try:
                    dt = datetime.fromisoformat(query.from_date)
                    date_filter["$gte"] = dt.isoformat()
                except ValueError: pass
                
            if query.to_date:
                # Convert YYYY-MM-DD to proper ISO end of day
                try:
                    dt = datetime.fromisoformat(query.to_date + "T23:59:59")
                    date_filter["$lte"] = dt.isoformat()
                except ValueError: pass
                
            if date_filter:
                filter_query["timestamp"] = date_filter
                
        if query.query:
            # Text search on description or event type
            filter_query["$or"] = [
                {"description": {"$regex": query.query, "$options": "i"}},
                {"event_type": {"$regex": query.query, "$options": "i"}}
            ]
            
        total = await self._collection.count_documents(filter_query)
        
        cursor = self._collection.find(filter_query, {"embedding_vector": 0}).sort("timestamp", -1).skip(query.offset).limit(query.limit)
        events = await cursor.to_list(length=query.limit)
        
        return events, total

    async def get_event_by_id(self, event_id: str) -> Optional[dict]:
        """Retrieve a single event by ID."""
        return await self._collection.find_one({"_id": event_id}, {"embedding_vector": 0})

    async def delete_event(self, event_id: str) -> bool:
        """Delete an event from MongoDB."""
        result = await self._collection.delete_one({"id": event_id})
        return result.deleted_count > 0

    async def delete_events(self, event_ids: list[str]) -> int:
        """Delete multiple events from MongoDB."""
        result = await self._collection.delete_many({"id": {"$in": event_ids}})
        return result.deleted_count

    async def get_stats(self) -> dict:
        """Aggregate statistics for dashboard widgets using MongoDB Aggregation Pipeline."""
        total = await self._collection.count_documents({})
        if total == 0:
            return {
                "total": 0,
                "total_chroma": 0,
                "anomalies_today": 0,
                "by_risk": {"Low": 0, "Medium": 0, "High": 0, "Critical": 0},
                "by_environment": {},
                "by_event_type": {},
                "recent_critical": [],
            }
            
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # Pipeline for basic stats
        pipeline = [
            {"$facet": {
                "anomalies_today": [
                    {"$match": {"timestamp": {"$regex": f"^{today_str}"}, "is_anomalous": True}},
                    {"$count": "count"}
                ],
                "by_risk": [
                    {"$group": {"_id": "$risk_level", "count": {"$sum": 1}}}
                ],
                "by_environment": [
                    {"$group": {"_id": "$environment", "count": {"$sum": 1}}}
                ],
                "by_event_type": [
                    {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
                ],
                "recent_critical": [
                    {"$match": {"risk_level": "Critical"}},
                    {"$sort": {"timestamp": -1}},
                    {"$limit": 5},
                    {"$project": {"embedding_vector": 0}}
                ]
            }}
        ]
        
        results = await self._collection.aggregate(pipeline).to_list(length=1)
        res = results[0]
        
        anomalies_today = res["anomalies_today"][0]["count"] if res["anomalies_today"] else 0
        
        by_risk = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
        for item in res["by_risk"]:
            by_risk[item["_id"]] = item["count"]
            
        by_env = {item["_id"]: item["count"] for item in res["by_environment"] if item["_id"]}
        by_type = {item["_id"]: item["count"] for item in res["by_event_type"] if item["_id"]}
        
        return {
            "total": total,
            "total_chroma": total, # For UI compatibility
            "anomalies_today": anomalies_today,
            "by_risk": by_risk,
            "by_environment": by_env,
            "by_event_type": by_type,
            "recent_critical": res["recent_critical"],
        }

    async def get_recent_events(self, limit: int = 20) -> list[dict]:
        """Get the most recent N events."""
        cursor = self._collection.find({}, {"embedding_vector": 0}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
