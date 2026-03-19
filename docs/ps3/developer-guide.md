# PS3 — Build Failure Diagnosis: Developer Guide

## Architecture Overview

```
User (Browser)
     │
     ▼
┌─────────────────────────────────────────┐
│  app/main.py  (Streamlit UI)            │
│  - Renders build output textarea        │
│  - Accepts optional language hint       │
│  - Calls diagnose_build()               │
│  - Displays BuildDiagnosis fields       │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  src/build_failure/agent.py             │
│  diagnose_build(output, model, hint)    │
│  - Builds messages from prompts         │
│  - Calls OpenAI with create()            │
│  - Returns BuildDiagnosis               │
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
(structured output → BuildDiagnosis)
       │
       ▼
┌─────────────────────────────────────────┐
│  src/build_failure/models.py            │
│  BuildDiagnosis + ErrorLocation         │
└─────────────────────────────────────────┘
```

**Data flow:** User pastes build output → UI calls `diagnose_build()` → agent builds prompt (with optional language hint) → TCS GenAI Lab API parses response into `BuildDiagnosis` → UI renders fields.

---

## Project Structure

```
ps3/
├── app/
│   └── main.py                    # Streamlit app — UI and rendering only
├── src/
│   └── build_failure/
│       ├── __init__.py
│       ├── agent.py               # Single function: diagnose_build()
│       ├── config.py              # OpenAI client factory (TCS proxy) + model map
│       ├── models.py              # BuildDiagnosis + ErrorLocation Pydantic models
│       └── prompts.py             # System prompt + user message builder
└── pyproject.toml                 # Package: build-failure, Python 3.11+
```

---

## Core Components

### `agent.py`

```python
def diagnose_build(build_output: str, model_key: str = "gpt-4o", language_hint: str = "") -> BuildDiagnosis:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(build_output, language_hint)},
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
    return BuildDiagnosis(**data)
```

Uses `client.chat.completions.create()` with a JSON-only instruction appended to the system prompt. The response is manually parsed from JSON and validated against the Pydantic model. This is required because the TCS GenAI Lab proxy does not support the `.beta.parse()` structured output endpoint.

The `language_hint` parameter is forwarded to `build_user_message()` and prepended to the user prompt when provided. It helps the LLM resolve ambiguous error messages (e.g., a stack trace that could be Java or Kotlin).

### `models.py`

Two nested Pydantic models:

```python
class ErrorLocation(BaseModel):
    file_path: str     # File where error occurred, or "unknown"
    line_number: str   # Line number, or "unknown"
    column: str        # Column number, or "unknown"

class BuildDiagnosis(BaseModel):
    build_tool: str         # maven | gradle | npm | pip | cargo | make | other
    language: str           # java | python | javascript | rust | c++ | other
    error_type: str         # compilation | dependency | configuration | linking | syntax | runtime
    error_message: str      # Core error message extracted from output
    error_location: ErrorLocation
    diagnosis: str          # Why the build failed
    fix_explanation: str    # How to fix it
    code_fix: str           # Concrete code/config change, or "N/A"
    estimated_fix_time: str # minutes | hours | days
```

`ErrorLocation` is an embedded object — the LLM populates it as a nested JSON structure within `BuildDiagnosis`.

### `prompts.py`

```python
def build_user_message(build_output: str, language_hint: str = "") -> str:
    hint_text = f"\nLanguage/framework hint: {language_hint}" if language_hint else ""
    return f"""Diagnose the following build failure:{hint_text}\n\n--- BUILD OUTPUT ---\n{build_output}\n--- END OUTPUT ---\n..."""
```

The language hint is injected between the instruction line and the build output delimiter. This placement gives it context without overriding the LLM's own detection from the output.

### `config.py`

Identical to PS2's config. See PS2 developer guide for detailed explanation of the `lru_cache` client pattern and environment variable handling.

---

## Environment Setup

```bash
cd /path/to/hack2/ps3
python -m venv .venv
source .venv/bin/activate
pip install -e .

cat > .env << 'EOF'
OPENAI_API_KEY=your-hackathon-api-key-here
OPENAI_BASE_URL=https://genailab.tcs.in
PYTHONHTTPSVERIFY=0
REQUESTS_CA_BUNDLE=
CURL_CA_BUNDLE=
EOF

streamlit run app/main.py
```

---

## Extending the App

### Add a new build tool

The `build_tool` field is a free-form string — the LLM detects it from the output. To constrain it to known values, change the field to a `Literal` type:

```python
from typing import Literal

class BuildDiagnosis(BaseModel):
    build_tool: Literal["maven", "gradle", "npm", "pip", "cargo", "make", "bazel", "other"]
    ...
```

Also update `SYSTEM_PROMPT` in `prompts.py` to list the new tool name.

### Add a new output field

1. Add to `BuildDiagnosis` in `models.py`:
   ```python
   affected_files: list[str] = Field(description="List of files that need to be changed to fix the issue")
   ```

2. Update `SYSTEM_PROMPT` to request it:
   ```python
   SYSTEM_PROMPT = """...
   5. List all files that need to be modified to fix the issue
   """
   ```

3. Render in `app/main.py`:
   ```python
   if result.affected_files:
       st.subheader("Files to Modify")
       for f in result.affected_files:
           st.code(f)
   ```

### Change error type classification

Edit the `error_type` field description in `models.py`:
```python
error_type: str = Field(
    description="Type of error: compilation | dependency | configuration | linking | syntax | runtime | test | packaging"
)
```

---

## Testing

### Test the agent in isolation

```python
import os
os.environ["OPENAI_API_KEY"] = "your_key"

from build_failure.agent import diagnose_build

output = """
[ERROR] COMPILATION ERROR :
[ERROR] /src/UserService.java:[45,32] error: cannot find symbol
"""
result = diagnose_build(output, model_key="gpt-4o-mini", language_hint="Java Spring")
print(result.build_tool)       # maven
print(result.error_location.file_path)  # /src/UserService.java
print(result.code_fix)
```

### Unit test with mocks

```python
from unittest.mock import MagicMock, patch
from build_failure.models import BuildDiagnosis, ErrorLocation

mock_diagnosis = BuildDiagnosis(
    build_tool="maven",
    language="java",
    error_type="compilation",
    error_message="cannot find symbol: method getUserById(long)",
    error_location=ErrorLocation(file_path="/src/UserService.java", line_number="45", column="32"),
    diagnosis="Method getUserById(long) does not exist on UserRepository",
    fix_explanation="Add the missing method to UserRepository interface",
    code_fix="User getUserById(Long id);",
    estimated_fix_time="minutes",
)

with patch("build_failure.agent.get_llm_client") as mock_client:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = mock_diagnosis.model_dump_json()
    mock_client.return_value.chat.completions.create.return_value = mock_response

    from build_failure.agent import diagnose_build
    result = diagnose_build("any build output")
    assert result.build_tool == "maven"
    assert result.error_location.line_number == "45"
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
docker build -t ps3-build-failure .
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  -e OPENAI_BASE_URL=https://genailab.tcs.in \
  ps3-build-failure
```

### Production environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | TCS GenAI Lab API key |
| `OPENAI_BASE_URL` | TCS GenAI Lab proxy URL |
| `PYTHONHTTPSVERIFY` | Set to `0` to bypass self-signed cert |
