# 🛡️ Hybrid YOLO–VLM–RAG Surveillance Platform

> **Final-Year Research Project** — A Hybrid YOLO–Vision Language Model Framework with Retrieval-Augmented Event Memory for Real-Time Video Anomaly Detection

An intelligent AI-powered surveillance platform that goes beyond conventional CCTV recording by combining real-time object detection, vision-language scene understanding, semantic event memory, and natural language querying.

---

## 📐 Architecture

```
Video Feed (Webcam / CCTV / IP Camera)
              ↓
           YOLOv8
              ↓
    Object/Event Detection
              ↓
        Trigger Engine
              ↓
     Gemini 1.5 Flash VLM
              ↓
     Scene Understanding
              ↓
     Context Reasoning
              ↓
    Anomaly Assessment
         (Hybrid Fusion)
              ↓
      Risk Classification
    Low / Medium / High / Critical
              ↓
   Semantic Event Memory (ChromaDB)
              ↓
      RAG Retrieval (Groq LLM)
              ↓
  Dashboard + Chat Interface + Voice Alerts
```

## 🏗️ Technology Stack

| Layer | Technology |
|---|---|
| Object Detection | YOLOv8 (Ultralytics) |
| Vision Language Model | Gemini 1.5 Flash |
| RAG Vector Store | ChromaDB + sentence-transformers |
| RAG Answer Generation | Groq (llama3-8b) |
| Backend Framework | FastAPI + WebSockets |
| Voice Alerts | pyttsx3 (offline TTS) |
| Frontend | Vanilla HTML/CSS/JS |

---

## 🚀 Quick Start

### 1. Configure API Keys

Edit `.env` in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key   # https://aistudio.google.com/app/apikey (free)
GROQ_API_KEY=your_groq_api_key       # https://console.groq.com/keys (free)
```

### 2. Install & Run (Windows)

```batch
# Double-click start.bat  (creates venv automatically on first run)
# OR manually:

cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Open the Dashboard

Navigate to: **http://localhost:8000/**

- Click **▶ Start Stream** to begin camera monitoring
- The system will auto-detect objects, analyze scenes, and store events

---

## 📁 Project Structure

```
anomaly/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Configuration loader
│   ├── requirements.txt
│   │
│   ├── core/
│   │   ├── detector.py            # YOLOv8 detection engine
│   │   ├── vlm_analyzer.py        # Gemini VLM scene analysis
│   │   ├── anomaly_engine.py      # Multi-source anomaly fusion
│   │   ├── trigger_engine.py      # Smart VLM trigger logic
│   │   ├── environment_manager.py # 9 environment profiles
│   │   └── zone_manager.py        # Polygon zone violation detection
│   │
│   ├── memory/
│   │   ├── models.py              # Pydantic data models
│   │   ├── event_store.py         # ChromaDB + JSON event store
│   │   └── rag_engine.py          # RAG retrieval + Groq answer gen
│   │
│   ├── alerts/
│   │   └── voice_alert.py         # pyttsx3 TTS voice alerts
│   │
│   ├── api/
│   │   ├── routes_stream.py       # WebSocket video stream
│   │   ├── routes_events.py       # Event history API
│   │   ├── routes_rag.py          # RAG query API
│   │   ├── routes_zones.py        # Zone management API
│   │   └── routes_environment.py  # Environment config API
│   │
│   └── utils/
│       ├── frame_extractor.py     # Camera/video utilities
│       └── image_utils.py         # Base64/PIL/CV2 converters
│
├── frontend/
│   ├── index.html                 # Main SPA shell
│   ├── style.css                  # Premium dark design system
│   ├── app.js                     # App controller & routing
│   └── js/
│       ├── api.js                 # Backend API client
│       ├── stream.js              # WebSocket video handler
│       ├── events.js              # Event history UI
│       ├── rag_chat.js            # Surveillance AI chat
│       └── zone_canvas.js         # Zone drawing tool
│
├── data/
│   └── chroma_db/                 # ChromaDB vector store (auto-created)
│
├── .env                           # API keys (edit this!)
├── start.bat                      # One-click Windows launcher
└── README.md
```

---

## 🎯 Features

### Live Monitoring
- Real-time YOLOv8 object detection at 15fps
- Gemini Flash VLM scene analysis (triggered intelligently, ~every 3s)
- Risk level indicator: Low / Medium / High / Critical
- Live detection panel and anomaly alerts

### Environment-Aware Analysis
9 built-in environment profiles:
- 🏠 Home | 🏢 Office | 🎓 Classroom | 🔬 Laboratory
- 🏭 Factory | 📦 Warehouse | 🚗 Parking | 🚶 Corridor | ⚙️ Custom

Each profile defines expected activities, anomaly types, and risk weights.

### Zone-Based Monitoring
- Draw restricted/safe polygon zones directly on the camera feed
- Automatic zone violation detection triggers immediate alerts

### Semantic Event Memory
Events stored as vector embeddings in ChromaDB with full metadata:
```json
{
  "timestamp": "2026-07-14T15:30:00",
  "environment": "Laboratory",
  "event_type": "No PPE Detected",
  "risk_level": "High",
  "description": "A person entered the lab without protective equipment.",
  "recommended_action": "Verify compliance with safety protocols."
}
```

### RAG Natural Language Querying
Ask questions in plain English:
- *"What anomalies occurred today?"*
- *"Were any weapons detected this week?"*
- *"Summarize critical events in the laboratory"*

### Voice Alerts
Offline TTS announces High/Critical events:
- *"Warning. Unauthorized entry detected in the restricted zone."*
- *"Emergency. Fire detected. Please evacuate immediately."*

---

## 🔬 Research Contribution

The novelty of this project is the **hybrid multi-source fusion architecture**:

| Component | Contribution |
|---|---|
| YOLOv8 | Fast real-time object detection |
| Gemini VLM | Scene understanding + context reasoning |
| Anomaly Engine | Fuses YOLO + VLM + zones + environment rules |
| ChromaDB + Embeddings | Semantic event memory (not just raw video) |
| RAG + Groq LLM | Explainable natural language event querying |

No single component is novel alone — the contribution is their **integration** into a unified, explainable, and intelligent surveillance framework.

---

## ⚙️ Configuration

All settings in `.env`:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Gemini 1.5 Flash API key (required) |
| `GROQ_API_KEY` | — | Groq LLM API key (required for RAG) |
| `CAMERA_SOURCE` | `0` | Webcam index or RTSP URL |
| `YOLO_MODEL` | `yolov8n.pt` | YOLO weights (auto-downloaded) |
| `YOLO_CONFIDENCE` | `0.40` | Detection confidence threshold |
| `VLM_COOLDOWN_SECONDS` | `3.0` | Minimum time between VLM calls |
| `DEFAULT_ENVIRONMENT` | `office` | Initial surveillance environment |
| `VOICE_ENABLED` | `true` | Enable TTS voice alerts |

---

## 📋 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `ws://host/ws/stream` | WebSocket | Live video stream pipeline |
| `/api/events` | GET | Paginated event history |
| `/api/events/stats` | GET | Aggregated statistics |
| `/api/rag/query` | POST | Natural language RAG query |
| `/api/rag/summary` | GET | Daily surveillance summary |
| `/api/zones` | GET/POST/DELETE | Zone management |
| `/api/environment` | GET/POST | Environment configuration |
| `/api/health` | GET | System health check |
| `/docs` | — | Interactive Swagger API docs |
