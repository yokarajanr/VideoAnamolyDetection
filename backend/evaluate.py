"""
evaluate.py — Benchmarking and Evaluation Script for Hybrid YOLO-VLM

This script runs a structured evaluation of the anomaly detection pipeline
against a local dataset of images. It calculates academic metrics
(Precision, Recall, F1-Score, Latency) and generates a Confusion Matrix.

Usage:
1. Create a folder `data/eval_dataset/` with two subfolders:
   - `data/eval_dataset/normal/` (put normal images here)
   - `data/eval_dataset/anomaly/` (put anomalous images here)
2. Run `python evaluate.py`
"""

import os
import time
import json
from pathlib import Path
from tqdm import tqdm
import pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

# Suppress ultra-verbose logs during evaluation
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)

from core.detector import Detector
from core.vlm_analyzer import VLMAnalyzer
from config import DATA_DIR

EVAL_DIR = DATA_DIR / "eval_dataset"

def setup_directories():
    """Ensure evaluation directories exist."""
    normal_dir = EVAL_DIR / "normal"
    anomaly_dir = EVAL_DIR / "anomaly"
    
    normal_dir.mkdir(parents=True, exist_ok=True)
    anomaly_dir.mkdir(parents=True, exist_ok=True)
    
    return normal_dir, anomaly_dir

def run_evaluation():
    normal_dir, anomaly_dir = setup_directories()
    
    # Gather image paths and ground truths (0 = normal, 1 = anomaly)
    dataset = []
    
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for path in normal_dir.glob(ext):
            dataset.append({"path": path, "ground_truth": 0})
        for path in anomaly_dir.glob(ext):
            dataset.append({"path": path, "ground_truth": 1})
            
    if not dataset:
        print(f"❌ No images found in {EVAL_DIR}.")
        print("Please add .jpg or .png images to the 'normal' and 'anomaly' subfolders.")
        return

    print(f"📊 Starting Evaluation on {len(dataset)} images...")
    
    # Initialize Core Components
    detector = Detector()
    vlm = VLMAnalyzer()
    
    results = []
    
    for item in tqdm(dataset, desc="Evaluating Images"):
        filepath = item["path"]
        ground_truth = item["ground_truth"]
        
        try:
            # 1. Read Image Bytes
            with open(filepath, "rb") as f:
                frame_bytes = f.read()
                
            # 2. YOLO Detection
            yolo_start = time.time()
            # detector.detect expects a numpy array, but we can decode bytes
            import cv2
            import numpy as np
            nparr = np.frombuffer(frame_bytes, np.uint8)
            frame_cv2 = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            detections, _ = detector.detect(frame_cv2)
            yolo_latency = time.time() - yolo_start
            
            # 3. VLM Analysis
            vlm_start = time.time()
            det_summary = vlm.format_detections_summary(detections)
            # Call VLM synchronously for the script
            analysis = vlm._call_gemini(
                frame_bytes, 
                "Environment: Public Space. Determine if the scene contains safety violations, hazards, or anomalous behaviors.", 
                det_summary
            )
            vlm_latency = time.time() - vlm_start
            
            # Extract prediction
            is_anomalous = analysis.get("is_anomalous", False)
            prediction = 1 if is_anomalous else 0
            
            results.append({
                "filename": filepath.name,
                "ground_truth": ground_truth,
                "prediction": prediction,
                "yolo_latency_sec": yolo_latency,
                "vlm_latency_sec": vlm_latency,
                "total_latency_sec": yolo_latency + vlm_latency,
                "vlm_reasoning": analysis.get("risk_reasoning", "")
            })
            
            # Anti-Spam: Sleep for 4 seconds to respect Gemini's free-tier rate limit (15 RPM)
            time.sleep(4)
            
        except Exception as e:
            print(f"\nError processing {filepath.name}: {e}")
            
    # ── CALCULATE METRICS ──
    df = pd.DataFrame(results)
    
    y_true = df["ground_truth"]
    y_pred = df["prediction"]
    
    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    avg_latency = df["total_latency_sec"].mean()
    
    print("\n" + "="*40)
    print("📈 EVALUATION RESULTS")
    print("="*40)
    print(f"Total Images   : {len(df)}")
    print(f"Accuracy       : {accuracy:.2%}")
    print(f"Precision      : {precision:.2%}")
    print(f"Recall         : {recall:.2%}")
    print(f"F1-Score       : {f1:.2%}")
    print(f"Avg Latency    : {avg_latency:.2f} seconds/frame")
    print("="*40)
    
    # ── SAVE CSV ──
    report_path = EVAL_DIR / "evaluation_report.csv"
    df.to_csv(report_path, index=False)
    print(f"📄 Detailed report saved to: {report_path}")
    
    # ── PLOT CONFUSION MATRIX ──
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
                xticklabels=["Predicted Normal", "Predicted Anomaly"],
                yticklabels=["Actual Normal", "Actual Anomaly"])
    plt.title("Hybrid YOLO-VLM Confusion Matrix")
    plt.tight_layout()
    
    plot_path = EVAL_DIR / "confusion_matrix.png"
    plt.savefig(plot_path, dpi=300)
    print(f"📊 Confusion Matrix saved to: {plot_path}")


if __name__ == "__main__":
    run_evaluation()
