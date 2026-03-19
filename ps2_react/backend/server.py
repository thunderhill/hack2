import os, ssl, warnings

# ── SSL bypass — MUST be before any other import ─────────────────────────────
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ── Path setup ────────────────────────────────────────────────────────────────
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root / "src"))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_project_root / ".env", override=True)

# ── FastAPI app ───────────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pipeline_anomaly.agent import explain_anomaly
from pipeline_anomaly.config import MODEL_OPTIONS

app = FastAPI(title="Pipeline Anomaly Explainer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    log_snippet: str
    model_key: str = "gpt-4o-mini"


@app.get("/api/models")
def list_models():
    return {"models": MODEL_OPTIONS}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    try:
        result = explain_anomaly(req.log_snippet, req.model_key)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Serve React build if it exists ────────────────────────────────────────────
_frontend_dist = _project_root / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
