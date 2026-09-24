"""
RAG query evaluation — runs all 15 queries directly via the RAGEngine,
using the live MongoDB connection from .env. No web server needed.
"""
import asyncio, sys, os
sys.path.insert(0, '.')
os.chdir('f:/anomaly/backend')

from memory.event_store import EventStore
from memory.rag_engine import RAGEngine
from memory.models import RAGQuery

QUERIES = [
    "What anomalies occurred today?",
    "Were any weapons detected this week?",
    "Show all critical events in the office",
    "Summarize fighting incidents",
    "How many robberies were logged?",
    "What happened on 2026-09-01?",
    "Were there any zone violations?",
    "Describe the most dangerous event",
    "How many explosions were detected?",
    "What is a normal day like?",
    "Any camera malfunctions?",
    "When was the last road accident?",
    "List events with no people detected",
    "What environments were monitored?",
    "Were there any PPE violations?",
]

async def run():
    store = EventStore()
    engine = RAGEngine(store)

    for i, q in enumerate(QUERIES, 1):
        print(f"\n{'='*60}")
        print(f"Q{i:02d}: {q}")
        print('='*60)
        try:
            resp = await engine.query(RAGQuery(question=q, max_context_events=3))
            # Print top-3 retrieved events
            for j, ev in enumerate(resp.source_events[:3], 1):
                ts  = str(ev.get('timestamp',''))[:16]
                cls = ev.get('objects_detected', ['—'])
                risk = ev.get('risk_level','?')
                etype = ev.get('event_type','?')
                env  = ev.get('environment','?')
                print(f"  Retrieved {j}: [{ts}] {env} | {etype} | risk={risk} | objs={cls}")
            print(f"\n  ANSWER: {resp.answer[:400]}")
        except Exception as e:
            print(f"  ERROR: {e}")

asyncio.run(run())
