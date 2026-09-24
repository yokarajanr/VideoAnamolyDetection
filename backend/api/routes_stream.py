"""
api/routes_stream.py — WebSocket live video stream endpoint.

The main real-time pipeline endpoint:
  1. Frontend sends base64-encoded video frames over WebSocket
  2. Backend:
     a. Decodes frame
     b. Runs YOLO detection
     c. Checks zone violations
     d. Decides whether to invoke VLM (trigger engine)
     e. Runs anomaly engine
     f. Stores significant events in memory
     g. Triggers voice alerts if needed
     h. Sends back annotated frame + analysis results
  3. Frontend renders annotated frame and updates UI

This design allows the frontend webcam to serve as the camera source,
removing any backend camera dependency.
"""

import asyncio
import json
import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect  # type: ignore

from core.detector import YOLODetector
from core.vlm_analyzer import VLMAnalyzer
from core.anomaly_engine import AnomalyEngine
from core.trigger_engine import TriggerEngine
from core.environment_manager import EnvironmentManager
from core.zone_manager import ZoneManager
from memory.event_store import EventStore
from memory.models import SurveillanceEvent
from alerts.voice_alert import VoiceAlertSystem
from utils.image_utils import base64_to_frame, frame_to_base64, thumbnail
from utils.frame_extractor import get_camera_info
from config import YOLO_FRAME_SKIP, DEFAULT_ENVIRONMENT

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Shared singleton instances ─────────────────────────────────────────────────
# These are initialized once and reused across all WebSocket connections
_detector: Optional[YOLODetector] = None
_vlm: Optional[VLMAnalyzer] = None
_env_manager: Optional[EnvironmentManager] = None
_zone_manager: Optional[ZoneManager] = None
_event_store: Optional[EventStore] = None
_anomaly_engine: Optional[AnomalyEngine] = None
_trigger_engine: Optional[TriggerEngine] = None
_voice_alert: Optional[VoiceAlertSystem] = None


def initialize_pipeline(
    detector: YOLODetector,
    vlm: VLMAnalyzer,
    env_manager: EnvironmentManager,
    zone_manager: ZoneManager,
    event_store: EventStore,
    anomaly_engine: AnomalyEngine,
    trigger_engine: TriggerEngine,
    voice_alert: VoiceAlertSystem,
):
    """Called from main.py on startup to inject shared pipeline components."""
    global _detector, _vlm, _env_manager, _zone_manager
    global _event_store, _anomaly_engine, _trigger_engine, _voice_alert

    _detector = detector
    _vlm = vlm
    _env_manager = env_manager
    _zone_manager = zone_manager
    _event_store = event_store
    _anomaly_engine = anomaly_engine
    _trigger_engine = trigger_engine
    _voice_alert = voice_alert


