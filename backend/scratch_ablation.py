"""
Retrospective ablation and throttling analysis from the 825-event log.
Run from f:/anomaly/backend/
"""
import json
from collections import Counter

# YOLO_RISK_MAP from anomaly_engine.py
YOLO_RISK_MAP = {
    "fire": "Critical", "smoke": "Critical", "gun": "Critical",
    "knife": "High", "weapon": "Critical", "person": "Low",
    "scissors": "Low", "abuse": "Low", "arrest": "Low",
    "arson": "Low", "assault": "Low", "burglary": "Low",
    "explosion": "Critical", "fighting": "Low", "roadaccidents": "Low",
    "robbery": "Low", "shooting": "Low", "shoplifting": "Low",
    "stealing": "Low", "vandalism": "Low", "normal": "Low",
    "without helmet": "Low",
}

RISK_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}

with open("f:/anomaly/data/events.json", encoding="utf-8") as f:
    data = json.load(f)

events = data if isinstance(data, list) else data.get("events", [])
print(f"Total events loaded: {len(events)}")

# Count actual final risk distribution
actual_dist = Counter(e.get("risk_level", "Unknown") for e in events)
print("\n=== ACTUAL Risk Distribution (full AnomalyEngine) ===")
for k, v in sorted(actual_dist.items(), key=lambda x: -RISK_ORDER.get(x[0], -1)):
    print(f"  {k}: {v}")

# Simulate YOLO-only risk (no VLM, no zones)
def yolo_only_risk(objects_detected):
    max_risk = "Low"
    for cls in objects_detected:
        r = YOLO_RISK_MAP.get(cls.lower(), "Low")
        if RISK_ORDER.get(r, 0) > RISK_ORDER.get(max_risk, 0):
            max_risk = r
    return max_risk

yolo_only_dist = Counter()
yolo_critical_or_high = 0
actual_critical_or_high = 0

for e in events:
    objs = e.get("objects_detected", [])
    yr = yolo_only_risk(objs)
    yolo_only_dist[yr] += 1
    if yr in ("Critical", "High"):
        yolo_critical_or_high += 1
    if e.get("risk_level", "") in ("Critical", "High"):
        actual_critical_or_high += 1

print("\n=== SIMULATED YOLO-Only Risk Distribution ===")
for k, v in sorted(yolo_only_dist.items(), key=lambda x: -RISK_ORDER.get(x[0], -1)):
    print(f"  {k}: {v}")

print(f"\nYOLO-only High/Critical alerts: {yolo_critical_or_high}")
print(f"AnomalyEngine High/Critical alerts: {actual_critical_or_high}")
reduction = (1 - actual_critical_or_high / yolo_critical_or_high) * 100 if yolo_critical_or_high else 0
print(f"False-alarm reduction from fusion: {reduction:.1f}%")

# --- Throttling estimate ---
# 825 events stored. Each event = 1 VLM call triggered.
# Normal interval = 2.0s, Alert interval = 3.0s
# Estimate unthrottled: if VLM called every frame at ~15fps and 2s skip (YOLO_FRAME_SKIP=2)
# Effective fps for anomaly decisions ~ 7-8 fps
# With no throttle: every frame triggers VLM -> ~7-8 calls/sec
# With throttle: ~1 call per 2-3 seconds -> 0.33-0.5 calls/sec

# Estimate session duration from event timestamps
from datetime import datetime
timestamps = []
for e in events:
    try:
        ts = datetime.fromisoformat(e["timestamp"])
        timestamps.append(ts)
    except:
        pass

if timestamps:
    session_start = min(timestamps)
    session_end = max(timestamps)
    duration_secs = (session_end - session_start).total_seconds()
    duration_mins = duration_secs / 60
    print(f"\n=== Session Duration (from event timestamps) ===")
    print(f"  First event: {session_start}")
    print(f"  Last event:  {session_end}")
    print(f"  Total span:  {duration_secs:.0f}s ({duration_mins:.1f} minutes)")

    # Calls with throttle = 825 (the actual count)
    throttled_calls = len(events)
    # Calls without throttle: assume ~7fps effective, 1 VLM call per frame
    effective_fps = 7
    unthrottled_calls = int(duration_secs * effective_fps)
    reduction_pct = (1 - throttled_calls / unthrottled_calls) * 100
    print(f"\n=== Throttling / API Cost Estimate ===")
    print(f"  Actual VLM calls (throttled):   {throttled_calls}")
    print(f"  Est. calls without throttle (@{effective_fps}fps): {unthrottled_calls}")
    print(f"  API call reduction:             {reduction_pct:.1f}%")
    print(f"  Avg VLM calls per minute (actual): {throttled_calls / duration_mins:.1f}")

# Object class breakdown
print("\n=== Detected Object Classes (all events) ===")
cls_counter = Counter()
for e in events:
    for cls in e.get("objects_detected", []):
        cls_counter[cls.lower()] += 1
for cls, count in cls_counter.most_common():
    print(f"  {cls}: {count}")
