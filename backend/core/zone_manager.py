"""
core/zone_manager.py — Zone definition and violation detection.

Users draw polygon zones on the camera feed from the web dashboard.
Zones are classified as:
  - "restricted" (red): access should trigger an alert
  - "safe" (green): normal access area

For each frame, checks whether detected persons/objects fall inside
any zone and reports violations.

Now backed by MongoDB Atlas to persist markings across restarts.
"""

import logging
from typing import Optional
import cv2
import numpy as np
import motor.motor_asyncio
from config import MONGO_URI

logger = logging.getLogger(__name__)

DB_NAME = "anomaly_surveillance"
COLLECTION_NAME = "zones"


class Zone:
    """A named polygonal zone on the camera feed."""

    def __init__(
        self,
        zone_id: str,
        name: str,
        zone_type: str,  # "restricted" | "safe"
        points: list[list[float]],  # [[x, y], ...] normalized 0-1 coords
        color: Optional[str] = None,
        source: str = "live",
    ):
        self.zone_id = zone_id
        self.name = name
        self.zone_type = zone_type
        self.source = source
        self.points_normalized = points
        self.color = color or ("#FF3333" if zone_type == "restricted" else "#33FF88")

    def to_pixel_points(self, width: int, height: int) -> np.ndarray:
        """Convert normalized points to pixel coordinates for the given frame size."""
        return np.array(
            [[int(p[0] * width), int(p[1] * height)] for p in self.points_normalized],
            dtype=np.int32,
        )

    def contains_point(self, px: float, py: float, frame_w: int, frame_h: int) -> bool:
        """
        Check if a point (normalized) is inside this zone polygon.
        Uses OpenCV pointPolygonTest.
        """
        pixel_pts = self.to_pixel_points(frame_w, frame_h)
        test_pt = (int(px * frame_w), int(py * frame_h))
        result = cv2.pointPolygonTest(pixel_pts, test_pt, False)
        return result >= 0  # >= 0 means inside or on boundary

    def to_dict(self) -> dict:
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "zone_type": self.zone_type,
            "source": self.source,
            "points": self.points_normalized,
            "color": self.color,
        }


class ZoneManager:
    """
    Manages zone definitions and checks detections for violations.
    """

    def __init__(self):
        self._zones: dict[str, Zone] = {}
        if MONGO_URI:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
            self._db = self._client[DB_NAME]
            self._collection = self._db[COLLECTION_NAME]
        else:
            self._client = None
            logger.warning("MONGO_URI not found. ZoneManager will run entirely in-memory.")

    async def load_zones(self):
        """Load saved zones from MongoDB Atlas on startup."""
        if not self._client:
            return
            
        try:
            cursor = self._collection.find({})
            count = 0
            async for doc in cursor:
                zone = Zone(
                    zone_id=doc.get("zone_id", ""),
                    name=doc.get("name", "Unknown"),
                    zone_type=doc.get("zone_type", "restricted"),
                    points=doc.get("points", []),
                    color=doc.get("color"),
                    source=doc.get("source", "live")
                )
                self._zones[zone.zone_id] = zone
                count += 1
            logger.info(f"Loaded {count} persistent zones from MongoDB.")
        except Exception as e:
            logger.error(f"Failed to load zones from MongoDB: {e}")

    async def add_zone(
        self,
        zone_id: str,
        name: str,
        zone_type: str,
        points: list[list[float]],
        color: Optional[str] = None,
        source: str = "live",
    ) -> Zone:
        """Add or replace a zone and save to MongoDB."""
        zone = Zone(zone_id, name, zone_type, points, color, source)
        self._zones[zone_id] = zone
        
        if self._client:
            try:
                await self._collection.update_one(
                    {"zone_id": zone_id},
                    {"$set": zone.to_dict()},
                    upsert=True
                )
            except Exception as e:
                logger.error(f"Failed to save zone {zone_id} to MongoDB: {e}")
                
        logger.info(f"Zone added: {name} ({zone_type}) for {source} with {len(points)} points")
        return zone

    async def remove_zone(self, zone_id: str) -> bool:
        if zone_id in self._zones:
            del self._zones[zone_id]
            if self._client:
                try:
                    await self._collection.delete_one({"zone_id": zone_id})
                except Exception as e:
                    logger.error(f"Failed to delete zone {zone_id} from MongoDB: {e}")
            return True
        return False

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        return self._zones.get(zone_id)

    def get_all_zones(self, source: Optional[str] = None) -> list[dict]:
        return [z.to_dict() for z in self._zones.values() if source is None or z.source == source]

    def check_violations(
        self,
        detections: list[dict],
        frame_w: int,
        frame_h: int,
        source: str = "live",
    ) -> list[dict]:
        """
        Check each detection against restricted zones.
        Returns a list of violation events.
        """
        violations = []
        restricted_zones = [
            z for z in self._zones.values() 
            if z.zone_type == "restricted" and z.source == source
        ]

        if not restricted_zones:
            return violations

        for det in detections:
            # Use normalized center of bounding box
            cx, cy = det["bbox_normalized"][0], det["bbox_normalized"][1]

            for zone in restricted_zones:
                if zone.contains_point(cx, cy, frame_w, frame_h):
                    violations.append({
                        "zone_id": zone.zone_id,
                        "zone_name": zone.name,
                        "zone_type": zone.zone_type,
                        "detected_class": det["class"],
                        "confidence": det["confidence"],
                        "bbox": det["bbox"],
                    })

        return violations

    def annotate_zones(self, frame: np.ndarray, source: str = "live") -> np.ndarray:
        """
        Draw all zones onto the frame with their respective colors.
        Restricted zones = red overlay, Safe zones = green overlay.
        """
        annotated = frame.copy()
        h, w = frame.shape[:2]

        for zone in self._zones.values():
            if zone.source != source:
                continue
            pts = zone.to_pixel_points(w, h)

            # Parse hex color to BGR
            hex_col = zone.color.lstrip("#")
            r, g, b = tuple(int(hex_col[i:i+2], 16) for i in (0, 2, 4))
            bgr = (b, g, r)
            light_bgr = (min(b + 60, 255), min(g + 60, 255), min(r + 60, 255))

            # Semi-transparent fill
            overlay = annotated.copy()
            cv2.fillPoly(overlay, [pts], bgr)
            cv2.addWeighted(overlay, 0.2, annotated, 0.8, 0, annotated)

            # Border
            cv2.polylines(annotated, [pts], isClosed=True, color=bgr, thickness=2)

            # Zone label
            centroid_x = int(np.mean(pts[:, 0]))
            centroid_y = int(np.mean(pts[:, 1]))
            label = f"{zone.name} [{zone.zone_type.upper()}]"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(
                annotated,
                (centroid_x - lw // 2 - 4, centroid_y - lh - 4),
                (centroid_x + lw // 2 + 4, centroid_y + 4),
                bgr, -1,
            )
            cv2.putText(
                annotated, label,
                (centroid_x - lw // 2, centroid_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA,
            )

        return annotated
