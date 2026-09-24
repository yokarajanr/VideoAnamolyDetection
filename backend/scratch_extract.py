import json
import random

with open('f:/anomaly/data/events.json', encoding='utf-8') as f:
    data = json.load(f)

events_by_risk = {}
for e in data:
    risk = e.get('risk_level', 'Unknown')
    if risk not in events_by_risk:
        events_by_risk[risk] = []
    events_by_risk[risk].append(e)

print(f"Total events found: {len(data)}")

# Sample a few events from each risk category
for risk, events in events_by_risk.items():
    sample = random.sample(events, min(3, len(events)))
    for e in sample:
        env = e.get('environment', 'Unknown')
        type = e.get('event_type', 'Unknown')
        yolo = e.get('objects_detected', [])
        desc = e.get('description', '')[:250].replace('\n', ' ')
        anom = e.get('is_anomalous', False)
        print(f"---")
        print(f"Scenario/Env: {env}")
        print(f"Type: {type}")
        print(f"YOLO result: {yolo}")
        print(f"VLM result (snippet): {desc}")
        print(f"Final risk: {risk}")
        print(f"Alert generated: {'Yes' if risk in ['High', 'Critical'] else 'No'}")
        print(f"Correct: {anom}")
