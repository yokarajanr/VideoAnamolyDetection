@echo off
echo ============================================================
echo  Hybrid YOLO-VLM-RAG Surveillance Platform — Launcher
echo ============================================================
echo.

REM Check if Python virtual environment exists
if not exist "backend\venv\Scripts\activate.bat" (
    echo [SETUP] Creating virtual environment...
    python -m venv backend\venv
    echo [SETUP] Installing dependencies...
    backend\venv\Scripts\pip install -r backend\requirements.txt
    echo.
)

echo [START] Activating virtual environment...
call backend\venv\Scripts\activate.bat

echo [START] Launching FastAPI backend on http://localhost:8000
echo [INFO]  Dashboard: http://localhost:8000/
echo [INFO]  API Docs:  http://localhost:8000/docs
echo.
echo [INFO]  Press Ctrl+C to stop the server
echo.

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
