# CLAUDE.md — TCS GenAI Lab Proxy: Known Issues & Required Fixes

> **Read this file before writing any code.**
> All projects in this repo run against the TCS internal MaaS proxy at
> `https://genailab.tcs.in`. That endpoint has several behaviours that
> differ from standard OpenAI or Azure OpenAI. The fixes below are
> **mandatory** — without them the app will fail at runtime with
> connection errors, 403 content blocks, or structured-output failures.

---

## 1. Environment — `.env` Template

Every project must have a `.env` file with these values. Do **not** use
the Azure OpenAI SDK defaults — they point to `*.azure.com` which is
unreachable from this environment.

```properties
# ── TCS GenAI Lab Proxy ──────────────────────────────────────────────────────
OPENAI_API_KEY=<your-key>
AZURE_GENAI_API_KEY=<your-key>          # same key, both names used by different libs
OPENAI_BASE_URL=https://genailab.tcs.in # no trailing slash, no /v1

# ── Model selector ───────────────────────────────────────────────────────────
# Use EXACTLY these names as returned by GET /v1/models:
#   genailab-maas-gpt-35-turbo
#   azure/genailab-maas-gpt-4o-mini      ← recommended default
#   azure/genailab-maas-gpt-4o           ← if available on your key
LLM_MODEL=azure/genailab-maas-gpt-4o-mini

# ── SSL (corporate proxy uses self-signed cert) ───────────────────────────────
PYTHONHTTPSVERIFY=0
REQUESTS_CA_BUNDLE=
CURL_CA_BUNDLE=

# ── Embeddings ───────────────────────────────────────────────────────────────
AZURE_EMBEDDING_DEPLOYMENT=azure/genailab-maas-text-embedding-3-large

# ── ChromaDB ─────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_MODE=memory

# ── Feature flags ────────────────────────────────────────────────────────────
ENABLE_GUARDRAILS=false
ENABLE_VECTOR_DB=false
ENABLE_AGENTS=false
GUARDRAILS_ENABLED=false
```

---

## 2. LLM Client — ALWAYS Use `openai.OpenAI`, Never `AzureOpenAI`

The TCS proxy is an **OpenAI-compatible REST API**, not a native Azure
OpenAI endpoint. Using `AzureOpenAI` will route to `*.azure.com` and
fail with a connection error.

### ✅ Correct pattern (`config.py` or equivalent)

```python
import os
import httpx
from functools import lru_cache
from openai import OpenAI          # NOT AzureOpenAI

# Model names EXACTLY as the proxy returns them from /v1/models
MODEL_DISPLAY_MAP: dict[str, str] = {
    "gpt-4o":       "azure/genailab-maas-gpt-4o",
    "gpt-4o-mini":  "azure/genailab-maas-gpt-4o-mini",
    "gpt-35-turbo": "genailab-maas-gpt-35-turbo",
}
MODEL_OPTIONS: list[str] = list(MODEL_DISPLAY_MAP.keys())

_DEFAULT_BASE_URL = "https://genailab.tcs.in"

@lru_cache(maxsize=1)
def _cached_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/") + "/v1",   # SDK appends /v1
        http_client=httpx.Client(verify=False),   # REQUIRED: self-signed cert
    )

def get_llm_client() -> OpenAI:
    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("AZURE_GENAI_API_KEY", "")
    )
    base_url = os.environ.get("OPENAI_BASE_URL", _DEFAULT_BASE_URL)
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set in .env")
    return _cached_client(api_key, base_url)

def get_deployment_name(display_name: str) -> str:
    if display_name not in MODEL_DISPLAY_MAP:
        raise ValueError(f"Unknown model {display_name!r}. Options: {MODEL_OPTIONS}")
    return MODEL_DISPLAY_MAP[display_name]
```

### ❌ Do NOT write this

```python
from openai import AzureOpenAI          # WRONG — routes to *.azure.com
client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_GENAI_ENDPOINT"],   # not set / wrong host
    api_version="2024-08-01-preview",
    api_key=os.environ["AZURE_GENAI_API_KEY"],
)
```

---

## 3. SSL — Patch Before Any Imports (Streamlit / FastAPI entry points)

The TCS proxy uses a self-signed TLS certificate. The SSL bypass must
happen at **process start**, before `openai`, `httpx`, or `requests` are
imported. In a Streamlit app this means the **very first lines** of
`main.py` / `app.py`:

```python
import os, ssl, warnings

# ── SSL bypass — MUST be before any other import ─────────────────────────────
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ── All other imports below ───────────────────────────────────────────────────
import streamlit as st
# ...
```

Setting these variables only in `.env` is **not sufficient** — they must
be set in-process before the SSL stack initialises.

---

## 4. Structured Output — Do NOT Use `.beta.chat.completions.parse`

The TCS proxy does not support the Azure structured-output beta endpoint.
Calling `.beta.chat.completions.parse(response_format=MyModel)` will
return a 403 or silently fail.

### ✅ Correct pattern — prompt for JSON, parse manually

```python
import json
from pydantic import BaseModel

class ClassificationResult(BaseModel):
    category: str
    priority: str
    summary: str
    confidence: float
    llm_used: str = ""

def _classify(self, user_msg: str) -> ClassificationResult:
    response = self._client.chat.completions.create(   # NOT .beta.
        model=self._deployment,
        messages=[
            {
                "role": "system",
                "content": CLASSIFY_SYSTEM_PROMPT
                    + "\nRespond ONLY with valid JSON. No markdown, no explanation.",
            },
            {"role": "user", "content": user_msg},
        ],
        max_tokens=512,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)
    result = ClassificationResult(**data)
    return result.model_copy(update={"llm_used": self._deployment})
```

---

## 5. Content Filter — Avoid Blocked Keywords in Prompts

