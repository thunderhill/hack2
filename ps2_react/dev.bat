@echo off
REM ── PS2 React: Dev mode (hot reload) ──────────────────────────────────────
REM Starts backend + frontend dev server separately for hot reload.
REM Run this from the ps2_react folder on Windows.

echo === Starting FastAPI backend (port 8000) ===
start "Backend" cmd /c "python backend/server.py"

echo === Starting Vite dev server (port 5173) ===
cd frontend
call npm install
call npm run dev
