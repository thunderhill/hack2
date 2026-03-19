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
│  - Calls Azure OpenAI with parse()      │
│  - Returns BuildDiagnosis               │
└──────┬───────────────────┬──────────────┘
       │                   │
       ▼                   ▼
┌────────────┐    ┌────────────────────────┐
│ config.py  │    │ prompts.py             │
│ AzureOpenAI│    │ SYSTEM_PROMPT          │
│ client     │    │ build_user_message()   │
└────────────┘    └────────────────────────┘
       │
       ▼
Azure OpenAI API
(structured output → BuildDiagnosis)
       │
       ▼
┌─────────────────────────────────────────┐
│  src/build_failure/models.py            │
│  BuildDiagnosis + ErrorLocation         │
└─────────────────────────────────────────┘
```

**Data flow:** User pastes build output → UI calls `diagnose_build()` → agent builds prompt (with optional language hint) → Azure OpenAI parses response into `BuildDiagnosis` → UI renders fields.

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
│       ├── config.py              # Azure OpenAI client factory + model map
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
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(build_output, language_hint)},
        ],
        response_format=BuildDiagnosis,
    )
    return response.choices[0].message.parsed
```

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
AZURE_GENAI_API_KEY=your_key_here
AZURE_GENAI_ENDPOINT=https://genailab-maas.services.ai.azure.com
AZURE_GENAI_API_VERSION=2024-08-01-preview
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
os.environ["AZURE_GENAI_API_KEY"] = "your_key"

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
    mock_response.choices[0].message.parsed = mock_diagnosis
    mock_client.return_value.beta.chat.completions.parse.return_value = mock_response

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
  -e AZURE_GENAI_API_KEY=your_key \
  -e AZURE_GENAI_ENDPOINT=https://genailab-maas.services.ai.azure.com \
  ps3-build-failure
```

### Production environment variables

| Variable | Description |
|---|---|
| `AZURE_GENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_GENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_GENAI_API_VERSION` | API version (default: `2024-08-01-preview`) |
