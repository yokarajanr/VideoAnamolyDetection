"""
api/routes_rag.py — RAG query endpoint for natural language surveillance querying.
"""

import logging
from typing import Optional
from fastapi import APIRouter

from memory.rag_engine import RAGEngine
from memory.models import RAGQuery, RAGResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["RAG"])

_rag_engine: Optional[RAGEngine] = None


def initialize(rag_engine: RAGEngine):
    global _rag_engine
    _rag_engine = rag_engine


@router.post("/query", response_model=RAGResponse)
async def query_surveillance_memory(body: RAGQuery):
    """
    Ask a natural language question about surveillance history.
    
    Examples:
    - "What anomalies occurred today?"
    - "How many times was the restricted zone accessed this week?"
    - "Show all critical events in the laboratory"
    - "What was detected before the last fire alert?"
    """
    result = await _rag_engine.query(body)
    return result


@router.get("/summary")
async def daily_summary():
    """Get an AI-generated daily surveillance summary."""
    summary = await _rag_engine.get_daily_summary()
    return {"summary": summary}


@router.get("/presets")
async def get_preset_queries():
    """Return pre-built query presets for the dashboard."""
    return {
        "presets": [
            {"label": "Today's anomalies", "query": "What anomalies occurred today?", "date_filter": "today"},
            {"label": "High-risk events this week", "query": "Show all high-risk and critical events this week", "date_filter": "this week"},
            {"label": "Most critical event", "query": "What was the most critical event detected?"},
            {"label": "Restricted zone violations", "query": "How many restricted zone violations occurred?"},
            {"label": "Weapon detections", "query": "Were any weapons detected? Give details."},
            {"label": "Fire/smoke incidents", "query": "Were there any fire or smoke incidents?"},
            {"label": "Today's summary", "query": "Summarize all surveillance activity today", "date_filter": "today"},
            {"label": "Environment breakdown", "query": "Which environments had the most anomalies?"},
        ]
    }
