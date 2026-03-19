#!/usr/bin/env bash
# PS2 React: Pipeline Anomaly Explainer
# Run this from the ps2_react folder

set -e

echo "=== Setting up Python backend ==="
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example — please add your API key!"
    exit 1
fi

pip install -e . 2>/dev/null || pip install openai pydantic python-dotenv fastapi "uvicorn[standard]" httpx

echo "=== Setting up React frontend ==="
cd frontend
[ -d node_modules ] || npm install

echo "=== Building React frontend ==="
npm run build
cd ..

echo "=== Starting server on http://localhost:8000 ==="
python backend/server.py
