"""
core/detector.py — Dual YOLO detection engine.

Runs two YOLO models simultaneously on every frame:
  1. Scene Classifier (UCF-Crime): Classifies the whole scene (e.g. "fighting", "robbery")
  2. Weapon Detector (Object Detection): Draws bounding boxes around weapons (knife, gun, etc.)

Results from both models are merged into a single unified detection list that is
passed downstream to the anomaly engine and VLM trigger system.
"""

import logging
from pathlib import Path
from typing import Optional
import cv2
import numpy as np
from ultralytics import YOLO

from config import (
    YOLO_MODEL, YOLO_CONFIDENCE, MODELS_DIR,
    WEAPON_MODEL, WEAPON_CONFIDENCE, WEAPON_MODEL_ENABLED,
)

logger = logging.getLogger(__name__)

# ── Risk-weighted classes ──────────────────────────────────────────────
HIGH_PRIORITY_CLASSES = {
    # Weapon detection classes
    "fire", "smoke", "knife", "gun", "weapon", "pistol", "rifle",
    "handgun", "scissors", "blade", "axe", "firearm",
    # Person/object classes
    "person",
    "cell phone",
    "backpack", "suitcase",
    # UCF-Crime scene classes
    "abuse", "arrest", "arson", "assault", "burglary",
    "explosion", "fighting", "roadaccidents", "robbery",
    "shooting", "shoplifting", "stealing", "vandalism",
}

# Bounding box colors per risk class (BGR format)
CLASS_COLORS = {
    "person":   (0, 255, 127),
    "fire":     (0, 0, 255),
    "knife":    (0, 0, 220),
    "gun":      (0, 0, 200),
    "pistol":   (0, 0, 200),
    "rifle":    (0, 0, 200),
    "handgun":  (0, 0, 200),
    "firearm":  (0, 0, 200),
    "blade":    (0, 50, 220),
    "axe":      (0, 50, 220),
    "weapon":   (0, 0, 220),
    "fighting":     (0, 80, 255),
    "shooting":     (0, 0, 255),
    "explosion":    (0, 0, 255),
    "robbery":      (0, 80, 255),
    "assault":      (0, 80, 255),
    "arson":        (0, 0, 255),
    "abuse":        (0, 80, 255),
    "roadaccidents":(0, 165, 255),
    "arrest":       (0, 165, 255),
    "burglary":     (0, 165, 255),
    "shoplifting":  (0, 200, 255),
    "stealing":     (0, 165, 255),
    "vandalism":    (0, 200, 255),
    "default":  (0, 215, 255),
}


def _load_model(model_name: str, label: str) -> Optional[YOLO]:
    """Load a YOLO model from local MODELS_DIR, backend folder, or by name."""
    # Check backend folder directly (where yolo11n.pt lives)
    backend_path = Path(__file__).resolve().parent.parent / model_name
    if backend_path.exists():
        model_source = str(backend_path)
    else:
        local_path = MODELS_DIR / model_name
        model_source = str(local_path) if local_path.exists() else model_name

    logger.info(f"Loading {label} model: {model_source}")
    try:
        model = YOLO(model_source)
        logger.info(f"\u2713 {label} model loaded successfully.")
        return model
    except Exception as e:
        logger.error(f"\u2717 Failed to load {label} model ({model_source}): {e}")
        return None


