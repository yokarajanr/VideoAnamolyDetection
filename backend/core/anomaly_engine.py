"""
core/anomaly_engine.py — Multi-source anomaly detection and risk fusion engine.

This is the research core: it fuses signals from:
  1. YOLO object detections
  2. VLM scene reasoning
  3. Zone violations
  4. Environment-specific rules
  5. Historical context

to produce a final, explainable risk assessment for each analyzed frame.

Output: a structured AnomalyReport that gets stored in the event memory.
"""

import logging
from datetime import datetime
from typing import Optional
import uuid

from core.environment_manager import EnvironmentManager

logger = logging.getLogger(__name__)

# ── Risk level ordering ────────────────────────────────────────────────────────
RISK_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}

# ── YOLO classes that immediately elevate risk ─────────────────────────────────
YOLO_RISK_MAP = {
    # Default COCO classes
    "fire": "Critical",
    "smoke": "Critical",
    "gun": "Critical",
    "knife": "High",
    "weapon": "Critical",
    "person": "Low",  # base; elevated by context
    "scissors": "Low",
    
    # UCF-Crime Classes (YOLO Classification) - Set to Low to let VLM verify behaviors
    "abuse": "Low",
    "arrest": "Low",
    "arson": "Low",
    "assault": "Low",
    "burglary": "Low",
    "explosion": "Critical",
    "fighting": "Low",
    "roadaccidents": "Low",
    "robbery": "Low",
    "shooting": "Low",
    "shoplifting": "Low",
    "stealing": "Low",
    "vandalism": "Low",
    "normal": "Low"
}

# ── Objects that suggest abandoned/suspicious items ───────────────────────────
ABANDONED_OBJECT_CLASSES = {"backpack", "suitcase", "handbag", "bag"}


def _max_risk(*risk_levels: str) -> str:
    """Return the highest risk level from a set of risk strings."""
    return max(risk_levels, key=lambda r: RISK_ORDER.get(r, 0))


class AnomalyReport:
    """
    Full anomaly assessment result for a single analyzed frame.
    Represents a potential surveillance event ready for storage.
    """

    def __init__(
        self,
        environment: str,
        yolo_detections: list[dict],
        vlm_analysis: Optional[dict],
        zone_violations: list[dict],
        environment_context: str,
        final_risk: str,
        anomalies: list[str],
        description: str,
        reasoning: str,
        recommended_action: str,
        is_anomalous: bool,
        frame_thumbnail: Optional[str] = None,
    ):
        self.event_id = str(uuid.uuid4())
        self.timestamp = datetime.now()
        self.environment = environment
        self.yolo_detections = yolo_detections
        self.vlm_analysis = vlm_analysis or {}
        self.zone_violations = zone_violations
        self.final_risk = final_risk
        self.anomalies = anomalies
        self.description = description
        self.reasoning = reasoning
        self.recommended_action = recommended_action
        self.is_anomalous = is_anomalous
        self.frame_thumbnail = frame_thumbnail

    def to_event_dict(self) -> dict:
        """Convert to the standard SurveillanceEvent dict for storage."""
        detected_objects = list({d["class"] for d in self.yolo_detections})
        zone_names = list({v["zone_name"] for v in self.zone_violations})

        return {
            "id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "environment": self.environment,
            "event_type": self.anomalies[0] if self.anomalies else "Normal Activity",
            "risk_level": self.final_risk,
            "objects_detected": detected_objects,
            "description": self.description,
            "reasoning": self.reasoning,
            "recommended_action": self.recommended_action,
            "frame_snapshot": self.frame_thumbnail or "",
            "zone_violations": zone_names,
            "is_anomalous": self.is_anomalous,
            "yolo_detections_count": len(self.yolo_detections),
            "vlm_environment_inference": self.vlm_analysis.get("environment_type", "") if self.vlm_analysis else "",
        }


