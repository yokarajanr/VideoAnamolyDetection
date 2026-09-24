"""Trace COCO label source in events.json"""
import json

with open('f:/anomaly/data/events.json', encoding='utf-8') as f:
    raw = json.load(f)
events = raw if isinstance(raw, list) else raw.get('events', [])

coco_classes = {'chair','dining table','person','vase','bottle','laptop','tv','couch'}
coco_events = []
for e in events:
    objs = [o.lower() for o in e.get('objects_detected', [])]
    found = [o for o in objs if o in coco_classes]
    if found:
        coco_events.append({
            'ts': e.get('timestamp','')[:16],
            'env': e.get('environment',''),
            'objs': found,
            'risk': e.get('risk_level',''),
            'desc': e.get('description','')[:200]
        })

print(f"Events with COCO classes: {len(coco_events)}")
print()

print("Sample COCO events (first 8):")
for ev in coco_events[:8]:
    print(f"  [{ev['ts']}] env={ev['env']} objs={ev['objs']} risk={ev['risk']}")

print()
print("VLM desc snippet for first COCO event:")
if coco_events:
    print(" ", coco_events[0]['desc'])

# Check if ucf_crime model could ever produce these
# It cannot - it only classifies into 14 UCF classes
# So these must come from: (a) a different model used historically, or (b) VLM text parsing
# Let's check the text_content field for clues
print()
print("Checking text_content of COCO events for model clues:")
for e in events:
    objs = [o.lower() for o in e.get('objects_detected', [])]
    if 'chair' in objs or 'dining table' in objs:
        tc = e.get('text_content','')[:400]
        print(" text_content snippet:", tc)
        print(" reasoning:", e.get('reasoning','')[:200])
        break