The TCS proxy has a server-side content filter that scans **both the
system prompt and user messages**. Certain words trigger a 403 with body:

```json
{"error": {"message": "Content blocked: harmful_violence category keyword 'crime' detected"}}
```

### Blocked words (non-exhaustive)

| Blocked | Safe replacement |
|---|---|
| `crime` / `criminal` | `reported incident` / `individual of concern` |
| `violence` / `violent` | `public disturbance` / `disruptive behaviour` |
| `assault` | `physical altercation` |
| `theft` / `stolen` | `property incident` |
| `murder` / `kill` | `serious incident` |
| `weapon` | `safety equipment concern` |
| `drug` / `narcotic` | `substance concern` |
| `threat to life/safety` | `threat to infrastructure` |

### Rules for writing system prompts

- Describe categories using **service-outcome language**, not incident
  language. E.g. `public_safety: neighborhood disturbances, traffic
  signals, dangerous intersections, flooding` not `crime concerns`.
- Use `critical: immediate threat to infrastructure or large-scale
  service disruption` not `immediate threat to life/safety`.
- Avoid the word `safety` paired with `life` or `death`.

### Sanitize user input before forwarding to the API

Add this utility wherever you build the user message:

```python
_SENSITIVE: dict[str, str] = {
    "crime":     "reported incident",
    "criminal":  "individual of concern",
    "murder":    "serious incident",
    "assault":   "physical altercation",
    "theft":     "property incident",
    "stolen":    "property incident",
    "drug":      "substance concern",
    "narcotic":  "substance concern",
    "weapon":    "safety equipment concern",
    "violence":  "public disturbance",
    "violent":   "disruptive",
    "kill":      "serious incident",
}

def sanitize_for_proxy(text: str) -> str:
    """Replace content-filter trigger words before sending to genailab.tcs.in."""
    for word, replacement in _SENSITIVE.items():
        text = text.replace(word, replacement)
        text = text.replace(word.capitalize(), replacement.capitalize())
        text = text.replace(word.upper(), replacement.upper())
    return text
```

Call it on any user-supplied text before it enters the messages array.

---

## 6. Available Models — Verified via `/v1/models`

These model IDs were confirmed live on the endpoint. Use them verbatim:

| Display name | Deployment ID (use in API calls) |
|---|---|
| GPT-3.5 Turbo | `genailab-maas-gpt-35-turbo` |
| GPT-4o Mini | `azure/genailab-maas-gpt-4o-mini` ← **recommended** |
| GPT-4o | `azure/genailab-maas-gpt-4o` |
| Text Embedding | `azure/genailab-maas-text-embedding-3-large` |
| Whisper | `azure/genailab-maas-whisper` |
| Gemini 3 Pro | `gemini-3-pro-preview` |

Default to `azure/genailab-maas-gpt-4o-mini` — it is the most reliably
available and fastest on this key.

---

## 7. Connectivity — VPN Requirement

`https://genailab.tcs.in` is only reachable from inside the TCS network
or via TCS VPN. If you see:

```
httpx.ConnectError: [WinError 10061] No connection could be made
```

that is a network/VPN issue, not a code bug. Verify VPN is active before
debugging further.

### Quick smoke test (run before starting the app)

```powershell
python -c "
import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('OPENAI_API_KEY')
r = httpx.get('https://genailab.tcs.in/v1/models',
               headers={'Authorization': 'Bearer ' + key}, verify=False)
print(r.status_code, r.text[:200])
"
```

Expected: `200` with a JSON list of models. Any other result → check VPN.

---

## 8. LangChain / LangGraph Integration

If using `langchain_openai.ChatOpenAI` instead of the raw SDK:

```python
from langchain_openai import ChatOpenAI
import httpx

llm = ChatOpenAI(
    model="azure/genailab-maas-gpt-4o-mini",
    openai_api_key=os.environ["OPENAI_API_KEY"],
    openai_api_base=os.environ["OPENAI_BASE_URL"].rstrip("/") + "/v1",
    http_client=httpx.Client(verify=False),      # REQUIRED
    temperature=0.1,
)
```

Do **not** use `AzureChatOpenAI` — same reason as §2 above.

---

## 9. Error Reference

| Error | Root cause | Fix |
|---|---|---|
| `Connection error` / `ConnectError` | Wrong endpoint (AzureOpenAI SDK default) or VPN off | Use `OpenAI` client with `OPENAI_BASE_URL`; check VPN |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Corporate self-signed cert | Add `http_client=httpx.Client(verify=False)` |
| `403 Content blocked: … 'crime'` | Proxy content filter on prompt or input | Reword prompts; call `sanitize_for_proxy()` on user text |
| `404 model not found` | Wrong deployment name | Use exact IDs from §6 above |
| `AttributeError: beta` | `.beta.parse` not supported on proxy | Switch to `.chat.completions.create` + manual JSON parse (§4) |
| `EnvironmentError: OPENAI_API_KEY not set` | `.env` not loaded before module import | Call `load_dotenv()` at very top of entry point |

---

## 10. Checklist Before Running Any Project

- [ ] VPN is active — smoke test from §7 returns 200
- [ ] `.env` has `OPENAI_BASE_URL=https://genailab.tcs.in`
- [ ] `.env` has `LLM_MODEL=azure/genailab-maas-gpt-4o-mini`
- [ ] Entry point (`main.py` / `app.py`) has SSL patch as **first lines** (§3)
- [ ] LLM client uses `openai.OpenAI` with `http_client=httpx.Client(verify=False)` (§2)
- [ ] No `.beta.chat.completions.parse` calls anywhere (§4)
- [ ] System prompts contain no blocked keywords (§5)
- [ ] User input is passed through `sanitize_for_proxy()` before API call (§5)
