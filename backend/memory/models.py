"""
memory/models.py — Pydantic data models for surveillance events.

Defines the canonical SurveillanceEvent schema used throughout the system
for API responses, ChromaDB storage, and RAG retrieval.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class SurveillanceEvent(BaseModel):
    """
    Canonical surveillance event record — the semantic memory unit.
    Stored in ChromaDB as an embedded document with full metadata.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.now)
    environment: str = "Unknown"
    event_type: str = "Normal Activity"
    risk_level: str = "Low"  # Low | Medium | High | Critical
    objects_detected: list[str] = Field(default_factory=list)
    description: str = ""
    reasoning: str = ""
    recommended_action: str = "Continue monitoring."
    frame_snapshot: str = ""  # base64 JPEG thumbnail
    zone_violations: list[str] = Field(default_factory=list)
    is_anomalous: bool = False
    yolo_detections_count: int = 0
    vlm_environment_inference: str = ""

    def to_chroma_document(self) -> str:
        """
        Generate the text document stored and embedded in ChromaDB.
        This text is what semantic search operates over.
        """
        zones_text = (
            f"Zone violations: {', '.join(self.zone_violations)}."
            if self.zone_violations else ""
        )
        objects_text = (
            f"Objects detected: {', '.join(self.objects_detected)}."
            if self.objects_detected else ""
        )
        return (
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Environment: {self.environment}. "
            f"Event: {self.event_type}. "
            f"Risk: {self.risk_level}. "
            f"{self.description} "
            f"{objects_text} "
            f"{zones_text} "
            f"Reasoning: {self.reasoning} "
            f"Action: {self.recommended_action}"
        ).strip()

    def to_chroma_metadata(self) -> dict:
        """Metadata stored alongside the ChromaDB document for filtering."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "date": self.timestamp.strftime("%Y-%m-%d"),
            "environment": self.environment,
            "event_type": self.event_type,
            "risk_level": self.risk_level,
            "is_anomalous": str(self.is_anomalous),
            "has_zone_violations": str(bool(self.zone_violations)),
        }

    def to_summary(self) -> str:
        """Short human-readable summary for RAG context injection."""
        ts = self.timestamp.strftime("%b %d, %Y at %H:%M")
        return (
            f"• [{self.risk_level}] {ts} — {self.event_type} in {self.environment}. "
            f"{self.description[:200]}"
            + ("..." if len(self.description) > 200 else "")
        )


class EventQuery(BaseModel):
    """Parameters for querying the event history."""
    query: Optional[str] = None
    risk_level: Optional[str] = None        # Low | Medium | High | Critical
    environment: Optional[str] = None
    event_type: Optional[str] = None
    from_date: Optional[str] = None         # YYYY-MM-DD
    to_date: Optional[str] = None           # YYYY-MM-DD
    is_anomalous: Optional[bool] = None
    limit: int = 50
    offset: int = 0


class RAGQuery(BaseModel):
    """Natural language question for the RAG engine."""
    question: str
    max_context_events: int = 8
    date_filter: Optional[str] = None       # e.g. "today", "this week", "2026-07-14"


class RAGResponse(BaseModel):
    """Response from the RAG engine."""
    question: str
    answer: str
    source_events: list[dict] = Field(default_factory=list)
    context_used: int = 0


class ZoneConfig(BaseModel):
    """Zone polygon configuration."""
    zone_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    zone_type: str  # "restricted" | "safe"
    source: str = "live"  # "live" | "test"
    points: list[list[float]]   # [[x, y], ...] normalized 0.0–1.0
    color: Optional[str] = None


class EnvironmentUpdate(BaseModel):
    """Request to change the surveillance environment."""
    environment_key: str
    custom_description: Optional[str] = None
