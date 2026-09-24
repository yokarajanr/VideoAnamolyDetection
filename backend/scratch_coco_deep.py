"""Deep trace: where did 'person', 'chair', 'dining table' actually come from?
These are COCO classes. ucf_crime_best.pt is a CLASSIFY model with 14 UCF classes.
Hypothesis: an earlier version of the pipeline used yolov8n.pt or yolo11n.pt for detection.
"""
import json

with open('f:/anomaly/data/events.json', encoding='utf-8') as f:
    raw = json.load(f)
events = raw if isinstance(raw, list) else raw.get('events', [])

# Focus on chair/dining table/vase/bottle - person could be from weapon_best in detect mode
pure_coco = {'chair','dining table','vase','bottle','laptop','tv','couch'}

chair_events = [e for e in events
                if any(o.lower() in pure_coco for o in e.get('objects_detected',[]))]
print(f"Events with pure COCO-only classes (chair/dining table/vase/bottle): {len(chair_events)}")

# Time range
tss = sorted(e.get('timestamp','') for e in chair_events)
print(f"Date range: {tss[0][:16]} to {tss[-1][:16]}")

print()
# Check reasoning field for model clues  
for e in chair_events[:5]:
    print("objects:", e.get('objects_detected'))
    print("reasoning:", e.get('reasoning','')[:250])
    print("risk:", e.get('risk_level'))
    print("yolo_count:", e.get('yolo_detections_count'))
    print("vlm_env_infer:", e.get('vlm_environment_inference',''))
    print("---")

# Check: person events came with zone violations
# This suggests they were triggered by the weapon_best.pt (detect) model
# But chair/dining table cannot come from weapon_best (which only has Helmet/without helmet)
# Let's check if ALL chair events have zone_violations = true
print()
chair_only = [e for e in events if any(o.lower() in {'chair','dining table','vase','bottle'}
                                       for o in e.get('objects_detected',[]))]
print(f"chair/dining table/vase/bottle events: {len(chair_only)}")
zones_present = sum(1 for e in chair_only if e.get('zone_violations'))
print(f"  of which have zone_violations: {zones_present}")

# Check if the 'person' detections come alongside zone violations
# (weapon_best.pt runs in detect mode and could detect Helmet class at a person-shaped bbox)
person_events = [e for e in events if 'person' in [o.lower() for o in e.get('objects_detected',[])]]
print(f"\nTotal 'person' events: {len(person_events)}")
person_with_zones = sum(1 for e in person_events if e.get('zone_violations'))
print(f"  'person' events with zone_violations: {person_with_zones}")
