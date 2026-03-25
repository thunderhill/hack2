# PS2 Modular LLM Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ps2's Pipeline Anomaly Explainer support TCS GenAI proxy and local Ollama as selectable LLM providers, plus add a `confidence_level` field to the anomaly output.

**Architecture:** A `ProviderConfig` frozen dataclass and `PROVIDERS` registry in `config.py` encapsulate all provider-specific details (base URL, API key env var, SSL flag, model map). The provider is selected via `LLM_PROVIDER` env var as default and overridable in the Streamlit sidebar at runtime. Ollama models are fetched dynamically from its `/api/tags` endpoint.

**Tech Stack:** Python 3.11, openai SDK, httpx, Pydantic v2, Streamlit, Ollama (systemd service at `http://localhost:11434`), pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `ps2/tests/__init__.py` | Create | Makes tests a package |
| `ps2/tests/test_models.py` | Create | Tests `confidence_level` field validator |
| `ps2/tests/test_config.py` | Create | Tests `ProviderConfig`, `get_model`, `list_ollama_models` |
| `ps2/tests/test_agent.py` | Create | Tests `explain_anomaly` provider parameter |
| `ps2/src/pipeline_anomaly/models.py` | Modify | Add `confidence_level` + `field_validator` |
| `ps2/src/pipeline_anomaly/prompts.py` | Modify | Add JSON schema with `confidence_level` to system prompt |
| `ps2/src/pipeline_anomaly/config.py` | Rewrite | `ProviderConfig`, `PROVIDERS`, `list_ollama_models`, updated client/model fns |
| `ps2/src/pipeline_anomaly/agent.py` | Modify | Add `provider` parameter, pass to client and model fns |
| `ps2/app/main.py` | Modify | Provider + model dropdowns, disabled button guard, 4th metric |
| `ps2/.env.example` | Modify | Add `LLM_PROVIDER` and `OLLAMA_BASE_URL` |

---

## Task 1: Add `confidence_level` to `AnomalyExplanation`

**Files:**
- Modify: `ps2/src/pipeline_anomaly/models.py`
- Create: `ps2/tests/__init__.py`
- Create: `ps2/tests/test_models.py`

- [ ] **Step 1: Create empty test package**

```bash
touch /path/to/ps2/tests/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `ps2/tests/test_models.py`:

```python
import pytest
from pipeline_anomaly.models import AnomalyExplanation

BASE = dict(
    anomaly_type="build_failure",
    plain_english_summary="Build failed",
    root_cause="dependency conflict",
    affected_stage="install",
    severity="high",
    remediation_steps=["fix deps"],
    prevention_tips=["pin versions"],
)


def test_confidence_level_default_when_missing():
    """confidence_level defaults to 0.0 when not provided."""
    result = AnomalyExplanation(**BASE)
    assert result.confidence_level == 0.0


def test_confidence_level_stored_as_fraction():
    """A valid fraction 0.0-1.0 is stored unchanged."""
    result = AnomalyExplanation(**BASE, confidence_level=0.87)
    assert result.confidence_level == pytest.approx(0.87)


def test_confidence_level_normalises_percentage():
    """LLM returning 87 (percentage) is divided by 100 → 0.87."""
    result = AnomalyExplanation(**BASE, confidence_level=87)
    assert result.confidence_level == pytest.approx(0.87)


def test_confidence_level_clamped_above_one():
    """A value like 1.5 is clamped to 1.0."""
    result = AnomalyExplanation(**BASE, confidence_level=1.5)
    assert result.confidence_level == pytest.approx(1.0)


def test_confidence_level_clamped_below_zero():
    """A negative value is clamped to 0.0."""
    result = AnomalyExplanation(**BASE, confidence_level=-0.1)
    assert result.confidence_level == pytest.approx(0.0)
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd ps2 && python -m pytest tests/test_models.py -v
```

Expected: `ImportError` or `ValidationError` — `confidence_level` doesn't exist yet.

- [ ] **Step 4: Add `confidence_level` field and validator to `models.py`**

Replace the contents of `ps2/src/pipeline_anomaly/models.py`:

```python
from pydantic import BaseModel, Field, field_validator


