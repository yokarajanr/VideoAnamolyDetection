"""
config.py — Central configuration loader for the surveillance platform.
Reads all settings from .env and exposes them as typed constants.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
GEMINI_API_KEYS: list[str] = [k.strip() for k in os.getenv("GEMINI_API_KEY", "").split(",") if k.strip()]
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# ── Video ─────────────────────────────────────────────────────────────────────
CAMERA_SOURCE: str = os.getenv("CAMERA_SOURCE", "0")

# ── YOLO ──────────────────────────────────────────────────────────────────────
YOLO_MODEL: str = os.getenv("YOLO_MODEL", "ucf_crime_best.pt")
YOLO_CONFIDENCE: float = float(os.getenv("YOLO_CONFIDENCE", "0.40"))
YOLO_FRAME_SKIP: int = int(os.getenv("YOLO_FRAME_SKIP", "2"))

# ── Weapon Detection Model (secondary YOLO) ───────────────────────────────────
WEAPON_MODEL: str = os.getenv("WEAPON_MODEL", "weapon_best.pt")
WEAPON_CONFIDENCE: float = float(os.getenv("WEAPON_CONFIDENCE", "0.45"))
WEAPON_MODEL_ENABLED: bool = os.getenv("WEAPON_MODEL_ENABLED", "true").lower() == "true"

# ── VLM ───────────────────────────────────────────────────────────────────────
VLM_PROVIDER: str = os.getenv("VLM_PROVIDER", "gemini")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_FALLBACK_MODEL: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")
VLM_COOLDOWN_SECONDS: float = float(os.getenv("VLM_COOLDOWN_SECONDS", "3.0"))
OLLAMA_VLM_MODEL: str = os.getenv("OLLAMA_VLM_MODEL", "moondream")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ── LLM (RAG) ─────────────────────────────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-8b-8192")

# ── Voice ─────────────────────────────────────────────────────────────────────
TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "pyttsx3")
VOICE_ENABLED: bool = os.getenv("VOICE_ENABLED", "true").lower() == "true"

# ── Email Alerts ──────────────────────────────────────────────────────────────
EMAIL_ALERTS_ENABLED: bool = os.getenv("EMAIL_ALERTS_ENABLED", "false").lower() == "true"
EMAIL_SENDER: str = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD: str = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT: str = os.getenv("EMAIL_RECIPIENT", "")

# ── Environment ───────────────────────────────────────────────────────────────
DEFAULT_ENVIRONMENT: str = os.getenv("DEFAULT_ENVIRONMENT", "office")

# ── Server ────────────────────────────────────────────────────────────────────
BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

# ── Database ──────────────────────────────────────────────────────────────────
MONGO_URI: str = os.getenv("MONGO_URI", "")

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR: Path = ROOT_DIR / "data"
CHROMA_DIR: Path = DATA_DIR / "chroma_db"
MODELS_DIR: Path = ROOT_DIR / "models"
EVENTS_JSON: Path = DATA_DIR / "events.json"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
