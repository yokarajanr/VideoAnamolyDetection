from typing import Optional

"""
alerts/voice_alert.py — Voice alert system for high/critical risk events.

Uses pyttsx3 for fully offline Text-to-Speech.
Alerts are:
  - Only triggered for High and Critical risk levels
  - Queued to prevent overlapping speech
  - Templated per event type for natural-sounding alerts

Thread-safe queue-based design runs TTS in a background thread
so it never blocks the main detection pipeline.
"""

import logging
import queue
import threading
from datetime import datetime

from config import VOICE_ENABLED, TTS_PROVIDER

logger = logging.getLogger(__name__)

# ── Alert templates ────────────────────────────────────────────────────────────
HIGH_RISK_TEMPLATES: dict[str, str] = {
    "unauthorized": "Warning. Unauthorized entry detected in {zone}.",
    "zone_violation": "Alert. Zone violation detected. A {object} entered the {zone} area.",
    "weapon": "Warning. A potential weapon has been detected. Please verify immediately.",
    "crowd": "Alert. Crowd formation detected in the {environment} area.",
    "loitering": "Alert. Suspicious loitering detected near {zone}.",
    "ppe": "Safety alert. Missing personal protective equipment detected.",
    "default": "Warning. A high-risk event has been detected. Please review the surveillance feed.",
}

CRITICAL_RISK_TEMPLATES: dict[str, str] = {
    "fire": "Emergency. Fire or smoke detected. Please evacuate immediately and contact emergency services.",
    "weapon_gun": "Emergency. A firearm has been detected. Security personnel required immediately.",
    "medical": "Emergency. A person may be injured or unconscious. Medical assistance required immediately.",
    "chemical": "Emergency. Possible chemical hazard detected. Evacuate the area immediately.",
    "default": "Emergency. A critical security event has been detected. Immediate action required.",
}


def _select_template(risk_level: str, event_type: str, context: dict) -> str:
    """Select and format the best matching voice alert template."""
    
    # If we have a detailed VLM description, use it for a personalized alert
    vlm_desc = context.get("vlm_description", "").strip()
    if vlm_desc:
        # Just grab the first sentence to keep the voice alert concise
        first_sentence = vlm_desc.split('.')[0] + "."
        prefix = "Emergency." if risk_level == "Critical" else "Warning."
        return f"{prefix} {first_sentence}"

    et_lower = event_type.lower()
    templates = CRITICAL_RISK_TEMPLATES if risk_level == "Critical" else HIGH_RISK_TEMPLATES

    # Match event type to template key
    template_text = None
    if "fire" in et_lower or "smoke" in et_lower:
        template_text = templates.get("fire") or templates["default"]
    elif "weapon" in et_lower or "gun" in et_lower:
        template_text = templates.get("weapon_gun") or templates.get("weapon") or templates["default"]
    elif "unauthorized" in et_lower or "entry" in et_lower:
        template_text = templates.get("unauthorized", templates["default"])
    elif "zone" in et_lower or "violation" in et_lower:
        template_text = templates.get("zone_violation", templates["default"])
    elif "crowd" in et_lower:
        template_text = templates.get("crowd", templates["default"])
    elif "ppe" in et_lower or "helmet" in et_lower or "protective" in et_lower:
        template_text = templates.get("ppe", templates["default"])
    elif "medical" in et_lower or "fallen" in et_lower or "injur" in et_lower:
        template_text = templates.get("medical", templates["default"])
    else:
        template_text = templates["default"]

    # Fill template placeholders
    zone = context.get("zone", "the restricted area")
    environment = context.get("environment", "the monitored area")
    obj = context.get("object", "person")

    return template_text.format(zone=zone, environment=environment, object=obj)


class VoiceAlertSystem:
    """
    Queue-based voice alert system.
    Runs TTS in a background daemon thread.
    Only High and Critical risk events are announced.
    """

    def __init__(self):
        self._enabled = VOICE_ENABLED
        self._queue: queue.Queue = queue.Queue()
        self._engine = None
        self._last_alert_texts: list[str] = []
        self._thread: threading.Thread | None = None

        if self._enabled:
            self._init_engine()
            self._start_worker()

    def _init_engine(self):
        """Initialize the TTS engine."""
        if TTS_PROVIDER == "pyttsx3":
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", 165)   # Speaking speed (wpm)
                self._engine.setProperty("volume", 0.9)

                # Prefer a female voice if available
                voices = self._engine.getProperty("voices")
                if voices and len(voices) > 1:
                    self._engine.setProperty("voice", voices[1].id)

                logger.info("pyttsx3 TTS engine initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize pyttsx3: {e}")
                self._enabled = False

    def _start_worker(self):
        """Start the background TTS worker thread."""
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self):
        """Background thread that speaks alerts from the queue."""
        while True:
            try:
                text = self._queue.get(timeout=1.0)
                if self._engine:
                    try:
                        self._engine.say(text)
                        self._engine.runAndWait()
                    except Exception as e:
                        logger.error(f"TTS speak error: {e}")
                self._queue.task_done()
            except queue.Empty:
                continue

    def trigger_alert(
        self,
        risk_level: str,
        event_type: str,
        context: Optional[dict] = None,
    ) -> bool:
        """
        Trigger a voice alert for a detected event.
        Only processes High and Critical risk levels.
        
        Returns True if alert was queued, False if skipped.
        """
        if not self._enabled:
            return False

        if risk_level not in ("High", "Critical"):
            return False

        ctx = context or {}
        text = _select_template(risk_level, event_type, ctx)

        # Deduplicate: don't repeat same alert within 30 seconds
        now = datetime.now()
        recent_cutoff = 30 # seconds
        
        # Cleanup old alerts
        self._last_alert_texts = [
            (txt, t) for (txt, t) in self._last_alert_texts 
            if (now - t).total_seconds() < recent_cutoff
        ]
        
        for (txt, _) in self._last_alert_texts:
            if text == txt:
                logger.debug(f"Duplicate alert suppressed (cooldown active): {text[:60]}")
                return False

        self._queue.put_nowait(text)
        self._last_alert_texts.append((text, now))

        logger.info(f"Voice alert queued [{risk_level}]: {text[:80]}")
        return True

    def speak_custom(self, text: str):
        """Speak arbitrary text (for system messages)."""
        if self._enabled and self._engine:
            self._queue.put_nowait(text)

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool):
        self._enabled = enabled