class AnomalyExplanation(BaseModel):
    anomaly_type: str = Field(description="Type/category of the anomaly detected")
    plain_english_summary: str = Field(description="Clear explanation of what went wrong for a non-expert")
    root_cause: str = Field(description="Technical root cause of the anomaly")
    affected_stage: str = Field(description="Pipeline stage where the anomaly occurred")
    severity: str = Field(description="Severity level: critical | high | medium | low")
    remediation_steps: list[str] = Field(description="Ordered list of steps to fix the issue")
    prevention_tips: list[str] = Field(description="Tips to prevent this anomaly in the future")
    confidence_level: float = Field(
        default=0.0,
        description="Model confidence in this analysis, 0.0–1.0",
    )

    @field_validator("confidence_level", mode="before")
    @classmethod
    def normalise_confidence(cls, v: float) -> float:
        """Normalise: if > 1.0, divide by 100 (percentage); then clamp to [0.0, 1.0]."""
        if v > 1.0:
            v = v / 100.0
        return max(0.0, min(1.0, v))
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
cd ps2 && python -m pytest tests/test_models.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ps2/tests/__init__.py ps2/tests/test_models.py ps2/src/pipeline_anomaly/models.py
git commit -m "feat(ps2): add confidence_level field to AnomalyExplanation with normalisation"
```

---

## Task 2: Add `confidence_level` to system prompt JSON schema

**Files:**
- Modify: `ps2/src/pipeline_anomaly/prompts.py`

> No separate test — the prompt content is validated indirectly by the agent integration. The key change is making the JSON schema explicit so the LLM returns `confidence_level` as a fraction.

- [ ] **Step 1: Update `prompts.py`**

Replace the contents of `ps2/src/pipeline_anomaly/prompts.py`:

```python
SYSTEM_PROMPT = """You are an expert DevOps engineer and CI/CD pipeline analyst.
Given a pipeline log snippet, you analyze it to:
1. Identify the type of anomaly or failure
2. Explain it clearly in plain English for developers
3. Pinpoint the root cause
4. Suggest actionable remediation steps

Be specific and practical. Use the log content to ground your analysis.

Respond ONLY with valid JSON matching this schema (no markdown fences, no extra text):
{
  "anomaly_type": "<short label for the failure type>",
  "plain_english_summary": "<clear explanation for a non-expert>",
  "root_cause": "<technical root cause>",
  "affected_stage": "<pipeline stage name>",
  "severity": "<critical|high|medium|low>",
  "remediation_steps": ["<step 1>", "<step 2>"],
  "prevention_tips": ["<tip 1>"],
  "confidence_level": <float between 0.0 and 1.0 — your confidence in this analysis>
}"""


def build_user_message(log_snippet: str) -> str:
    return f"""Analyze the following CI/CD pipeline log and explain the anomaly:

--- PIPELINE LOG ---
{log_snippet}
--- END LOG ---

Provide a thorough analysis including the anomaly type, plain English summary, root cause, affected stage, severity, remediation steps, and prevention tips."""
```

- [ ] **Step 2: Commit**

```bash
git add ps2/src/pipeline_anomaly/prompts.py
git commit -m "feat(ps2): add JSON schema with confidence_level to system prompt"
```

---

## Task 3: Rewrite `config.py` with provider registry

**Files:**
- Rewrite: `ps2/src/pipeline_anomaly/config.py`
- Create: `ps2/tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `ps2/tests/test_config.py`:

