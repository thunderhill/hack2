# PS2 — Pipeline Anomaly Explainer: Developer Guide

## Architecture Overview

```
User (Browser)
     │
     ▼
┌─────────────────────────────────────────┐
│  app/main.py  (Streamlit UI)            │
│  - Renders input form                   │
│  - Calls explain_anomaly()              │
│  - Displays AnomalyExplanation fields   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  src/pipeline_anomaly/agent.py          │
│  explain_anomaly(log_snippet, model_key)│
│  - Builds messages from prompts         │
│  - Calls OpenAI with create()            │
│  - Returns AnomalyExplanation           │
└──────┬───────────────────┬──────────────┘
       │                   │
       ▼                   ▼
┌────────────┐    ┌────────────────────────┐
│ config.py  │    │ prompts.py             │
│ OpenAI     │    │ SYSTEM_PROMPT          │
│ client     │    │ build_user_message()   │
└────────────┘    └────────────────────────┘
       │
       ▼
TCS GenAI Lab API (genailab.tcs.in)
(structured output → AnomalyExplanation)
       │
       ▼
┌─────────────────────────────────────────┐
│  src/pipeline_anomaly/models.py         │
│  AnomalyExplanation (Pydantic)          │
└─────────────────────────────────────────┘
```

**Data flow:** User pastes log → UI calls `explain_anomaly()` → agent builds prompt → TCS GenAI Lab API parses response into `AnomalyExplanation` → UI renders fields.

---

## Project Structure

```
ps2/
├── app/
│   └── main.py                    # Streamlit app — UI only, no business logic
├── src/
│   └── pipeline_anomaly/
│       ├── __init__.py
│       ├── agent.py               # Single function: explain_anomaly()
│       ├── config.py              # OpenAI client factory (TCS proxy) + model map
│       ├── models.py              # AnomalyExplanation Pydantic model
│       └── prompts.py             # System prompt + user message builder
└── pyproject.toml                 # Package metadata (hatchling build)
```

---

## Core Components

### `agent.py`

Contains a single function:

```python
def explain_anomaly(log_snippet: str, model_key: str = "gpt-4o") -> AnomalyExplanation:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(log_snippet)},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)
    return AnomalyExplanation(**data)
```

Uses `client.chat.completions.create()` with a JSON-only instruction appended to the system prompt. The response is manually parsed from JSON and validated against the Pydantic model. This is required because the TCS GenAI Lab proxy does not support the `.beta.parse()` structured output endpoint.

### `models.py`

```python
class AnomalyExplanation(BaseModel):
    anomaly_type: str           # e.g., "Dependency Conflict"
    plain_english_summary: str  # Non-technical explanation
    root_cause: str             # Technical root cause
    affected_stage: str         # e.g., "install-dependencies"
    severity: str               # critical | high | medium | low
    remediation_steps: list[str]  # Ordered fix steps
    prevention_tips: list[str]    # Long-term prevention
```

All fields are `str` or `list[str]` — deliberately simple to maximize LLM reliability with structured output.

### `prompts.py`

```python
SYSTEM_PROMPT = """You are an expert DevOps engineer and CI/CD pipeline analyst..."""

def build_user_message(log_snippet: str) -> str:
    return f"""Analyze the following CI/CD pipeline log...\n\n--- PIPELINE LOG ---\n{log_snippet}\n--- END LOG ---\n..."""
```

The system prompt establishes the LLM's role and analysis approach. The user message wraps the log in delimiters to prevent prompt injection and clearly separates instruction from data.

### `config.py`

```python
MODEL_OPTIONS = ["gpt-4o", "gpt-4o-mini", "gpt-35-turbo"]
MODEL_DISPLAY_MAP = {
    "gpt-4o": "azure/genailab-maas-gpt-4o",
    "gpt-4o-mini": "azure/genailab-maas-gpt-4o-mini",
    "gpt-35-turbo": "genailab-maas-gpt-35-turbo",
}

@lru_cache(maxsize=1)
def _cached_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/") + "/v1",
        http_client=httpx.Client(verify=False),
    )

def get_llm_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_GENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://genailab.tcs.in")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set in .env")
    return _cached_client(api_key, base_url)
```

