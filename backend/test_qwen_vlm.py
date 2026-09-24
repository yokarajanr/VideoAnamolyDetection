"""
test_qwen_vlm.py — Temporary integration test for the Qwen VLM provider.

Run from the backend/ directory:
    python test_qwen_vlm.py

What this does:
  1. Verifies the Qwen server is reachable at QWEN_BASE_URL before running.
  2. Creates a synthetic 640x480 BGR test frame (no external image file needed).
  3. Encodes it to JPEG bytes (same path as the real pipeline).
  4. Instantiates VLMAnalyzer and calls analyze_frame_async().
  5. Prints the raw JSON result returned by Qwen.

DO NOT modify this file into production code.
Delete after testing is complete.
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# -- Make sure backend/ packages are importable --------------------------------
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# -- Verify .env is loaded before importing anything that reads config ---------
from dotenv import load_dotenv
load_dotenv(BACKEND_DIR.parent / ".env")

import httpx
import cv2
import numpy as np

# -- Import the target module --------------------------------------------------
from core.vlm_analyzer import VLMAnalyzer, QWEN_BASE_URL


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def check_qwen_server() -> bool:
    """Ping the Qwen server root to confirm it's reachable before the test."""
    print(f"\n[1/4] Checking Qwen server at {QWEN_BASE_URL} ...")
    try:
        r = httpx.get(QWEN_BASE_URL, timeout=5.0)
        # Any HTTP response (even 404) means the server is up
        print(f"      OK  Server reachable (HTTP {r.status_code})")
        return True
    except httpx.ConnectError:
        print(f"      FAIL  Could NOT connect to {QWEN_BASE_URL}")
        print("            Make sure your Qwen3-VL server is running.")
        return False
    except Exception as e:
        print(f"      FAIL  Unexpected error reaching server: {e}")
        return False


def make_test_frame_bytes() -> bytes:
    """
    Create a synthetic 640x480 test image (no external file needed).
    Draws a simple office scene so the VLM has something real to describe.
    Returns raw JPEG bytes -- the same format the production pipeline sends.
    """
    print("\n[2/4] Generating synthetic test frame ...")

    # Dark-grey background (simulates an indoor room)
    frame = np.full((480, 640, 3), fill_value=40, dtype=np.uint8)

    # Floor line
    cv2.line(frame, (0, 380), (640, 380), (80, 80, 80), 2)

    # Simple desk (brown rectangle)
    cv2.rectangle(frame, (160, 280), (480, 380), (42, 85, 130), -1)

    # Person silhouette (rough stick figure)
    cv2.circle(frame, (320, 180), 30, (200, 180, 160), -1)              # head
    cv2.rectangle(frame, (300, 210), (340, 290), (100, 120, 180), -1)  # body
    cv2.line(frame, (300, 220), (270, 270), (100, 120, 180), 6)        # left arm
    cv2.line(frame, (340, 220), (370, 270), (100, 120, 180), 6)        # right arm
    cv2.line(frame, (305, 290), (290, 370), (100, 120, 180), 6)        # left leg
    cv2.line(frame, (335, 290), (350, 370), (100, 120, 180), 6)        # right leg

    # Monitor on desk
    cv2.rectangle(frame, (260, 220), (380, 275), (30, 30, 30), -1)
    cv2.rectangle(frame, (265, 225), (375, 270), (50, 80, 120), -1)

    # Label
    cv2.putText(
        frame, "TEST FRAME - Qwen VLM Integration",
        (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA,
    )

    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("cv2.imencode failed -- check OpenCV installation.")

    jpeg_bytes = buf.tobytes()
    print(f"      OK  Frame encoded: {len(jpeg_bytes):,} bytes (640x480 JPEG)")
    return jpeg_bytes


async def run_test():
    # -- Step 1: Reachability check --------------------------------------------
    if not check_qwen_server():
        sys.exit(1)

    # -- Step 2: Synthetic test frame ------------------------------------------
    frame_bytes = make_test_frame_bytes()

    # -- Step 3: Instantiate VLMAnalyzer ---------------------------------------
    print("\n[3/4] Instantiating VLMAnalyzer ...")
    print(f"      VLM_PROVIDER  = {os.getenv('VLM_PROVIDER', 'NOT SET')}")
    print(f"      QWEN_BASE_URL = {QWEN_BASE_URL}")
    vlm = VLMAnalyzer()

    # -- Step 4: Call analyze_frame_async() ------------------------------------
    environment_context = (
        "Environment: office\n"
        "Expected activities: desk work, computer use, meetings\n"
        "This is a standard office environment during business hours."
    )
    detections_summary = (
        "  - 1x person\n"
        "  WARNING HIGH PRIORITY CLASSES: person"
    )

    print("\n[4/4] Calling VLMAnalyzer.analyze_frame_async() ...")
    print(f"      Endpoint: POST {QWEN_BASE_URL}/v1/chat/completions")
    print("      (timeout: 60s -- Qwen can be slow on first inference)\n")
    print("-" * 60)

    result = await vlm.analyze_frame_async(
        frame_bytes=frame_bytes,
        environment_context=environment_context,
        detections_summary=detections_summary,
    )

    # -- Print result ----------------------------------------------------------
    print("\n=== RESULT FROM QWEN VLM ===\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # -- Quick sanity checks ---------------------------------------------------
    print("\n" + "-" * 60)
    print("SANITY CHECKS:")
    expected_keys = [
        "scene_description",
        "environment_type",
        "detected_activities",
        "objects_of_interest",
        "anomalies_found",
        "is_anomalous",
        "risk_level",
        "risk_reasoning",
        "recommended_action",
        "zone_violations_noted",
    ]
    all_ok = True
    for key in expected_keys:
        present = key in result
        status = "OK " if present else "MISSING"
        if not present:
            all_ok = False
        print(f"  [{status}]  {key}")

    print()
    if all_ok:
        print("SUCCESS  All expected keys present. Qwen integration is working correctly.")
    else:
        print("WARNING  Some keys missing -- check _parse_vlm_response() and the Qwen prompt.")


if __name__ == "__main__":
    asyncio.run(run_test())