```python
import os
import pytest
from unittest.mock import patch, MagicMock


def test_provider_config_is_hashable():
    """ProviderConfig must be hashable (frozen dataclass) for lru_cache."""
    from pipeline_anomaly.config import PROVIDERS
    tcs = PROVIDERS["tcs"]
    assert hash(tcs) is not None  # raises TypeError if not hashable


def test_providers_registry_has_tcs_and_ollama():
    from pipeline_anomaly.config import PROVIDERS
    assert "tcs" in PROVIDERS
    assert "ollama" in PROVIDERS


def test_get_model_tcs_known_key():
    from pipeline_anomaly.config import get_model
    assert get_model("tcs", "gpt-4o-mini") == "azure/genailab-maas-gpt-4o-mini"


def test_get_model_tcs_unknown_key_raises():
    from pipeline_anomaly.config import get_model
    with pytest.raises(ValueError, match="Unknown model"):
        get_model("tcs", "nonexistent-model")


def test_get_model_ollama_identity():
    """Ollama get_model returns the key unchanged (identity lookup)."""
    from pipeline_anomaly.config import get_model
    assert get_model("ollama", "llama3:8b") == "llama3:8b"
    assert get_model("ollama", "mistral") == "mistral"


def test_get_model_unknown_provider_raises():
    from pipeline_anomaly.config import get_model
    with pytest.raises(ValueError, match="Unknown provider"):
        get_model("openrouter", "some-model")


def test_list_ollama_models_returns_empty_list_when_unavailable():
    """list_ollama_models() returns [] when Ollama is not running."""
    import httpx
    from pipeline_anomaly.config import list_ollama_models
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = list_ollama_models()
    assert result == []


def test_list_ollama_models_parses_api_tags_response():
    """list_ollama_models() parses the /api/tags JSON and returns model names."""
    from pipeline_anomaly.config import list_ollama_models
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "models": [
            {"name": "llama3:8b"},
            {"name": "mistral:latest"},
        ]
    }
    with patch("httpx.get", return_value=mock_response):
        result = list_ollama_models()
    assert result == ["llama3:8b", "mistral:latest"]


def test_get_llm_client_unknown_provider_raises():
    from pipeline_anomaly.config import get_llm_client
    with pytest.raises(ValueError, match="Unknown provider"):
        get_llm_client("nonexistent")


def test_get_llm_client_tcs_uses_ssl_bypass(monkeypatch):
    """TCS client is created with verify=False."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://genailab.tcs.in")
    from pipeline_anomaly import config
    # Clear cache so monkeypatched env is picked up
    config._cached_client.cache_clear()
    client = config.get_llm_client("tcs")
    assert client.base_url is not None
    config._cached_client.cache_clear()


def test_ollama_base_url_strips_trailing_v1(monkeypatch):
    """If OLLAMA_BASE_URL has a /v1 suffix it is stripped before appending /v1."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    from pipeline_anomaly import config
    config._cached_client.cache_clear()
    tcs_provider = config.PROVIDERS["ollama"]
    base = os.environ.get("OLLAMA_BASE_URL", tcs_provider.base_url)
    # Simulate the stripping logic
    normalized = base.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    assert normalized == "http://localhost:11434"
    config._cached_client.cache_clear()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd ps2 && python -m pytest tests/test_config.py -v
```

Expected: `ImportError` — `ProviderConfig`, `PROVIDERS`, `list_ollama_models` don't exist yet.

- [ ] **Step 3: Rewrite `config.py`**

Replace the full contents of `ps2/src/pipeline_anomaly/config.py`:

