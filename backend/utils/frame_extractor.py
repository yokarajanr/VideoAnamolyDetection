"""
utils/frame_extractor.py — Video frame sampling utilities.
Handles reading from webcam, IP camera RTSP, or video files.
"""

import cv2
import logging
from typing import Generator, Optional
import numpy as np

logger = logging.getLogger(__name__)


def open_capture(source: str) -> cv2.VideoCapture:
    """Open a video capture from webcam index (e.g. '0') or RTSP URL."""
    try:
        src = int(source)
    except ValueError:
        src = source  # RTSP URL string

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video source: {source}")

    # Optimize buffer for low latency
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def frame_generator(
    source: str,
    frame_skip: int = 1,
    max_width: int = 1280,
) -> Generator[np.ndarray, None, None]:
    """
    Generator that yields processed frames from a video source.
    
    Args:
        source: Camera index string ('0') or RTSP URL
        frame_skip: Yield every Nth frame (e.g. 2 = every other frame)
        max_width: Resize frames wider than this value
    """
    cap = open_capture(source)
    frame_idx = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Frame read failed — attempting reconnect...")
                cap.release()
                import time; time.sleep(1.0)
                cap = open_capture(source)
                continue

            frame_idx += 1
            if frame_idx % frame_skip != 0:
                continue

            # Resize for performance
            h, w = frame.shape[:2]
            if w > max_width:
                scale = max_width / w
                frame = cv2.resize(
                    frame,
                    (int(w * scale), int(h * scale)),
                    interpolation=cv2.INTER_AREA,
                )

            yield frame
    finally:
        cap.release()


def get_camera_info(source: str) -> dict:
    """Return metadata about the camera/video source."""
    cap = open_capture(source)
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "source": source,
    }
    cap.release()
    return info
