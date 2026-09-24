"""
Task 2: Standalone latency benchmark — no live server needed.
Generates a synthetic test frame (640x480 black with white rectangle)
and runs the full detect→assess pipeline 50 times.
Run from: f:/anomaly/backend/
"""
import time, statistics, sys, platform
import numpy as np
import cv2

# ── Hardware spec ──────────────────────────────────────────────────────────────
import psutil
import subprocess

def get_cpu_name():
    if platform.system() == "Windows":
        try:
            r = subprocess.check_output("wmic cpu get name", shell=True).decode()
            return r.strip().split("\n")[-1].strip()
        except: pass
    return platform.processor()

ram_gb = round(psutil.virtual_memory().total / 1024**3, 1)
cpu    = get_cpu_name()

try:
    import torch
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None (CPU only)"
    cuda = torch.cuda.is_available()
except:
    gpu = "Unknown"
    cuda = False

print("=" * 55)
print("HARDWARE SPEC")
print("=" * 55)
print(f"  CPU : {cpu}")
print(f"  RAM : {ram_gb} GB")
print(f"  GPU : {gpu}")
print(f"  CUDA: {cuda}")
print()

# ── Load models ────────────────────────────────────────────────────────────────
sys.path.insert(0, ".")
from core.detector import DualYOLODetector
from core.anomaly_engine import AnomalyEngine
from core.environment_manager import EnvironmentManager

detector = DualYOLODetector()
env_mgr  = EnvironmentManager()
engine   = AnomalyEngine(env_mgr)

# ── Synthetic test frame ───────────────────────────────────────────────────────
frame = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.rectangle(frame, (100, 100), (300, 400), (200, 200, 200), -1)

RUNS = 50
print(f"Running {RUNS} inference iterations on a 640×480 synthetic frame...")
print()

yolo_times  = []
fusion_times = []

for i in range(RUNS):
    # YOLO
    t0 = time.perf_counter()
    detections = detector.detect(frame)
    t1 = time.perf_counter()
    yolo_times.append((t1 - t0) * 1000)  # ms

    # Fusion (AnomalyEngine only — no VLM)
    t2 = time.perf_counter()
    report = engine.assess(detections, vlm_analysis=None, zone_violations=[])
    t3 = time.perf_counter()
    fusion_times.append((t3 - t2) * 1000)

def stats(times):
    return {
        "mean":   round(statistics.mean(times), 2),
        "median": round(statistics.median(times), 2),
        "p95":    round(sorted(times)[int(len(times) * 0.95)], 2),
        "min":    round(min(times), 2),
        "max":    round(max(times), 2),
    }

ys = stats(yolo_times)
fs = stats(fusion_times)

total_mean = ys["mean"] + fs["mean"]
fps_mean   = round(1000 / total_mean, 1) if total_mean > 0 else 0

print("=" * 55)
print("LATENCY RESULTS (ms) — no VLM call (offline pipeline)")
print("=" * 55)
print(f"\n{'Stage':<25} {'Mean':>7} {'Median':>8} {'p95':>7} {'Min':>7} {'Max':>7}")
print("-" * 55)
print(f"{'YOLO Detect (dual model)':<25} {ys['mean']:>7} {ys['median']:>8} {ys['p95']:>7} {ys['min']:>7} {ys['max']:>7}")
print(f"{'AnomalyEngine.assess()':<25} {fs['mean']:>7} {fs['median']:>8} {fs['p95']:>7} {fs['min']:>7} {fs['max']:>7}")
print("-" * 55)
print(f"{'TOTAL (no VLM)':<25} {round(total_mean,2):>7}  ms")
print(f"{'Effective FPS (no VLM)':<25} {fps_mean:>7}  fps")
print()
print("NOTE: VLM (Gemini API) round-trip is NOT included — requires live API.")
print("      Expected VLM latency: 800–2500 ms (network-dependent).")
print("      With VLM in pipeline: effective FPS drops to ~0.4–1.2 fps (throttled).")