@router.websocket("/ws/stream")
async def video_stream(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time video analysis.
    
    Message protocol:
    - Client → Server: JSON {"type": "frame", "data": "<base64_jpeg>"}
    - Server → Client: JSON {"type": "analysis", "frame": "<base64>", "detections": [...], ...}
    """
    await websocket.accept()
    logger.info(f"WebSocket connected: {websocket.client}")

    frame_count = 0
    latest_vlm_result: Optional[dict] = None
    new_vlm_result: bool = False
    pending_vlm_task: Optional[asyncio.Task] = None

    try:
        while True:
            # Receive frame from frontend
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if msg.get("type") != "frame":
                continue

            frame_count += 1

            # Decode frame
            b64 = msg.get("data", "")
            source = msg.get("source", "live")
            if not b64:
                continue

            frame = base64_to_frame(b64)
            if frame is None:
                continue

            h, w = frame.shape[:2]

            # ── YOLO detection ─────────────────────────────────────────────
            detections = _detector.detect(frame)

            # ── Zone violation check ───────────────────────────────────────
            violations = _zone_manager.check_violations(detections, w, h, source=source)

            # ── VLM trigger decision ───────────────────────────────────────
            should_run_vlm, trigger_reason = _trigger_engine.should_trigger(
                detections, violations, _env_manager.current
            )

            if should_run_vlm and (pending_vlm_task is None or pending_vlm_task.done()):
                # Capture frame bytes for VLM (async, non-blocking)
                from utils.image_utils import frame_to_bytes, resize_frame
                # Compress image aggressively to speed up network transmission to VLM API
                small_frame = resize_frame(frame, max_width=640)
                frame_bytes = frame_to_bytes(small_frame, quality=60)
                env_context = _env_manager.get_context_prompt()
                det_summary = _vlm.format_detections_summary(detections)
                if violations:
                    det_summary += f"\nWarning: Zone violation detected in {violations[0]['zone_name']}!"

                async def run_vlm(fb=frame_bytes, ec=env_context, ds=det_summary):
                    nonlocal latest_vlm_result, new_vlm_result
                    result = await _vlm.analyze_frame_async(fb, ec, ds)
                    latest_vlm_result = result
                    new_vlm_result = True
                    return result

                pending_vlm_task = asyncio.create_task(run_vlm())

            # ── Anomaly assessment ─────────────────────────────────────────
            frame_thumb = thumbnail(frame)
            report = _anomaly_engine.assess(
                yolo_detections=detections,
                vlm_analysis=latest_vlm_result,
                zone_violations=violations,
                frame_thumbnail=frame_thumb,
            )

            # ── Store significant events ───────────────────────────────────
            # Because VLM is now the primary brain, we rely on its assessment.
            # If the AnomalyEngine (driven by VLM) declares an anomaly, we store it.
            if report.is_anomalous or report.final_risk in ("High", "Critical") or violations:
                # Force anomaly if zone violation
                if violations and not report.is_anomalous:
                    report.is_anomalous = True
                    if report.final_risk in ("Low", "Medium"):
                        report.final_risk = "High"
                    if "Zone Violation" not in report.anomalies:
                        report.anomalies.insert(0, "Zone Violation")

                event = SurveillanceEvent(**report.to_event_dict())
                await _event_store.store_event(event)

                # ── Voice alert ────────────────────────────────────────────
                event_type = report.anomalies[0] if report.anomalies else "Anomaly"
                context = {
                    "zone": violations[0]["zone_name"] if violations else "the area",
                    "environment": _env_manager.current,
                    "object": detections[0]["class"] if detections else "person",
                }

                # Use VLM detailed text for TTS if available, else fallback to generic context
                vlm_description = report.description if report.description else ""
                if vlm_description:
                    context["vlm_description"] = vlm_description

                _voice_alert.trigger_alert(report.final_risk, event_type, context)

                # ── Email alert ────────────────────────────────────────────
                if report.final_risk in ("High", "Critical") or violations:
                    from alerts.email_alert import email_alert
                    email_alert.send_alert(
                        risk_level=report.final_risk,
                        event_type=event_type,
                        vlm_description=report.description,
                        recommended_action=report.recommended_action
                    )


            # ── Annotate frame ─────────────────────────────────────────────
            annotated = _detector.annotate_frame(frame, detections)
            annotated = _zone_manager.annotate_zones(annotated, source=source)

            # Add risk overlay — directly reflects the AnomalyEngine's current verdict.
            # Since VLM (the primary brain) holds state between its periodic calls,
            # this will remain stable.
            display_risk = report.final_risk

            risk_colors = {
                "Low": (0, 200, 100),
                "Medium": (0, 180, 255),
                "High": (0, 100, 255),
                "Critical": (0, 0, 255),
            }
            risk_color = risk_colors.get(display_risk, (0, 200, 100))
            import cv2
            cv2.rectangle(annotated, (0, 0), (200, 36), (0, 0, 0), -1)
            cv2.putText(
                annotated,
                f"RISK: {display_risk.upper()}",
                (8, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                risk_color, 2, cv2.LINE_AA,
            )


            # ── Send response ──────────────────────────────────────────────
            response = {
                "type": "analysis",
                "frame": frame_to_base64(annotated),
                "risk_level": report.final_risk,
                "is_anomalous": report.is_anomalous,
                "anomalies": report.anomalies,
                "description": report.description,
                "recommended_action": report.recommended_action,
                "detections": [
                    {"class": d["class"], "confidence": d["confidence"], "bbox": d.get("bbox")}
                    for d in detections
                ],
                "zone_violations": [
                    {"zone": v["zone_name"], "object": v["detected_class"]}
                    for v in violations
                ],
                "environment": _env_manager.current,
                "vlm_active": new_vlm_result,
                "frame_number": frame_count,
                "event_stored": report.is_anomalous,
            }
            new_vlm_result = False
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass
