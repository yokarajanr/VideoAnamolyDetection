"""
utils/image_utils.py — Image encoding/decoding helpers.
Handles frame conversion between OpenCV, PIL, and base64 for API transport.
"""

import base64
import io
import numpy as np
import cv2
from PIL import Image


def frame_to_base64(frame: np.ndarray, quality: int = 80) -> str:
    """Encode a BGR OpenCV frame to a base64 JPEG string for WebSocket transport."""
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
    _, buffer = cv2.imencode(".jpg", frame, encode_params)
    return base64.b64encode(buffer).decode("utf-8")


def base64_to_frame(b64_string: str) -> np.ndarray:
    """Decode a base64 string back to a BGR OpenCV frame."""
    img_data = base64.b64decode(b64_string)
    np_arr = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(np_arr, cv2.IMREAD_COLOR)


def frame_to_pil(frame: np.ndarray) -> Image.Image:
    """Convert a BGR OpenCV frame to a PIL Image (RGB)."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def frame_to_bytes(frame: np.ndarray, quality: int = 85) -> bytes:
    """Encode frame to JPEG bytes (for VLM APIs that accept bytes)."""
    pil_image = frame_to_pil(frame)
    buf = io.BytesIO()
    pil_image.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def resize_frame(frame: np.ndarray, max_width: int = 1280) -> np.ndarray:
    """Resize frame proportionally if wider than max_width."""
    h, w = frame.shape[:2]
    if w <= max_width:
        return frame
    scale = max_width / w
    new_w = int(w * scale)
    new_h = int(h * scale)
    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)


def thumbnail(frame: np.ndarray, size: tuple = (320, 240)) -> str:
    """Create a small base64 thumbnail of a frame for event records."""
    small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
    return frame_to_base64(small, quality=60)
