# A Hybrid YOLO-VLM-RAG Framework for Real-Time Anomaly Detection and Context-Aware Surveillance

**Authors**: [Your Name]
**Institution**: [Your University / Institution]

**Abstract**—Traditional surveillance systems rely heavily on human monitoring or basic motion detection, which are prone to fatigue and high false-positive rates. While modern computer vision models like YOLO have improved real-time object detection, they lack the cognitive ability to understand complex behavioral contexts, such as distinguishing between a person holding a tool versus a weapon in a threatening manner. This paper proposes a novel Hybrid YOLO-VLM-RAG Surveillance Platform that bridges the gap between fast, localized object detection and deep, contextual scene understanding. The framework integrates YOLOv11m for high-speed primary detection (weapons, fire, persons), a Vision-Language Model (Gemini) for explainable behavioral analysis, and Retrieval-Augmented Generation (RAG) with FAISS and MongoDB to maintain temporal event memory. The system is deployed via a real-time FastAPI backend, delivering instant alerts through WebSockets, SMTP Email, and TTS Voice notifications. Our evaluation focuses on predictive accuracy, explainability, latency, and operational usability in real-world security deployments.

**Index Terms**—Anomaly Detection, Vision-Language Models (VLM), YOLO, Retrieval-Augmented Generation (RAG), Explainable AI, Real-time Surveillance, Cybersecurity.

---

## I. INTRODUCTION

Intelligent video surveillance is a critical component of modern physical security infrastructure. Historically, these systems required continuous human observation, which is unscalable and susceptible to human error. The advent of Deep Learning, particularly Convolutional Neural Networks (CNNs), enabled automated object detection and classification in real-time.

However, recognizing an object (e.g., a knife) does not necessarily imply a threat. Contextual understanding—such as analyzing body language, intent, and environmental factors—is required to accurately classify an event as an anomaly or a benign action. Traditional object detectors operate as "black boxes" that output bounding boxes and confidence scores, providing no semantic explanation for their predictions. Security analysts require actionable, explainable insights to initiate emergency response procedures.

To address these limitations, we propose a Hybrid YOLO-VLM-RAG architecture. This framework combines the micro-second inference speed of YOLO with the deep reasoning capabilities of Vision-Language Models (VLMs) and the long-term memory retrieval of RAG.

## II. RELATED WORK

### A. Traditional Surveillance Systems
Early automated surveillance relied on background subtraction, motion detection, and handcrafted feature extraction (e.g., HOG, SIFT). These methods suffer from environmental sensitivity, struggling with lighting changes, shadows, and occlusions.

### B. Machine Learning-Based Detection
State-of-the-art surveillance utilizes single-shot detectors like YOLO (You Only Look Once) and SSD. These models achieve real-time processing speeds (30+ FPS) and high accuracy for standard object classes. However, they lack temporal awareness and fail to comprehend complex scenes involving human-object interactions.

### C. Explainable Artificial Intelligence (XAI) in Vision
Explainable AI (XAI) methods, such as Grad-CAM and SHAP, provide saliency maps indicating which pixels influenced a CNN's decision. While useful for model debugging, these heatmaps do not provide human-readable semantic explanations of *why* an event is dangerous, which is essential for rapid security decision-making.

## III. RESEARCH GAP

The existing literature provides a strong foundation for object detection, but several limitations remain for practical anomaly detection:
1. **Lack of Semantic Explanations:** Bounding boxes and confidence scores do not explain the *intent* of an actor in a scene.
2. **Absence of Temporal Memory:** Most frame-by-frame detectors have zero memory of past events, leading to repetitive alerts for the same ongoing incident.
3. **High Computational Cost of VLMs:** Running large multimodal models on every video frame is computationally prohibitive for real-time applications.

**Therefore, there is a need for an integrated framework that jointly evaluates high-speed localized detection, semantic explainability, temporal memory, and computational efficiency.**

## IV. PROPOSED SYSTEM

### A. Overall Architecture
The proposed framework follows a cascaded, event-driven workflow:
1. **Camera Stream & Frame Extraction:** Continuous video input is processed at a fixed framerate.
2. **Primary Detection (YOLOv11m):** Extracts bounding boxes and classes (e.g., person, weapon, fire).
3. **Trigger Engine & Zone Manager:** Evaluates spatial zones (Restricted/Safe) and detection confidence. If a threshold is met, it triggers the secondary analysis.
4. **Cognitive Analysis (VLM):** The triggered frame is sent to a Vision-Language Model (Gemini 1.5/3.6 Flash) for deep behavioral analysis and risk assessment.
5. **Memory Retrieval (RAG):** The system compares the current VLM analysis with historical events (FAISS vector store) to provide temporal context.
6. **Alerting System:** If the risk is High/Critical, the system fires Voice (TTS) and Email (SMTP) alerts and logs the event to MongoDB.

