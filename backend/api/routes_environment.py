"""
api/routes_environment.py — Environment configuration API endpoints.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

from core.environment_manager import EnvironmentManager, ENVIRONMENT_PROFILES
from memory.models import EnvironmentUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/environment", tags=["Environment"])

_env_manager: Optional[EnvironmentManager] = None


def initialize(env_manager: EnvironmentManager):
    global _env_manager
    _env_manager = env_manager


@router.get("")
async def get_current_environment():
    """Return the current environment profile."""
    return {
        "current": _env_manager.current,
        "profile": _env_manager.get_profile(),
        "context_prompt": _env_manager.get_context_prompt(),
    }


@router.get("/list")
async def list_environments():
    """Return all available environment profiles."""
    return {"environments": _env_manager.get_all_environments()}


@router.post("")
async def set_environment(body: EnvironmentUpdate):
    """Switch to a different environment."""
    success = _env_manager.set_environment(body.environment_key)
    if not success:
        valid = list(ENVIRONMENT_PROFILES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown environment '{body.environment_key}'. Valid: {valid}"
        )
    return {
        "status": "ok",
        "current": _env_manager.current,
        "profile": _env_manager.get_profile(),
    }


@router.get("/{env_key}/profile")
async def get_environment_profile(env_key: str):
    """Return profile for any named environment."""
    if env_key not in ENVIRONMENT_PROFILES:
        raise HTTPException(status_code=404, detail=f"Environment '{env_key}' not found")
    return _env_manager.get_profile(env_key)
