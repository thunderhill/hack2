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
@dataclass
class ProviderConfig:
    base_url: str
    api_key_env: str      # env var name to read key from
    ssl_verify: bool
    model_map: dict[str, str]   # display_name → deployment_id
    default_model: str
```

### `PROVIDERS` registry (`config.py`)

| Key | `base_url` | `ssl_verify` | Model source |
|-----|-----------|--------------|--------------|
| `tcs` | `https://genailab.tcs.in` | `False` | Static map (3 models) |
| `ollama` | `$OLLAMA_BASE_URL` (default `http://localhost:11434`) | `True` | Dynamic — queried from `/api/tags` |

For Ollama, `model_map` is populated at runtime by calling `GET http://localhost:11434/api/tags`. If Ollama is unreachable, the sidebar shows an error and falls back gracefully.

### `get_llm_client(provider: str) -> OpenAI` (`config.py`)

- Reads `ProviderConfig` for the given provider
- Reads API key from `ProviderConfig.api_key_env` (Ollama uses `"ollama"` as a dummy key if the env var is unset)
- Creates `httpx.Client(verify=ssl_verify)`
- Cache key is `(provider, api_key, base_url)` — replaces the old `(api_key, base_url)` key

### `get_model(provider: str, model_key: str) -> str` (`config.py`)

- Looks up `PROVIDERS[provider].model_map[model_key]`
- For Ollama, model_map is identity (display name == deployment ID)

---

## Changed Files

### `src/pipeline_anomaly/config.py`
- Add `ProviderConfig` dataclass
- Add `PROVIDERS` registry with `tcs` and `ollama` entries
- Add `list_ollama_models() -> list[str]` — calls `/api/tags`, returns model name list
- Update `get_llm_client(provider)` and `get_model(provider, model_key)`
- Keep `MODEL_OPTIONS` as a convenience alias for TCS models (backward compat for existing sidebar code)

### `src/pipeline_anomaly/models.py`
- Add `confidence_level: float` field to `AnomalyExplanation`

### `src/pipeline_anomaly/prompts.py`
- Add `confidence_level` instruction to system prompt JSON spec

### `src/pipeline_anomaly/agent.py`
- Add `provider: str = "tcs"` parameter to `explain_anomaly()`
- Pass `provider` to `get_llm_client()` and `get_model()`

### `app/main.py`
- Sidebar: provider dropdown (default from `LLM_PROVIDER` env var, fallback `"tcs"`)
- Sidebar: model dropdown — TCS uses static list; Ollama calls `list_ollama_models()` with a spinner
- Pass `(model_key, provider)` to `explain_anomaly()`
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

## Out of Scope

- No changes to `mcp_server.py`, `app_mcp.py`, or `chroma_store.py`
- No new files or subpackages
- No changes to guardrails logic