The `lru_cache` on `_cached_client` ensures the `OpenAI` client is created once and reused. The client uses `httpx.Client(verify=False)` to bypass the TCS proxy's self-signed TLS certificate. Environment variables are read at call time to support `.env` file loading.

---

## Environment Setup

```bash
# Clone the repo and enter the project
cd /path/to/hack2/ps2

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package in editable mode
pip install -e .

# Create the .env file
cat > .env << 'EOF'
OPENAI_API_KEY=your-hackathon-api-key-here
OPENAI_BASE_URL=https://genailab.tcs.in
PYTHONHTTPSVERIFY=0
REQUESTS_CA_BUNDLE=
CURL_CA_BUNDLE=
EOF

# Run the app
streamlit run app/main.py
```

---

## Extending the App

### Add a new output field

1. Add the field to `models.py`:
   ```python
   class AnomalyExplanation(BaseModel):
       ...
       estimated_fix_time: str = Field(description="Estimated time to fix: minutes | hours | days")
   ```

2. Update `prompts.py` to request the new field:
   ```python
   SYSTEM_PROMPT = """...
   5. Estimate fix time (minutes, hours, or days)
   """
   ```

3. Render the field in `app/main.py`:
   ```python
   st.metric("Est. Fix Time", result.estimated_fix_time)
   ```

### Modify the system prompt

Edit `SYSTEM_PROMPT` in `prompts.py`. The prompt instructs the LLM on how to analyze logs. Keep instructions numbered and specific — vague prompts produce inconsistent structured output.

### Add a new model option

1. Add the model key and deployment name to `config.py`:
   ```python
   MODEL_OPTIONS = ["gpt-4o", "gpt-4o-mini", "gpt-35-turbo", "gpt-4-turbo"]
   MODEL_DISPLAY_MAP = {
       ...
       "gpt-4-turbo": "genailab-maas-gpt-4-turbo",
   }
   ```

2. The sidebar selector in `app/main.py` reads `MODEL_OPTIONS` automatically — no UI changes needed.

---

## Testing

### Test the agent function directly

```python
import os
os.environ["OPENAI_API_KEY"] = "your_key"

from pipeline_anomaly.agent import explain_anomaly

log = """
[ERROR] npm ERR! code ERESOLVE
[ERROR] npm ERR! ERESOLVE unable to resolve dependency tree
"""
result = explain_anomaly(log, model_key="gpt-4o-mini")
print(result.severity)
print(result.remediation_steps)
```

### Mock Azure OpenAI for unit tests

```python
from unittest.mock import MagicMock, patch
from pipeline_anomaly.models import AnomalyExplanation

mock_result = AnomalyExplanation(
    anomaly_type="Dependency Conflict",
    plain_english_summary="npm cannot resolve peer dependencies",
    root_cause="react-router-dom@5 requires react@^17, but react@18 is installed",
    affected_stage="install-dependencies",
    severity="high",
    remediation_steps=["Run npm install --legacy-peer-deps"],
    prevention_tips=["Pin dependency versions in package.json"],
)

with patch("pipeline_anomaly.agent.get_llm_client") as mock_client:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = mock_result.model_dump_json()
    mock_client.return_value.chat.completions.create.return_value = mock_response

    from pipeline_anomaly.agent import explain_anomaly
    result = explain_anomaly("any log text", "gpt-4o")
    assert result.severity == "high"
```

---

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8501
CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0"]
```

```bash
docker build -t ps2-pipeline-anomaly .
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  -e OPENAI_BASE_URL=https://genailab.tcs.in \
  ps2-pipeline-anomaly
```

### Streamlit Cloud

1. Push the `ps2/` directory to a GitHub repository.
2. Connect the repo at [share.streamlit.io](https://share.streamlit.io).
3. Set the main file path to `app/main.py`.
4. Add secrets in the Streamlit Cloud dashboard under **Settings → Secrets**:
   ```toml
   OPENAI_API_KEY = "your_key"
   OPENAI_BASE_URL = "https://genailab.tcs.in"
   ```

### Production environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | TCS GenAI Lab API key |
| `OPENAI_BASE_URL` | TCS GenAI Lab proxy URL |
| `PYTHONHTTPSVERIFY` | Set to `0` to bypass self-signed cert |
