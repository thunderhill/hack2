# PS4 — Quality Inspection Assistant: Developer Guide

## Architecture Overview

```
User (Browser)
     │
     ▼
┌─────────────────────────────────────────┐
│  app/main.py  (Streamlit UI)            │
│  - Renders inspection data textarea     │
│  - Accepts optional product type hint   │
│  - Calls generate_inspection_report()   │
│  - Displays QualityInspectionReport     │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  src/quality_inspection/agent.py        │
│  generate_inspection_report(data, ...)  │
│  - Builds messages from prompts         │
│  - Calls OpenAI with create()            │
│  - Returns QualityInspectionReport      │
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
TCS GenAI Lab API (genailab.tcs.in) (ISO 9001 quality engineer persona)
(structured output → QualityInspectionReport)
       │
       ▼
┌─────────────────────────────────────────┐
│  src/quality_inspection/models.py       │
│  QualityInspectionReport + DefectDetail │
└─────────────────────────────────────────┘
```

---

## Project Structure

```
ps4/
├── app/
│   └── main.py                      # Streamlit app — rendering only
├── src/
│   └── quality_inspection/
│       ├── __init__.py
│       ├── agent.py                 # Single function: generate_inspection_report()
│       ├── config.py                # OpenAI client factory (TCS proxy) + model map
│       ├── models.py                # QualityInspectionReport + DefectDetail
│       └── prompts.py               # System prompt + user message builder
└── pyproject.toml                   # Package: quality-inspection, Python 3.11+
```

---

## Core Components

### `agent.py`

```python
def generate_inspection_report(inspection_data: str, model_key: str = "gpt-4o", product_type: str = "") -> QualityInspectionReport:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(inspection_data, product_type)},
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
    return QualityInspectionReport(**data)
```

Uses `client.chat.completions.create()` with a JSON-only instruction appended to the system prompt. The response is manually parsed from JSON and validated against the Pydantic model. This is required because the TCS GenAI Lab proxy does not support the `.beta.parse()` structured output endpoint.

### `models.py`

```python
class DefectDetail(BaseModel):
    defect_id: str           # Unique ID, e.g., "D001"
    defect_type: str         # dimensional | surface | material | functional | cosmetic
    description: str         # Clear defect description
    severity: str            # critical | major | minor
    affected_component: str  # Which part is affected

class QualityInspectionReport(BaseModel):
    product_id: str                    # Extracted from input
    inspection_date: str               # Extracted or "Not specified"
    overall_quality_status: str        # PASS | FAIL | CONDITIONAL_PASS
    defect_count: int                  # Total defects found
    defects: list[DefectDetail]        # Individual defect catalog
    quality_score: float               # 0.0–100.0
    root_cause_analysis: str           # Probable root causes
    corrective_actions: list[str]      # Immediate actions
    preventive_measures: list[str]     # Long-term prevention
    disposition: str                   # rework | scrap | accept | quarantine
    inspector_notes: str               # Additional observations
```

`DefectDetail` uses an auto-generated `defect_id` (e.g., D001, D002) to allow referencing specific defects in the root cause analysis and corrective actions sections.

### `prompts.py`

The system prompt establishes the AI as a "senior quality engineer with expertise in manufacturing quality control and ISO 9001 standards." This domain framing is important for getting consistent defect classification and disposition recommendations aligned with industry standards.

```python
def build_user_message(inspection_data: str, product_type: str = "") -> str:
    product_context = f"\nProduct type: {product_type}" if product_type else ""
    return f"""Generate a quality inspection report for the following inspection data:{product_context}\n\n--- INSPECTION DATA ---\n{inspection_data}\n--- END DATA ---\n..."""
```

---

## Environment Setup

```bash
cd /path/to/hack2/ps4
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

### Add a new defect type

Change `defect_type` to a `Literal` and add the new category:

```python
from typing import Literal

class DefectDetail(BaseModel):
    defect_type: Literal["dimensional", "surface", "material", "functional", "cosmetic", "assembly", "marking"]
    ...
```

Update `SYSTEM_PROMPT` to mention the new defect type so the LLM classifies correctly.

### Add a quality standard reference

Add a field to `QualityInspectionReport`:

```python
applicable_standards: list[str] = Field(
    description="Applicable quality standards referenced, e.g., ISO 9001, IATF 16949, IPC-A-610"
)
```

Update the system prompt to instruct the AI to reference applicable standards based on the product type.

### Modify quality scoring logic

The quality score is computed by the LLM based on the inspection data and the system prompt's instructions. To enforce a specific scoring formula (e.g., deduct 10 points per critical defect), update `SYSTEM_PROMPT`:

```python
SYSTEM_PROMPT = """...
Quality score calculation:
- Start at 100
- Deduct 10 points per critical defect
- Deduct 5 points per major defect
- Deduct 1 point per minor defect
- Minimum score is 0
"""
```

### Add new disposition types

```python
disposition: str = Field(
    description="Recommended disposition: rework | scrap | accept | quarantine | conditional_release | downgrade"
)
```

---

## Testing

### Test the agent in isolation

```python
import os
os.environ["OPENAI_API_KEY"] = "your_key"

from quality_inspection.agent import generate_inspection_report

data = """
Product ID: WIDGET-001
- 5 units have dimensional deviation: length 10.2mm vs spec 10.0mm ±0.1mm
- 2 units failed tensile test: 450N vs minimum 500N required
"""
report = generate_inspection_report(data, model_key="gpt-4o-mini", product_type="Mechanical widget")
print(report.overall_quality_status)
print(report.quality_score)
for defect in report.defects:
    print(f"{defect.defect_id}: {defect.severity} — {defect.defect_type}")
```

### Unit test with mocks

```python
from unittest.mock import MagicMock, patch
from quality_inspection.models import QualityInspectionReport, DefectDetail

mock_report = QualityInspectionReport(
    product_id="WIDGET-001",
    inspection_date="2024-03-15",
    overall_quality_status="FAIL",
    defect_count=2,
    defects=[
        DefectDetail(defect_id="D001", defect_type="dimensional", description="Length deviation",
                     severity="major", affected_component="body"),
        DefectDetail(defect_id="D002", defect_type="functional", description="Tensile test failure",
                     severity="critical", affected_component="joint"),
    ],
    quality_score=62.0,
    root_cause_analysis="Process temperature exceeded during manufacturing",
    corrective_actions=["Quarantine batch", "Re-inspect remaining units"],
    preventive_measures=["Calibrate temperature sensors weekly"],
    disposition="quarantine",
    inspector_notes="Batch shows systematic dimensional issues",
)

with patch("quality_inspection.agent.get_llm_client") as mock_client:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = mock_report.model_dump_json()
    mock_client.return_value.chat.completions.create.return_value = mock_response

    from quality_inspection.agent import generate_inspection_report
    result = generate_inspection_report("any inspection data")
    assert result.overall_quality_status == "FAIL"
    assert len(result.defects) == 2
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
docker build -t ps4-quality-inspection .
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  -e OPENAI_BASE_URL=https://genailab.tcs.in \
  ps4-quality-inspection
```

### Production environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | TCS GenAI Lab API key |
| `OPENAI_BASE_URL` | TCS GenAI Lab proxy URL |
| `PYTHONHTTPSVERIFY` | Set to `0` to bypass self-signed cert |