class DualYOLODetector:
    """
    Dual-model YOLO detector.

    Runs two models in sequence on every frame:
      - Primary  (scene classifier): Classifies the overall scene activity
      - Secondary (weapon detector): Detects weapons with bounding boxes

    Both result sets are merged and returned as a unified list of detections.
    """

    def __init__(
        self,
        primary_model_path: Optional[str] = None,
        weapon_model_path: Optional[str] = None,
        confidence: Optional[float] = None,
        weapon_confidence: Optional[float] = None,
    ):
        self.confidence_threshold = confidence or YOLO_CONFIDENCE
        self.weapon_confidence_threshold = weapon_confidence or WEAPON_CONFIDENCE

        # ── Load primary (scene classification) model ──────────────────
        self.primary_model = _load_model(
            primary_model_path or YOLO_MODEL,
            "Primary (Scene Classifier)"
        )

        # ── Load secondary (weapon detection) model ──────────────────
        self.weapon_model: Optional[YOLO] = None
        if WEAPON_MODEL_ENABLED:
            self.weapon_model = _load_model(
                weapon_model_path or WEAPON_MODEL,
                "Secondary (Weapon Detector)"
            )
            if self.weapon_model is None:
                logger.warning(
                    f"Weapon model not found — running with scene classifier only. "
                    f"Place '{WEAPON_MODEL}' in the backend folder to enable weapon detection."
                )
        else:
            logger.info("Weapon model disabled via WEAPON_MODEL_ENABLED=false in .env")

    # ────────────────────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray) -> list[dict]:
        """
        Run both models on the frame and return a merged detection list.

        Each detection dict has:
          - class (str)
          - confidence (float)
          - bbox [x1, y1, x2, y2]
          - bbox_normalized [cx, cy, w, h]
          - is_high_priority (bool)
          - is_classification (bool) — True for scene-level, False for bbox detections
          - source (str) — "scene" | "weapon"
        """
        detections: list[dict] = []

        if self.primary_model is not None:
            detections.extend(self._run_scene_model(frame))

        if self.weapon_model is not None:
            detections.extend(self._run_weapon_model(frame))

        return detections

    def annotate_frame(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw bounding boxes and labels onto the frame."""
        annotated = frame.copy()
        h_frame, w_frame = annotated.shape[:2]

        bbox_dets = [d for d in detections if not d.get("is_classification")]
        classification_dets = [d for d in detections if d.get("is_classification")]

        # 1. Draw weapon / object bounding boxes
        for det in bbox_dets:
            x1, y1, x2, y2 = det["bbox"]
            cls = det["class"]
            conf = det["confidence"]
            color = CLASS_COLORS.get(cls, CLASS_COLORS["default"])
            label = f"{cls} {conf:.0%}"
            thickness = 3 if cls in (
                "knife", "gun", "pistol", "rifle", "handgun", "firearm", "blade", "axe", "weapon"
            ) else 2
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(annotated, (x1, y1 - lh - 8), (x1 + lw + 4, y1), color, -1)
            cv2.putText(
                annotated, label,
                (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA,
            )

        # 2. Draw scene classification banner (top-right corner)
        banner_y = 10
        for det in classification_dets:
            cls = det["class"]
            conf = det["confidence"]
            color = CLASS_COLORS.get(cls, CLASS_COLORS["default"])
            label = f"{cls.upper()} {conf:.0%}"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
            x_start = w_frame - lw - 22
            cv2.rectangle(annotated, (x_start, banner_y), (w_frame - 10, banner_y + lh + 16), color, -1)
            cv2.putText(
                annotated, label,
                (x_start + 6, banner_y + lh + 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (255, 255, 255), 2, cv2.LINE_AA,
            )
            banner_y += lh + 26

        return annotated

    def get_class_summary(self, detections: list[dict]) -> dict[str, int]:
        """Return a count summary: {'knife': 1, 'fighting': 1, ...}"""
        summary: dict[str, int] = {}
        for det in detections:
            cls = det["class"]
            summary[cls] = summary.get(cls, 0) + 1
        return summary

    def has_high_priority(self, detections: list[dict]) -> bool:
        """Return True if any detection is in the high-priority class set."""
        return any(det["is_high_priority"] for det in detections)

    # ────────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ────────────────────────────────────────────────────────────────────────────

    def _run_scene_model(self, frame: np.ndarray) -> list[dict]:
        """Run the primary scene classification model."""
        h, w = frame.shape[:2]
        detections = []
        try:
            results = self.primary_model(frame, conf=self.confidence_threshold, verbose=False)
            for result in results:
                if hasattr(result, "probs") and result.probs is not None:
                    top1_idx = int(result.probs.top1)
                    cls_name = self.primary_model.names[top1_idx].lower()
                    conf = float(result.probs.top1conf)

                    # ── Overconfidence filter ────────────────────────────────
                    # When a classification model hits 99-100% on an input it has
                    # never seen (e.g., a webcam vs CCTV training data), it is
                    # actually MAXIMALLY CONFUSED, not maximally certain.
                    # Real anomalies in known CCTV footage score 75-95%, not 100%.
                    # We skip outputs that are suspiciously overconfident.
                    if conf >= 0.99:
                        logger.debug(
                            f"[Overconfidence Filter] Skipping '{cls_name}' at {conf:.1%} "
                            f"— model likely confused by unfamiliar input."
                        )
                        continue  # Skip this detection entirely

                    if conf >= self.confidence_threshold:
                        detections.append({
                            "class": cls_name,
                            "confidence": round(conf, 3),
                            "bbox": [0, 0, w, h],
                            "bbox_normalized": [0.5, 0.5, 1.0, 1.0],
                            "is_high_priority": cls_name in HIGH_PRIORITY_CLASSES,
                            "is_classification": True,
                            "source": "scene",
                        })

                elif hasattr(result, "boxes") and result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        cls_name = self.primary_model.names[cls_id].lower()
                        conf = float(box.conf[0])
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                        cx = ((x1 + x2) / 2) / w
                        cy = ((y1 + y2) / 2) / h
                        bw = (x2 - x1) / w
                        bh = (y2 - y1) / h
                        detections.append({
                            "class": cls_name,
                            "confidence": round(conf, 3),
                            "bbox": [x1, y1, x2, y2],
                            "bbox_normalized": [round(cx, 4), round(cy, 4), round(bw, 4), round(bh, 4)],
                            "is_high_priority": cls_name in HIGH_PRIORITY_CLASSES,
                            "is_classification": False,
                            "source": "scene",
                        })
        except Exception as e:
            logger.error(f"Scene model inference error: {e}")
        return detections

    def _run_weapon_model(self, frame: np.ndarray) -> list[dict]:
        """Run the secondary weapon detection model."""
        h, w = frame.shape[:2]
        detections = []
        try:
            results = self.weapon_model(frame, conf=self.weapon_confidence_threshold, verbose=False)
            for result in results:
                if hasattr(result, "boxes") and result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        cls_name = self.weapon_model.names[cls_id].lower()
                        conf = float(box.conf[0])
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                        cx = ((x1 + x2) / 2) / w
                        cy = ((y1 + y2) / 2) / h
                        bw = (x2 - x1) / w
                        bh = (y2 - y1) / h
                        detections.append({
                            "class": cls_name,
                            "confidence": round(conf, 3),
                            "bbox": [x1, y1, x2, y2],
                            "bbox_normalized": [round(cx, 4), round(cy, 4), round(bw, 4), round(bh, 4)],
                            "is_high_priority": cls_name in HIGH_PRIORITY_CLASSES,
                            "is_classification": False,
                            "source": "weapon",
                        })
        except Exception as e:
            logger.error(f"Weapon model inference error: {e}")
        return detections


# ── Backward compatibility alias ───────────────────────────────────────────────
YOLODetector = DualYOLODetector

