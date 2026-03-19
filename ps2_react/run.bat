@echo off
REM ── PS2 React: Pipeline Anomaly Explainer ──────────────────────────────────
REM Run this from the ps2_react folder on Windows

echo === Setting up Python backend ===
if not exist ".env" (
    copy .env.example .env
    echo Created .env from .env.example — please add your API key!
    pause
    exit /b 1
)

pip install -e . >nul 2>&1
if errorlevel 1 (
    echo Installing Python dependencies...
    pip install openai pydantic python-dotenv fastapi "uvicorn[standard]" httpx
)

echo === Setting up React frontend ===
cd frontend
if not exist "node_modules" (
    echo Installing npm packages...
    call npm install
)

echo === Building React frontend ===
call npm run build
cd ..

echo === Starting server on http://localhost:8000 ===
python backend/server.py
