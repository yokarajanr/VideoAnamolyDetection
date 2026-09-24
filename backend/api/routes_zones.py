"""
api/routes_zones.py — Zone configuration API endpoints.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

from core.zone_manager import ZoneManager
from memory.models import ZoneConfig

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/zones", tags=["Zones"])

_zone_manager: Optional[ZoneManager] = None


def initialize(zone_manager: ZoneManager):
    global _zone_manager
    _zone_manager = zone_manager


@router.get("")
async def get_zones(source: str = "live"):
    """Return all configured zones."""
    return {"zones": _zone_manager.get_all_zones(source=source)}


@router.post("")
async def create_zone(zone: ZoneConfig):
    """Create or update a zone polygon."""
    if len(zone.points) < 3:
        raise HTTPException(status_code=400, detail="Zone must have at least 3 points.")
    created = await _zone_manager.add_zone(
        zone_id=zone.zone_id,
        name=zone.name,
        zone_type=zone.zone_type,
        points=zone.points,
        color=zone.color,
        source=zone.source,
    )
    return {"status": "ok", "zone": created.to_dict()}


@router.delete("/{zone_id}")
async def delete_zone(zone_id: str):
    """Delete a zone by ID."""
    removed = await _zone_manager.remove_zone(zone_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Zone {zone_id} not found")
    return {"status": "ok", "deleted": zone_id}


@router.delete("")
async def clear_all_zones(source: str = "live"):
    """Remove all zones."""
    zones = _zone_manager.get_all_zones(source=source)
    for z in zones:
        await _zone_manager.remove_zone(z["zone_id"])
    return {"status": "ok", "deleted_count": len(zones)}