## V. MACHINE LEARNING MODELS

### A. YOLOv11m (Primary Detector)
YOLOv11m is utilized for its optimal balance between speed (GFLOPs) and mean Average Precision (mAP). It acts as a strict spatial filter, ensuring that computationally expensive VLMs are only invoked when suspicious objects or persons enter restricted zones.

### B. Vision-Language Model (Secondary Brain)
The VLM (Google Gemini) processes the raw image alongside text prompts containing the YOLO bounding box data. The VLM acts as an Explainability Framework, outputting structured JSON containing:
*   Scene Description
*   Behavioral Analysis
*   Detected Activities
*   Anomalies Found
*   Final Risk Level (Low, Medium, High, Critical)

### C. RAG (Retrieval-Augmented Generation)
We implement RAG using a `SentenceTransformer` (e.g., `all-MiniLM-L6-v2`) to generate embeddings of past VLM event descriptions. These are stored in FAISS (Facebook AI Similarity Search) to allow the VLM to "remember" if a similar anomaly occurred recently, suppressing redundant alerts.

## VI. EXPLAINABILITY FRAMEWORK

Instead of relying on mathematical feature attribution (like SHAP or Permutation Importance), this system pioneers **Semantic Explainability** via VLMs. 

When an anomaly is detected, the VLM generates a human-readable justification. For example, rather than just highlighting a knife, the explanation explicitly states: *"A person is concealing their identity with a helmet indoors and brandishing a knife near the cash register, indicating a high potential for robbery."* 

This reduces the cognitive load on security operators and provides immediate actionable intelligence.

## VII. SYSTEM PERFORMANCE & ROBUSTNESS

### A. Trigger Cooldown Mechanics
To ensure explanation robustness and prevent API throttling, the Trigger Engine implements a dynamic cooldown. During normal operation, the VLM baseline is updated sparingly. During an active threat, the cooldown is bypassed or reduced, ensuring high-resolution tracking of the anomaly.

### B. Prototype Latency
The total response time determines whether the proposed detector is practical for real-time intervention:
*   **YOLO Inference:** ~15-30 ms per frame (Real-time).
*   **VLM API Processing:** ~10-15 seconds (Asynchronous).
*   **RAG Retrieval:** ~5-10 ms.
By making the VLM call asynchronous, the video stream maintains high FPS without stuttering, while the rich analysis resolves in the background.

## VIII. PROTOTYPE IMPLEMENTATION

### A. FastAPI Backend
The backend is built in Python using FastAPI, handling WebSockets for live video streaming, background tasks for VLM polling, and REST routes for historical event querying.

### B. Frontend Dashboard
A vanilla JavaScript frontend provides an interactive security console featuring:
*   Live Video Monitor with drawn bounding boxes.
*   Interactive Zone Drawing (Restricted/Safe areas).
*   Real-time Risk Badges and VLM Description Overlays.
*   Event History timeline fetched from MongoDB.

### C. Multi-Channel Alerting
The system implements a `WinError 10060`-resistant SMTP email alert system (using Port 587 and STARTTLS) and a text-to-speech engine (`pyttsx3`) for immediate physical deterrence.

## IX. CONCLUSION & FUTURE WORK

This paper presents a trustworthy, hybrid artificial intelligence framework for real-time anomaly detection. By cascading YOLO for speed, Gemini for semantic explainability, and FAISS for temporal memory, the system overcomes the limitations of traditional black-box object detectors. 

Future research will focus on adversarial robustness (preventing actors from using adversarial clothing to evade YOLO), integrating audio-based anomaly detection (e.g., glass breaking), and deploying localized open-source VLMs (e.g., LLaVA or Ollama) to remove cloud API dependencies entirely.

---
**References:**
[1] J. Redmon, S. Divvala, R. Girshick, and A. Farhadi, "You Only Look Once: Unified, Real-Time Object Detection," in CVPR, 2016.
[2] Google DeepMind, "Gemini: A Family of Highly Capable Multimodal Models," 2023.
[3] P. Lewis et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," in NeurIPS, 2020.
