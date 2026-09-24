"""
memory/rag_engine.py — Retrieval-Augmented Generation engine for surveillance querying.

Implements the RAG pipeline:
  1. Embed user's natural language question
  2. Retrieve semantically similar events from ChromaDB
  3. Apply optional date/risk filters
  4. Build a structured context prompt
  5. Send to Groq LLM (llama3-8b) for natural language answer generation
  6. Return answer with cited source events

This allows users to ask questions like:
  - "What anomalies occurred today?"
  - "How many times was the server room accessed this week?"
  - "Show all critical events in the laboratory"
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL
from memory.event_store import EventStore
from memory.models import RAGQuery, RAGResponse

logger = logging.getLogger(__name__)

# ── System prompt for surveillance RAG ───────────────────────────────────────
SYSTEM_PROMPT = """You are an advanced, friendly, and highly intelligent AI surveillance assistant. You have access to a real-time event memory database containing security logs.

Your personality:
- You speak naturally, conversationally, and warmly, just like a helpful human assistant.
- You understand natural language, intent, and nuance. If the user asks a general question or greets you, respond politely and naturally before addressing security concerns.
- You do not sound like a rigid robot. Use natural phrasing, and feel free to use formatting (like bolding) to make your answers easy to read.

Your capabilities:
- Answer questions about past surveillance events using the provided context.
- Summarize events (e.g., today, this week) and identify patterns.
- Count events by type, risk level, or environment.
- Recommend security improvements based on patterns.