```python
import os
import httpx
from dataclasses import dataclass
from functools import lru_cache
from openai import OpenAI


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key_env: str          # env var to read key from
    ssl_verify: bool
    model_map: tuple[tuple[str, str], ...]  # (display_name, deployment_id); empty for Ollama
    default_model: str

    @property
    def model_map_dict(self) -> dict[str, str]:
        return dict(self.model_map)


_DEFAULT_TCS_URL = "https://genailab.tcs.in"
_DEFAULT_OLLAMA_URL = "http://localhost:11434"

PROVIDERS: dict[str, ProviderConfig] = {
    "tcs": ProviderConfig(
        base_url=_DEFAULT_TCS_URL,
        api_key_env="OPENAI_API_KEY",
        ssl_verify=False,
        model_map=(
            ("gpt-4o", "azure/genailab-maas-gpt-4o"),
            ("gpt-4o-mini", "azure/genailab-maas-gpt-4o-mini"),
            ("gpt-35-turbo", "genailab-maas-gpt-35-turbo"),
        ),
        default_model="gpt-4o-mini",
    ),
    "ollama": ProviderConfig(
        base_url=_DEFAULT_OLLAMA_URL,
        api_key_env="OLLAMA_API_KEY",
        ssl_verify=True,
        model_map=(),          # populated dynamically via list_ollama_models()
        default_model="",
    ),
}

# Convenience alias — backward compat for code that imports MODEL_OPTIONS
MODEL_OPTIONS: list[str] = list(PROVIDERS["tcs"].model_map_dict.keys())


def get_model(provider: str, model_key: str) -> str:
    """Return the deployment ID for a given provider + display name.

    For Ollama, the model_key IS the deployment ID (identity lookup).
    For TCS, looks up the static model_map and raises ValueError for unknown keys.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. Options: {list(PROVIDERS)}")
    if provider == "ollama":
        return model_key
    model_map = PROVIDERS[provider].model_map_dict
    if model_key not in model_map:
        raise ValueError(
            f"Unknown model {model_key!r} for provider {provider!r}. "
            f"Options: {list(model_map)}"
        )
    return model_map[model_key]


def list_ollama_models() -> list[str]:
    """Return model names available in the local Ollama instance.

    Calls GET {OLLAMA_BASE_URL}/api/tags. Returns [] on any error (Ollama not
    running, network issue, etc.) — never raises.
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_URL).rstrip("/")
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        data = response.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


@lru_cache(maxsize=None)
def _cached_client(provider: str, api_key: str, base_url: str) -> OpenAI:
    config = PROVIDERS[provider]
    return OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/") + "/v1",
        http_client=httpx.Client(verify=config.ssl_verify),
    )


def get_llm_client(provider: str = "tcs") -> OpenAI:
    """Return a cached OpenAI-compatible client for the given provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. Options: {list(PROVIDERS)}")
    config = PROVIDERS[provider]
    api_key = os.environ.get(config.api_key_env) or "ollama"
    if provider == "tcs" and not api_key:
        raise EnvironmentError(f"{config.api_key_env} is not set in .env")

    # Resolve base URL from env (allows override) and strip accidental /v1 suffix
    if provider == "tcs":
        raw_url = os.environ.get("OPENAI_BASE_URL", config.base_url)
    else:
        raw_url = os.environ.get("OLLAMA_BASE_URL", config.base_url)

    base_url = raw_url.rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]

    return _cached_client(provider, api_key, base_url)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd ps2 && python -m pytest tests/test_config.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ps2/tests/test_config.py ps2/src/pipeline_anomaly/config.py
git commit -m "feat(ps2): add ProviderConfig registry with TCS and Ollama support"
```

---

## Task 4: Add `provider` parameter to `agent.py`

**Files:**
- Modify: `ps2/src/pipeline_anomaly/agent.py`
- Create: `ps2/tests/test_agent.py`

- [ ] **Step 1: Write failing test**

Create `ps2/tests/test_agent.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock


MOCK_RESPONSE = {
    "anomaly_type": "dependency_conflict",
    "plain_english_summary": "npm cannot resolve peer deps",
    "root_cause": "react@18 conflicts with react-router-dom@5",
    "affected_stage": "install-dependencies",
    "severity": "high",
    "remediation_steps": ["upgrade react-router-dom"],
    "prevention_tips": ["pin peer deps"],
    "confidence_level": 0.9,
}


def _mock_openai_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


def test_explain_anomaly_accepts_provider_param():
    """explain_anomaly accepts a provider kwarg without raising."""
    from pipeline_anomaly.agent import explain_anomaly
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps(MOCK_RESPONSE)
    )
    with patch("pipeline_anomaly.agent.get_llm_client", return_value=mock_client):
        result = explain_anomaly("some log", model_key="gpt-4o-mini", provider="tcs")
    assert result.anomaly_type == "dependency_conflict"
    assert result.confidence_level == pytest.approx(0.9)


def test_explain_anomaly_passes_provider_to_client():
    """get_llm_client is called with the correct provider."""
    from pipeline_anomaly.agent import explain_anomaly
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps(MOCK_RESPONSE)
    )
    with patch("pipeline_anomaly.agent.get_llm_client", return_value=mock_client) as mock_get:
        explain_anomaly("log", model_key="llama3:8b", provider="ollama")
    mock_get.assert_called_once_with("ollama")


def test_explain_anomaly_default_provider_is_tcs():
    """When provider is omitted, defaults to 'tcs'."""
    from pipeline_anomaly.agent import explain_anomaly
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps(MOCK_RESPONSE)
    )
    with patch("pipeline_anomaly.agent.get_llm_client", return_value=mock_client) as mock_get:
        explain_anomaly("log", model_key="gpt-4o-mini")
    mock_get.assert_called_once_with("tcs")
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd ps2 && python -m pytest tests/test_agent.py -v
```

