# PS2 — Modular LLM Provider Design

**Date:** 2026-03-25
**Project:** ps2 / Pipeline Anomaly Explainer

---

## Problem

`config.py` hard-codes the TCS GenAI proxy as the only LLM provider. There is no way to run the app against a local LLM (Ollama) without manually editing source files.

---

## Goal

Make the LLM provider selectable via:
1. `.env` — sets the default provider for a session
2. Streamlit sidebar — allows per-session override at runtime

Supported providers: **TCS GenAI proxy** (`https://genailab.tcs.in`) and **Ollama** (local systemd service, default `http://localhost:11434`).

Also add a `confidence_level` field (float 0.0–1.0) to the anomaly explanation output.

---

## Approach

**Provider registry in `config.py`** — a `ProviderConfig` dataclass and a `PROVIDERS` dict. All provider-specific details (base URL, API key env var, SSL flag, model map) live in one place. Updated `get_llm_client(provider)` and `get_model(provider, model_key)` accept the provider name. No new files or subpackages needed.

---

## Architecture

### `ProviderConfig` dataclass (`config.py`)

```python
@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key_env: str      # env var name to read key from; Ollama uses "OLLAMA_API_KEY"
    ssl_verify: bool
    model_map: tuple[tuple[str, str], ...]   # (display_name, deployment_id) pairs; empty for Ollama
    default_model: str
```

`frozen=True` is required so `ProviderConfig` instances are hashable and can be used safely. Because `dict` is not hashable, `model_map` is stored as a `tuple` of `(key, value)` pairs and converted to a dict on access via a property.

### `PROVIDERS` registry (`config.py`)

| Key | `base_url` | `ssl_verify` | Model source |
|-----|-----------|--------------|--------------|
| `tcs` | `https://genailab.tcs.in` | `False` | Static map (3 models) |
| `ollama` | `$OLLAMA_BASE_URL` (default `http://localhost:11434`) | `True` | Dynamic — queried from `/api/tags` at runtime |

**Important:** `OLLAMA_BASE_URL` must **not** include a `/v1` suffix (e.g. use `http://localhost:11434`, not `http://localhost:11434/v1`). The client factory appends `/v1` automatically; a trailing `/v1` in the env var will be stripped before appending to prevent double-suffix.

For Ollama, `model_map` is empty in the registry. `list_ollama_models()` queries the Ollama API at runtime and returns model names directly (e.g. `"llama3:8b"`) — these are the final deployment IDs passed verbatim to the OpenAI client.

### `get_llm_client(provider: str) -> OpenAI` (`config.py`)

- Reads `ProviderConfig` for the given provider
- Reads API key: `api_key = os.environ.get(config.api_key_env) or "ollama"` (Ollama does not require a real key)
- Creates `httpx.Client(verify=config.ssl_verify)`
- Cache key is `(provider, api_key, base_url)` — primitive tuple, not the dataclass
- `@lru_cache(maxsize=None)` — `maxsize=1` is replaced to avoid evicting the first provider's client when switching to the second

### `get_model(provider: str, model_key: str) -> str` (`config.py`)

- For `"tcs"`: looks up the static `model_map`; if `model_key` is not found raises `ValueError(f"Unknown model {model_key!r} for provider {provider!r}. Options: {list(model_map)}")`
- For `"ollama"`: returns `model_key` unchanged (identity lookup — the sidebar passes the deployment ID directly from `list_ollama_models()`, no mapping needed)

---

## Changed Files

### `src/pipeline_anomaly/config.py`
- Add `ProviderConfig` dataclass
- Add `PROVIDERS` registry with `tcs` and `ollama` entries
- Add `list_ollama_models() -> list[str]` — calls `GET {base_url}/api/tags`, returns model name list; catches all exceptions (`Exception`) broadly and returns `[]` on any error (connection refused, timeout, etc.) so the caller always gets a list, never an exception; **no Streamlit decorator** — `config.py` must not import Streamlit
- Update `get_llm_client(provider)` and `get_model(provider, model_key)`
- Keep `MODEL_OPTIONS` as a convenience alias for TCS models (backward compat for existing sidebar code)

### `src/pipeline_anomaly/models.py`
- Add `confidence_level: float = Field(default=0.0, description="Model confidence in this analysis, 0.0–1.0")` to `AnomalyExplanation` — Pydantic default handles the missing-field case without any try/except in `agent.py`
- Add a `field_validator` to normalise out-of-range values: if the LLM returns a value > 1.0 (e.g. `87` instead of `0.87`), divide by 100; clamp to `[0.0, 1.0]`

### `src/pipeline_anomaly/prompts.py`
- Add `confidence_level` to the system prompt's JSON schema instruction, explicitly with the range:
  `"confidence_level": <float between 0.0 and 1.0 — your confidence in this analysis>`
- This ensures the LLM outputs a decimal fraction, not a percentage integer

### `src/pipeline_anomaly/agent.py`
- Signature: `explain_anomaly(log_snippet: str, model_key: str = "gpt-4o", provider: str = "tcs") -> AnomalyExplanation`
- `provider` is keyword-safe (positional order: log_snippet, model_key, provider)
- Pass `provider` to `get_llm_client(provider)` and `get_model(provider, model_key)`

### `app/main.py`
- Sidebar: provider dropdown (default from `LLM_PROVIDER` env var, fallback `"tcs"`)
- Sidebar: model dropdown — TCS uses static list from `MODEL_OPTIONS`; Ollama uses a thin `@st.cache_data(ttl=60)`-decorated wrapper defined in `app/main.py` that calls `list_ollama_models()` from `config.py` — the decorator stays in the UI layer, not in `config.py`
- When `list_ollama_models()` returns `[]`, the sidebar shows a `st.warning("Ollama unavailable — is the service running?")` and the "Analyze Anomaly" button is **disabled** (`st.button(..., disabled=True)`) — no empty model key ever reaches `explain_anomaly()`
- Call: `explain_anomaly(log_input, model_key, provider)` — positional order matches updated signature
- Display `confidence_level` as a 4th metric (shown as percentage, e.g. `87%`)

### `ps2/.env.example`
- Add `LLM_PROVIDER=tcs` and `OLLAMA_BASE_URL=http://localhost:11434`

---

## Data Flow

```
User selects provider + model in sidebar
        ↓
explain_anomaly(log, model_key, provider)
        ↓
get_llm_client(provider)  →  cached OpenAI client
get_model(provider, model_key)  →  deployment ID
        ↓
chat.completions.create(model=deployment_id, ...)
        ↓
AnomalyExplanation (includes confidence_level)
        ↓
Streamlit renders 4 metric columns + details
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Ollama not running | `list_ollama_models()` returns `[]`; sidebar shows "Ollama unavailable" warning |
| Unknown provider key | `get_llm_client()` raises `ValueError` with valid options listed |
| TCS VPN not connected | Existing `ConnectError` surfaces as Streamlit error message (unchanged) |
| `confidence_level` missing from LLM response | Pydantic validation error caught in `agent.py`; returns 0.0 as default |

---

## `.env.example` additions

```properties
LLM_PROVIDER=tcs                          # tcs | ollama
OLLAMA_BASE_URL=http://localhost:11434
```

---

## File Count Clarification

5 Python source files change: `config.py`, `models.py`, `prompts.py`, `agent.py`, `app/main.py`. The `.env.example` is also updated but is not a Python source file.

---

## Out of Scope

- No changes to `mcp_server.py`, `app_mcp.py`, or `chroma_store.py`
- No new files or subpackages
- No changes to guardrails logic