Guidelines:
- When answering security questions, rely strictly on the provided surveillance context.
- If the context doesn't contain enough information to answer a specific security question, admit it naturally (e.g., "I checked the logs, but I couldn't find any events matching that description today.")
- Always mention timestamps when referring to specific incidents.
- If the user asks a general conversational question not related to security, feel free to chat with them normally!"""


def _parse_date_filter(date_str: str) -> Optional[tuple[datetime, datetime]]:
    """
    Parse common date strings into (start, end) datetime range.
    Supports: 'today', 'yesterday', 'this week', 'last week', 'this month', 'YYYY-MM-DD'
    """
    now = datetime.now()
    d = date_str.lower().strip()

    if d == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif d == "yesterday":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59)
        return start, end
    elif d in ("this week", "week"):
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif d == "last week":
        start = now - timedelta(days=now.weekday() + 7)
        start = start.replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return start, end
    elif d == "this month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    else:
        # Try parsing YYYY-MM-DD
        try:
            date = datetime.strptime(d, "%Y-%m-%d")
            return (
                date.replace(hour=0, minute=0, second=0),
                date.replace(hour=23, minute=59, second=59),
            )
        except ValueError:
            return None


def _build_chroma_date_filter(start: datetime, end: datetime) -> dict:
    """Build MongoDB Atlas Vector Search filter for date range."""
    return {
        "$and": [
            {"timestamp": {"$gte": start.isoformat()}},
            {"timestamp": {"$lte": end.isoformat()}},
        ]
    }


class RAGEngine:
    """
    Retrieval-Augmented Generation engine for natural language
    surveillance event querying.
    """

    def __init__(self, event_store: EventStore):
        self.store = event_store

        if not GROQ_API_KEY:
            logger.warning("GROQ_API_KEY not set. RAG answers will be limited.")
            self._groq = None
        else:
            self._groq = Groq(api_key=GROQ_API_KEY)
            logger.info(f"RAG engine initialized with Groq model: {GROQ_MODEL}")

    async def query(self, rag_query: RAGQuery) -> RAGResponse:
        """
        Full RAG pipeline: retrieve → contextualize → generate.
        """
        question = rag_query.question
        n_ctx = rag_query.max_context_events

        # ── Step 1: Build optional metadata filter ────────────────────────
        where_filter = None
        
        # Automatically infer date filter from question if not provided
        if not rag_query.date_filter:
            q_lower = question.lower()
            if "today" in q_lower:
                rag_query.date_filter = "today"
            elif "yesterday" in q_lower:
                rag_query.date_filter = "yesterday"
            elif "this week" in q_lower:
                rag_query.date_filter = "this week"
            elif "last week" in q_lower:
                rag_query.date_filter = "last week"
                
        if rag_query.date_filter:
            date_range = _parse_date_filter(rag_query.date_filter)
            if date_range:
                where_filter = _build_chroma_date_filter(*date_range)

        # ── Step 2: Semantic retrieval from ChromaDB ──────────────────────
        similar_events = await self.store.semantic_search(
            query=question,
            n_results=n_ctx,
            match_filter=where_filter,
        )

        if not similar_events:
            # Fallback: get recent events as context
            recent = await self.store.get_recent_events(limit=n_ctx)
            similar_events = [{"document": self._event_to_doc(e), "metadata": e, "similarity_score": 0.0}
                              for e in recent]

        # ── Step 3: Build context string ──────────────────────────────────
        context_parts = []
        for i, ev in enumerate(similar_events, 1):
            doc = ev.get("document", "")
            score = ev.get("similarity_score", 0)
            context_parts.append(f"[Event {i} | Relevance: {score:.2f}]\n{doc}")

        context_text = "\n\n".join(context_parts)
        total_events = await self.store._collection.count_documents({})

        user_prompt = (
            f"Surveillance Memory Context (retrieved {len(similar_events)} of {total_events} total events):\n\n"
            f"{context_text}\n\n"
            f"---\n"
            f"Security Operator Question: {question}\n\n"
            f"Provide a clear, factual answer based on the surveillance event context above."
        )

        # ── Step 4: Generate answer with Groq LLM ─────────────────────────
        if self._groq is None:
            answer = self._fallback_answer(similar_events, question)
        else:
            try:
                response = self._groq.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=1000,
                )
                answer = response.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                # Retry with fewer events if context was too large
                try:
                    truncated_context = "\n\n".join(context_parts[:5])
                    short_prompt = (
                        f"Surveillance Context (top 5 events):\n\n{truncated_context}\n\n"
                        f"---\nQuestion: {question}\nProvide a clear answer."
                    )
                    response = self._groq.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": short_prompt},
                        ],
                        temperature=0.2,
                        max_tokens=800,
                    )
                    answer = response.choices[0].message.content
                except Exception as e2:
                    logger.error(f"Groq retry also failed: {e2}")
                    answer = self._fallback_answer(similar_events, question)

        # ── Step 5: Build response ────────────────────────────────────────
        source_events = [ev.get("metadata", {}) for ev in similar_events]

        return RAGResponse(
            question=question,
            answer=answer,
            source_events=source_events,
            context_used=len(similar_events),
        )

    def _event_to_doc(self, event: dict) -> str:
        """Convert a plain event dict to a document string for context."""
        ts = event.get("timestamp", "Unknown")
        env = event.get("environment", "Unknown")
        et = event.get("event_type", "Unknown")
        risk = event.get("risk_level", "Unknown")
        desc = event.get("description", "")
        return f"[{ts}] {env} | {et} | Risk: {risk} — {desc}"

    def _fallback_answer(self, events: list[dict], question: str) -> str:
        """Simple rule-based fallback when Groq is unavailable."""
        if not events:
            return "No relevant events found in the surveillance memory for your query."

        lines = [f"Found {len(events)} relevant event(s) for: '{question}'\n"]
        for ev in events[:5]:
            doc = ev.get("document", "")
            lines.append(f"• {doc[:200]}...")

        return "\n".join(lines)

    async def get_daily_summary(self) -> str:
        """Generate a daily surveillance summary report."""
        stats = await self.store.get_stats()
        today = datetime.now().strftime("%B %d, %Y")

        summary = f"## Surveillance Summary — {today}\n\n"
        summary += f"**Total Events Today:** {stats['anomalies_today']} anomalies detected\n\n"

        by_risk = stats["by_risk"]
        summary += "**Risk Distribution (All Time):**\n"
        for level in ["Critical", "High", "Medium", "Low"]:
            count = by_risk.get(level, 0)
            summary += f"  - {level}: {count} events\n"

        if stats.get("recent_critical"):
            summary += "\n**Recent Critical Events:**\n"
            for ev in stats["recent_critical"][:3]:
                ts = ev.get("timestamp", "")[:16]
                desc = ev.get("description", "")[:100]
                summary += f"  - [{ts}] {desc}\n"

        return summary
