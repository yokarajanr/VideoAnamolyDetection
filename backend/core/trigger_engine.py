"""
core/trigger_engine.py — Smart VLM triggering decision engine.

Determines WHEN to invoke the expensive VLM analysis based on:
  - YOLO detection classes (high-priority triggers)
  - Zone violations (always trigger)
  - Rate limiting / cooldown (prevent API abuse)
  - Change detection (only re-analyze if scene changes significantly)
  - Periodic forced analysis (every N seconds, even if no triggers)

This decouples the fast YOLO loop from the slower VLM call,
allowing real-time performance while still getting deep analysis.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Classes that always trigger VLM analysis immediately
IMMEDIATE_TRIGGER_CLASSES = {
    "fire", "smoke", "gun", "knife", "weapon",
    "abuse", "arrest", "arson", "assault", "burglary", 
    "explosion", "fighting", "roadaccidents", "robbery", 
    "shooting", "shoplifting", "stealing", "vandalism"
}

# Base classes that trigger VLM analysis only if not in cooldown
BASE_SOFT_TRIGGER_CLASSES = {
    "backpack", "suitcase", "handbag",
    "scissors", "cell phone", "normal"
}

# Environments where any living being should trigger the VLM (low traffic)
ISOLATED_ENVIRONMENTS = {
    "home", "farming", "custom"
}

# Living beings that should trigger VLM in isolated environments
LIVING_BEINGS = {
    "person", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"
}

# ── Adaptive Trigger Config ───────────────────────────────────────────────────
NORMAL_INTERVAL_SECONDS = 2.0  # Periodic baseline scan (frequent to catch fast anomalies)
ALERT_INTERVAL_SECONDS = 3.0    # Deep analysis during suspicious activity
ALERT_MODE_DURATION = 30.0      # How long to stay in alert mode after a trigger


class TriggerEngine:
    """
    Decides when to invoke VLM analysis using a smart adaptive interval.
    
    Normal mode: Fires every 30 seconds to conserve API quota.
    Alert mode: If YOLO detects weapons/crimes or a zone violation occurs,
                shifts to firing every 3 seconds for real-time deep analysis.
    """

    def __init__(self):
        self._last_trigger_time: float = 0.0
        self._alert_mode_until: float = 0.0
        self._frame_count: int = 0

    def should_trigger(
        self,
        detections: list[dict],
        zone_violations: list[dict],
        environment: str = "home"
    ) -> tuple[bool, str]:
        """
        Main decision method.
        Returns: (should_trigger: bool, reason: str)
        """
        self._frame_count += 1
        now = time.time()
        
        # Determine if we should be in Alert Mode based on current frame
        detected_classes = {d["class"] for d in detections}
        has_suspicious_yolo = bool(detected_classes & IMMEDIATE_TRIGGER_CLASSES)
        has_zone_violation = bool(zone_violations)
        
        if has_suspicious_yolo or has_zone_violation:
            # Enter or extend alert mode
            self._alert_mode_until = now + ALERT_MODE_DURATION
            
        in_alert_mode = now < self._alert_mode_until
        current_interval = ALERT_INTERVAL_SECONDS if in_alert_mode else NORMAL_INTERVAL_SECONDS
        
        time_since_last = now - self._last_trigger_time
        
        if time_since_last >= current_interval:
            self._last_trigger_time = now
            
            reason = "periodic_baseline"
            if in_alert_mode:
                if has_zone_violation:
                    reason = f"zone_violation:{zone_violations[0]['zone_name']}"
                elif has_suspicious_yolo:
                    reason = f"suspicious_activity:{','.join(detected_classes & IMMEDIATE_TRIGGER_CLASSES)}"
                else:
                    reason = "alert_mode_active"
                    
            return True, reason
            
        return False, ""

    def get_stats(self) -> dict:
        now = time.time()
        in_alert_mode = now < self._alert_mode_until
        return {
            "frame_count": self._frame_count,
            "last_trigger_seconds_ago": round(now - self._last_trigger_time, 1),
            "current_interval": ALERT_INTERVAL_SECONDS if in_alert_mode else NORMAL_INTERVAL_SECONDS,
            "in_alert_mode": in_alert_mode
        }