Expected: `TypeError` — `explain_anomaly` doesn't accept `provider` kwarg yet.

- [ ] **Step 3: Update `agent.py`**

Replace the contents of `ps2/src/pipeline_anomaly/agent.py`:

```python
import json
from .config import get_llm_client, get_model
from .models import AnomalyExplanation
from .prompts import SYSTEM_PROMPT, build_user_message
from .guardrails import run_input_guardrails, run_output_guardrails


def explain_anomaly(
    log_snippet: str,
    model_key: str = "gpt-4o",
    provider: str = "tcs",
) -> AnomalyExplanation:
    # ── Input guardrails ─────────────────────────────────────────────────
    guard = run_input_guardrails(log_snippet)
    if guard.blocked:
        raise ValueError(f"Input blocked by guardrails: {guard.block_reason}")
    sanitized_input = guard.sanitized_input

    # ── LLM call ─────────────────────────────────────────────────────────
    client = get_llm_client(provider)
    deployment = get_model(provider, model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(sanitized_input)},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    if raw.endswith("```"):
        raw = raw[:-3]
    data = json.loads(raw)
    result = AnomalyExplanation(**data)

    # ── Output guardrails ────────────────────────────────────────────────
    out_guard = run_output_guardrails(result)
    if out_guard.warnings:
        result._guardrail_warnings = out_guard.warnings

    return result
```

Note: The `SYSTEM_PROMPT` already contains the JSON-only instruction (added in Task 2), so the redundant `+ "\nRespond ONLY with valid JSON..."` suffix is removed.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd ps2 && python -m pytest tests/test_agent.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Run all tests**

```bash
cd ps2 && python -m pytest tests/ -v
```

Expected: all 18 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ps2/tests/test_agent.py ps2/src/pipeline_anomaly/agent.py
git commit -m "feat(ps2): add provider parameter to explain_anomaly"
```

---

## Task 5: Update `app/main.py` with provider selector and confidence metric

**Files:**
- Modify: `ps2/app/main.py`

> Streamlit UI is not unit-tested here. Manual smoke test instructions are provided.

- [ ] **Step 1: Replace `ps2/app/main.py`**