class AnomalyEngine:
    """
    Hybrid multi-source anomaly detection and risk assessment engine.
    
    Fuses YOLO + VLM + Zone + Environment signals into a final risk verdict.
    This is the primary research contribution of the architecture.
    """

    def __init__(self, environment_manager: EnvironmentManager):
        self.env_manager = environment_manager

    def assess(
        self,
        yolo_detections: list[dict],
        vlm_analysis: Optional[dict],
        zone_violations: list[dict],
        frame_thumbnail: Optional[str] = None,
    ) -> AnomalyReport:
        """
        Main fusion method. Combines all signals into a final AnomalyReport.
        
        Signal hierarchy (highest priority wins):
        1. Critical YOLO classes (fire, gun) → always Critical
        2. Zone violations → elevate to at least High
        3. VLM risk assessment → trusted reasoning
        4. Environment-specific anomaly rules
        5. YOLO-based heuristics
        """
        profile = self.env_manager.get_profile()
        env_name = profile["display_name"]
        env_context = self.env_manager.get_context_prompt()
        anomalies_found: list[str] = []
        risk_signals: list[str] = []

        # ── Signal 1: VLM (The Primary Brain) ────────────────────────────────
        vlm_risk = "Low"
        vlm_description = "No VLM analysis available."
        vlm_reasoning = ""
        vlm_action = "Continue monitoring."
        vlm_confidence = 0

        if vlm_analysis and vlm_analysis.get("risk_level"):
            vlm_risk = vlm_analysis.get("risk_level", "Low")
            # Compile the full VLM analysis report for the description
            vlm_description = (
                f"Scene Description: {vlm_analysis.get('scene_description', '')}\n"
                f"Behavioral Analysis: {vlm_analysis.get('behavioral_analysis', 'N/A')}\n"
                f"Detected Activities: {', '.join(vlm_analysis.get('detected_activities', []))}\n"
                f"Objects of Interest: {', '.join(vlm_analysis.get('objects_of_interest', []))}\n"
                f"Anomalies Found: {', '.join(vlm_analysis.get('anomalies_found', []))}"
            )
            
            vlm_reasoning = vlm_analysis.get("risk_reasoning", "")
            vlm_action = vlm_analysis.get("recommended_action", "")
            vlm_confidence = vlm_analysis.get("confidence_score", 0)

            for anomaly in vlm_analysis.get("anomalies_found", []):
                if anomaly and anomaly not in anomalies_found:
                    anomalies_found.append(anomaly)

            # Only trust the VLM's risk level if it is highly confident to prevent premature false alarms
            if vlm_risk != "Low" and vlm_confidence >= 80:
                risk_signals.append(vlm_risk)
                
        # ── Signal 2: Critical YOLO classes (Hard Overrides) ───────────────
        for det in yolo_detections:
            cls = det["class"]
            # Override for absolute threats even if VLM missed it
            class_risk = YOLO_RISK_MAP.get(cls, "Low")
            if RISK_ORDER.get(class_risk, 0) > RISK_ORDER.get("Low", 0):
                risk_signals.append(class_risk)
                anomalies_found.append(f"{cls.capitalize()} Detected")

        # ── Signal 3: Zone violations ────────────────────────────────────────
        if zone_violations:
            risk_signals.append("High")
            for violation in zone_violations:
                anomalies_found.append(
                    f"Restricted Zone Violation: {violation['zone_name']}"
                    f" ({violation['detected_class']} detected)"
                )

        # ── Final risk fusion ────────────────────────────────────────────────
        final_risk = _max_risk(*risk_signals) if risk_signals else "Low"
        is_anomalous = bool(anomalies_found) or final_risk in ("High", "Critical")

        # ── Build description and reasoning ───────────────────────────────────
        if vlm_description and vlm_description != "No VLM analysis available.":
            description = vlm_description
        else:
            detected_classes = {d["class"] for d in yolo_detections}
            cls_summary = ", ".join(detected_classes) if detected_classes else "no objects"
            description = f"Detected: {cls_summary}. Environment: {env_name}."

        reasoning_parts = []
        if vlm_reasoning:
            reasoning_parts.append(f"VLM (Conf {vlm_confidence}%): {vlm_reasoning}")
        if zone_violations:
            reasoning_parts.append(
                f"Zone violations: {', '.join(v['zone_name'] for v in zone_violations)}"
            )
        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Normal activity detected."

        recommended_action = vlm_action if vlm_action else self._default_action(final_risk)

        return AnomalyReport(
            environment=env_name,
            yolo_detections=yolo_detections,
            vlm_analysis=vlm_analysis,
            zone_violations=zone_violations,
            environment_context=env_context,
            final_risk=final_risk,
            anomalies=anomalies_found,
            description=description,
            reasoning=reasoning,
            recommended_action=recommended_action,
            is_anomalous=is_anomalous,
            frame_thumbnail=frame_thumbnail,
        )

    def _default_action(self, risk: str) -> str:
        actions = {
            "Low": "Continue monitoring.",
            "Medium": "Review event and monitor closely.",
            "High": "Alert security personnel immediately.",
            "Critical": "Emergency response required. Contact authorities.",
        }
        return actions.get(risk, "Continue monitoring.")
