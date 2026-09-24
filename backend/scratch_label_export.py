"""
Task 1: Stratified 100-event CSV export for manual labelling.
Run from: f:/anomaly/backend/
"""
import json, csv, random
from collections import defaultdict

EVENTS_PATH = "f:/anomaly/data/events.json"
OUT_PATH    = "f:/anomaly/data/labelling_sample.csv"

with open(EVENTS_PATH, encoding="utf-8") as f:
    raw = json.load(f)
events = raw if isinstance(raw, list) else raw.get("events", [])
print(f"Loaded {len(events)} events")

# Build stratification keys: (yolo_class, environment)
strata = defaultdict(list)
for e in events:
    objs = e.get("objects_detected", [])
    cls  = objs[0].lower() if objs else "no_detection"
    env  = (e.get("environment") or "Unknown").strip()
    strata[(cls, env)].append(e)

print(f"Unique strata (class × env): {len(strata)}")

# Sample proportionally, aiming for 100 total
target = 100
total  = len(events)
sample = []
random.seed(42)

for key, bucket in sorted(strata.items()):
    n = max(1, round(len(bucket) / total * target))
    sample.extend(random.sample(bucket, min(n, len(bucket))))

# Trim or top-up to exactly 100
random.shuffle(sample)
if len(sample) > target:
    sample = sample[:target]
elif len(sample) < target:
    # fill from remaining events not already sampled
    sampled_ids = {e.get("id","") or e.get("_id","") for e in sample}
    remainder   = [e for e in events
                   if (e.get("id","") or e.get("_id","")) not in sampled_ids]
    need        = target - len(sample)
    sample.extend(random.sample(remainder, min(need, len(remainder))))

print(f"Final sample size: {len(sample)}")

# Write CSV
COLS = [
    "event_id", "timestamp", "environment",
    "yolo_class", "vlm_risk_level", "zone_violations",
    "vlm_description",
    "ground_truth_correct (Y/N)",
    "notes"
]

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=COLS)
    writer.writeheader()
    for e in sample:
        objs  = e.get("objects_detected", [])
        desc  = e.get("description", "")
        # strip embedded newlines so the cell reads cleanly in Excel
        desc_clean = " ".join(desc.split())[:300]
        zones = "; ".join(e.get("zone_violations", []))
        writer.writerow({
            "event_id":          e.get("id") or e.get("_id",""),
            "timestamp":         e.get("timestamp",""),
            "environment":       e.get("environment",""),
            "yolo_class":        ", ".join(objs) if objs else "—",
            "vlm_risk_level":    e.get("risk_level",""),
            "zone_violations":   zones or "—",
            "vlm_description":   desc_clean,
            "ground_truth_correct (Y/N)": "",
            "notes": "",
        })

print(f"CSV written to: {OUT_PATH}")

# Print strata breakdown for the sample
from collections import Counter
cls_dist = Counter(e.get("objects_detected", ["—"])[0].lower()
                   if e.get("objects_detected") else "no_detection"
                   for e in sample)
env_dist = Counter((e.get("environment") or "Unknown") for e in sample)
print("\n--- Class distribution in sample ---")
for k,v in cls_dist.most_common(): print(f"  {k}: {v}")
print("\n--- Environment distribution in sample ---")
for k,v in env_dist.most_common(): print(f"  {k}: {v}")
