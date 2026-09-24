import os
import matplotlib.pyplot as plt
import numpy as np

# Ensure images directory exists
os.makedirs('images', exist_ok=True)

# 1. Latency Benchmark Chart (Bar Chart)
def generate_latency_chart():
    labels = ['YOLO Detect (Dual)', 'AnomalyEngine']
    mean_latency = [142.78, 0.06]
    p95_latency = [155.56, 0.07]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    rects1 = ax.bar(x - width/2, mean_latency, width, label='Mean (ms)', color='#2b8cbe')
    rects2 = ax.bar(x + width/2, p95_latency, width, label='p95 (ms)', color='#a6bddb')

    ax.set_ylabel('Latency (ms)')
    ax.set_title('Pipeline Stage Latency (CPU-Only, AMD64)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.set_yscale('log') # Log scale because of huge difference

    # Add labels
    ax.bar_label(rects1, padding=3)
    ax.bar_label(rects2, padding=3)

    fig.tight_layout()
    plt.savefig('images/latency_benchmark.png', dpi=600)
    plt.close()

# 2. Retrospective Fusion Ablation (Grouped Bar Chart)
def generate_ablation_chart():
    labels = ['Critical', 'High', 'Medium', 'Low']
    yolo_only = [12, 0, 0, 813]
    full_engine = [405, 355, 65, 0]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    rects1 = ax.bar(x - width/2, yolo_only, width, label='YOLO-Only Policy', color='#bdbdbd')
    rects2 = ax.bar(x + width/2, full_engine, width, label='Full AnomalyEngine', color='#de2d26')

    ax.set_ylabel('Number of Events')
    ax.set_title('Retrospective Fusion Ablation (825 Events)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    ax.bar_label(rects1, padding=3)
    ax.bar_label(rects2, padding=3)

    fig.tight_layout()
    plt.savefig('images/ablation_study.png', dpi=600)
    plt.close()

# 3. Event Concentration (Pie Chart)
def generate_concentration_chart():
    labels = ['Fighting', 'Road Accidents', 'Robbery', 'Normal', 'Explosion', 'Shooting', 'Remaining']
    sizes = [27.4, 25.0, 19.5, 2.5, 1.5, 0.7, 23.4]
    colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628']
    explode = (0.05, 0, 0, 0, 0, 0, 0)  # explode 1st slice

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
           shadow=False, startangle=140)
    ax.axis('equal')
    ax.set_title('Event Concentration by Class')

    plt.savefig('images/event_concentration.png', dpi=600)
    plt.close()

if __name__ == '__main__':
    generate_latency_chart()
    generate_ablation_chart()
    generate_concentration_chart()
    print("Charts successfully generated in f:\\anomaly\\images\\")