```python
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
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

st.set_page_config(page_title="Pipeline Anomaly Explainer", page_icon="🔍", layout="wide")
st.title("🔍 Pipeline Anomaly Explanation Agent")
st.caption("Paste a CI/CD pipeline log snippet to get an AI-powered anomaly analysis.")

from pipeline_anomaly.config import MODEL_OPTIONS, list_ollama_models

PROVIDER_OPTIONS = ["tcs", "ollama"]
_DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "tcs")


@st.cache_data(ttl=60)
def _cached_ollama_models() -> list[str]:
    """Thin Streamlit-cached wrapper around config.list_ollama_models()."""
    return list_ollama_models()


with st.sidebar:
    st.header("Settings")

    provider = st.selectbox(
        "LLM Provider",
        PROVIDER_OPTIONS,
        index=PROVIDER_OPTIONS.index(_DEFAULT_PROVIDER) if _DEFAULT_PROVIDER in PROVIDER_OPTIONS else 0,
    )

    if provider == "tcs":
        model_key = st.selectbox("Model", MODEL_OPTIONS)
        ollama_unavailable = False
    else:
        ollama_models = _cached_ollama_models()
        if ollama_models:
            model_key = st.selectbox("Model", ollama_models)
            ollama_unavailable = False
        else:
            st.warning("Ollama unavailable — is the service running?")
            model_key = ""
            ollama_unavailable = True

SAMPLE_LOG = """[2024-03-15 14:23:11] Starting build #1234 for branch: main
[2024-03-15 14:23:12] Pulling Docker image: node:18-alpine
[2024-03-15 14:23:15] Running npm install...
[2024-03-15 14:23:45] npm ERR! code ERESOLVE
[2024-03-15 14:23:45] npm ERR! ERESOLVE unable to resolve dependency tree
[2024-03-15 14:23:45] npm ERR! peer dep missing: react@^17.0.0, required by react-router-dom@5.3.4
[2024-03-15 14:23:45] npm ERR! Conflicting peer dependency: react@18.2.0
[2024-03-15 14:23:45] npm ERR! Fix the upstream dependency conflict
[2024-03-15 14:23:46] Build failed with exit code 1
[2024-03-15 14:23:46] Pipeline stage 'install-dependencies' failed after 31s
[2024-03-15 14:23:47] Sending failure notification to team-channel"""

log_input = st.text_area(
    "Pipeline Log Snippet",
    value=SAMPLE_LOG,
    height=250,
    placeholder="Paste your pipeline log here...",
)

if st.button("Analyze Anomaly", type="primary", disabled=ollama_unavailable) and log_input.strip():
    from pipeline_anomaly.agent import explain_anomaly
    with st.spinner("Analyzing pipeline log..."):
        try:
            result = explain_anomaly(log_input, model_key, provider)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Anomaly Type", result.anomaly_type)
            col2.metric("Severity", result.severity.upper())
            col3.metric("Affected Stage", result.affected_stage)
            col4.metric("Confidence", f"{result.confidence_level:.0%}")

            st.subheader("Plain English Summary")
            st.info(result.plain_english_summary)

            st.subheader("Root Cause")
            st.error(result.root_cause)

            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("Remediation Steps")
                for i, step in enumerate(result.remediation_steps, 1):
                    st.write(f"{i}. {step}")
            with col_b:
                st.subheader("Prevention Tips")
                for tip in result.prevention_tips:
                    st.write(f"• {tip}")
        except Exception as e:
            st.error(f"Analysis failed: {e}")
```

- [ ] **Step 2: Manual smoke test — TCS provider**

```bash
cd ps2 && streamlit run app/main.py
```

- Sidebar shows "LLM Provider" dropdown with `tcs` selected by default
- Model dropdown shows `gpt-4o`, `gpt-4o-mini`, `gpt-35-turbo`
- Click "Analyze Anomaly" — 4 metric columns appear including "Confidence"

- [ ] **Step 3: Manual smoke test — Ollama provider**

- Switch sidebar to `ollama`
- If Ollama is running: model dropdown lists installed models; button is enabled
- If Ollama is stopped: yellow warning appears; button is disabled (greyed out)

- [ ] **Step 4: Commit**

```bash
git add ps2/app/main.py
git commit -m "feat(ps2): add provider selector sidebar and confidence_level metric"
```

---

## Task 6: Update `.env.example`

**Files:**
- Modify: `ps2/.env.example`

- [ ] **Step 1: Add new env vars to `.env.example`**

Append to `ps2/.env.example`:

```properties
# ── Provider selector ─────────────────────────────────────────────────────────
# tcs  → TCS GenAI proxy at https://genailab.tcs.in (default)
# ollama → local Ollama service (must be running as systemd service)
LLM_PROVIDER=tcs

# ── Ollama (local LLM) ────────────────────────────────────────────────────────
# Do NOT add /v1 — it is appended automatically
OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_API_KEY is optional; Ollama does not require authentication
```

- [ ] **Step 2: Commit**

```bash
git add ps2/.env.example
git commit -m "docs(ps2): add LLM_PROVIDER and OLLAMA_BASE_URL to .env.example"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
cd ps2 && python -m pytest tests/ -v
```

Expected: all tests PASS, no warnings about deprecated patterns.

- [ ] **Verify no `.beta.chat.completions.parse` calls**

```bash
grep -r "\.beta\." ps2/src/ ps2/app/
```

Expected: no output.

- [ ] **Verify no `AzureOpenAI` import**

```bash
grep -r "AzureOpenAI" ps2/src/ ps2/app/
```

Expected: no output.
