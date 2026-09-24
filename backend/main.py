"""
main.py — FastAPI application entry point for the Hybrid YOLO–VLM–RAG
          Real-Time Video Anomaly Detection Surveillance Platform.

Initializes all components on startup and wires them together:
  - YOLO detector
  - VLM analyzer (Gemini Flash)
  - Environment manager
  - Zone manager
  - Event store (ChromaDB)
  - Anomaly engine
  - Trigger engine
  - Voice alert system
  - RAG engine (Groq)

Then mounts all API routes and serves the frontend as static files.
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Import all components ──────────────────────────────────────────────────────
from config import BACKEND_HOST, BACKEND_PORT, DEFAULT_ENVIRONMENT, VLM_COOLDOWN_SECONDS

from core.detector import YOLODetector
from core.vlm_analyzer import VLMAnalyzer
from core.anomaly_engine import AnomalyEngine
from core.trigger_engine import TriggerEngine
from core.environment_manager import EnvironmentManager
from core.zone_manager import ZoneManager
from memory.event_store import EventStore
from memory.rag_engine import RAGEngine
from alerts.voice_alert import VoiceAlertSystem

from api import routes_stream, routes_events, routes_rag, routes_zones, routes_environment

# ── Application state ──────────────────────────────────────────────────────────
_components: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize all pipeline components. Shutdown: cleanup."""
    logger.info("=" * 60)
    logger.info("  Hybrid YOLO–VLM–RAG Surveillance Platform")
    logger.info("  Initializing components...")
    logger.info("=" * 60)

    # Core pipeline
    detector = YOLODetector()
    vlm = VLMAnalyzer()
    env_manager = EnvironmentManager(default_env=DEFAULT_ENVIRONMENT)
    zone_manager = ZoneManager()
    await zone_manager.load_zones()
    trigger_engine = TriggerEngine()

    # Memory layer
    event_store = EventStore()
    anomaly_engine = AnomalyEngine(env_manager)
    rag_engine = RAGEngine(event_store)

    # Alert system
    voice_alert = VoiceAlertSystem()

    # Wire WebSocket pipeline
    routes_stream.initialize_pipeline(
        detector=detector,
        vlm=vlm,
        env_manager=env_manager,
        zone_manager=zone_manager,
        event_store=event_store,
        anomaly_engine=anomaly_engine,
        trigger_engine=trigger_engine,
        voice_alert=voice_alert,
    )

    # Wire REST routes
    routes_events.initialize(event_store)
    routes_rag.initialize(rag_engine)
    routes_zones.initialize(zone_manager)
    routes_environment.initialize(env_manager)

    # Store for health endpoint
    _components.update({
        "detector": detector,
        "vlm": vlm,
        "env_manager": env_manager,
        "event_store": event_store,
        "voice_alert": voice_alert,
    })

    logger.info("✓ All components initialized. Platform ready.")
    logger.info(f"  Dashboard:  http://localhost:{BACKEND_PORT}/")
    logger.info(f"  API Docs:   http://localhost:{BACKEND_PORT}/docs")

    yield  # Application is running

    logger.info("Shutting down surveillance platform...")


# ── Create FastAPI app ─────────────────────────────────────────────────────────
app = FastAPI(
    title="Hybrid YOLO–VLM–RAG Surveillance Platform",
    description=(
        "A research-grade intelligent surveillance system combining "
        "YOLOv8 real-time detection, Gemini VLM scene understanding, "
        "ChromaDB semantic event memory, and Groq-powered RAG querying."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for development (frontend served separately / via Live Server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount API routes ───────────────────────────────────────────────────────────
app.include_router(routes_stream.router)
app.include_router(routes_events.router)
app.include_router(routes_rag.router)
app.include_router(routes_zones.router)
app.include_router(routes_environment.router)

# ── Serve frontend as static files ─────────────────────────────────────────────
# Mount at root so relative paths in HTML (style.css, js/api.js) resolve correctly.
# FastAPI explicit routes (/api/*, /ws/*) always take priority over this mount.
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

# ── Health endpoint ────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    """System health check."""
    store = _components.get("event_store")
    return {
        "status": "ok",
        "components": {
            "yolo": "ready",
            "vlm": "ready",
            "event_store": f"{store._collection.count() if store else 0} events",
            "voice_alert": _components.get("voice_alert", {}).is_enabled() if _components.get("voice_alert") else False,
        },
        "version": "1.0.0",
    }


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=False,
        log_level="info",
    )
