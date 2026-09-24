"""
api/routes_events.py — Event history CRUD and statistics API endpoints.
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from pydantic import BaseModel

class BulkDeleteRequest(BaseModel):
    event_ids: list[str]

from memory.event_store import EventStore
from memory.models import EventQuery

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["Events"])

_event_store: Optional[EventStore] = None


def initialize(event_store: EventStore):
    global _event_store
    _event_store = event_store


@router.get("")
async def get_events(
    query: Optional[str] = Query(None, description="Text search"),
    risk_level: Optional[str] = Query(None, description="Low|Medium|High|Critical"),
    environment: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    is_anomalous: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Retrieve paginated event history with optional filters."""
    eq = EventQuery(
        query=query,
        risk_level=risk_level,
        environment=environment,
        event_type=event_type,
        from_date=from_date,
        to_date=to_date,
        is_anomalous=is_anomalous,
        limit=limit,
        offset=offset,
    )
    events, total = await _event_store.get_events(eq)
    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset,
        "pages": (total + limit - 1) // limit if limit else 1,
    }


@router.get("/stats")
async def get_stats():
    """Return aggregated statistics for dashboard widgets."""
    return await _event_store.get_stats()


@router.get("/recent")
async def get_recent(limit: int = Query(20, ge=1, le=100)):
    """Get the most recent N events."""
    return await _event_store.get_recent_events(limit=limit)


@router.get("/{event_id}")
async def get_event(event_id: str):
    """Get a single event by ID."""
    event = await _event_store.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return event

@router.delete("/{event_id}")
async def delete_event(event_id: str):
    """Delete a single event by ID."""
    success = await _event_store.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return {"status": "success", "message": "Event deleted"}

@router.post("/bulk-delete")
async def bulk_delete_events(req: BulkDeleteRequest):
    """Delete multiple events."""
    deleted_count = await _event_store.delete_events(req.event_ids)
    return {"status": "success", "deleted_count": deleted_count}
