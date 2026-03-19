# PS8 — DevOps Incident Report Generator: Developer Guide

## Architecture Overview

```
User (Browser)
     │
     ▼
┌──────────────────────────────────────────────┐
│  app/main.py  (Streamlit UI)                 │
│  - Incident notes textarea                   │
│  - Optional service name in sidebar          │
│  - Calls generate_incident_report()          │
│  - Renders 4-tab report view                 │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  src/incident_report/agent.py                │
│  generate_incident_report(notes, model, svc) │
│  - Builds messages from prompts              │
│  - Calls Azure OpenAI with parse()           │
│  - Returns IncidentReport                    │
└──────┬───────────────────┬────────────────────┘
       │                   │
       ▼                   ▼
┌────────────┐    ┌──────────────────────────────┐
│ config.py  │    │ prompts.py                   │
│ OpenAI     │    │ SYSTEM_PROMPT (SRE persona,  │
│ client     │    │  Google SRE + ITIL practices)│
└────────────┘    └──────────────────────────────┘
       │
       ▼
TCS GenAI Lab API (genailab.tcs.in)
(structured output → IncidentReport)
       │
       ▼
┌────────────────────────────────────────────────┐
│  src/incident_report/models.py                 │
│  IncidentReport + TimelineEvent + ActionItem   │
└────────────────────────────────────────────────┘
```

---

## Project Structure

```
ps8/
├── app/
│   └── main.py                       # Streamlit app — 4-tab report rendering
├── src/
│   └── incident_report/
│       ├── __init__.py
│       ├── agent.py                  # Single function: generate_incident_report()
│       ├── config.py                 # OpenAI client factory (TCS proxy) + model map
│       ├── models.py                 # IncidentReport + TimelineEvent + ActionItem
│       └── prompts.py                # System prompt + user message builder
└── pyproject.toml                    # Package: incident-report, Python 3.11+
```

---

## Core Components

### `agent.py`

```python
def generate_incident_report(incident_notes: str, model_key: str = "gpt-4o", service_name: str = "") -> IncidentReport:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(incident_notes, service_name)},
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
    return IncidentReport(**data)
```

Uses `client.chat.completions.create()` with a JSON-only instruction appended to the system prompt. The response is manually parsed from JSON and validated against the Pydantic model. This is required because the TCS GenAI Lab proxy does not support the `.beta.parse()` structured output endpoint.

### `models.py`

Three Pydantic models:

```python
class TimelineEvent(BaseModel):
    timestamp: str   # Event timestamp (extracted from notes)
    event: str       # What happened
    actor: str       # system | engineer | automated

class ActionItem(BaseModel):
    action: str      # Specific action to take
    owner: str       # Team or role responsible
    priority: str    # P1 | P2 | P3
    due_date: str    # Target completion date

class IncidentReport(BaseModel):
    incident_id: str              # Extracted or generated (e.g., "INC-2024-0315")
    title: str                    # Concise incident title
    severity: str                 # SEV1 | SEV2 | SEV3 | SEV4
    status: str                   # resolved | monitoring | ongoing
    incident_start: str           # When the incident started
    incident_end: str             # When resolved
    total_duration: str           # Full duration
    time_to_detect: str           # Start to first alert
    time_to_resolve: str          # Detection to resolution
    affected_services: list[str]  # Affected services/systems
    customer_impact: str          # User/customer impact description
    users_affected: str           # Estimated affected users
    executive_summary: str        # 2–3 sentence summary
    timeline: list[TimelineEvent] # Chronological events
    root_cause: str               # Root cause (5-why methodology)
    contributing_factors: list[str]
    what_went_well: list[str]
    what_went_wrong: list[str]
    action_items: list[ActionItem]
    lessons_learned: str
```

`IncidentReport` is the largest Pydantic model in the PS projects — 19 fields across three nested types. The OpenAI structured output API handles this reliably because all fields have clear `Field(description=...)` annotations.

### `prompts.py`

The system prompt is the most domain-specific in the PS suite:

```python
SYSTEM_PROMPT = """You are a senior site reliability engineer (SRE) expert in writing post-incident reports (PIRs).
Given an incident timeline and notes, you write a professional, blameless post-incident report that:
1. Accurately reconstructs the timeline from available information
2. Identifies root cause using 5-why methodology
3. Assesses customer impact honestly
4. Highlights what went well and what needs improvement
5. Creates specific, actionable follow-up items with owners and deadlines
6. Maintains a blameless, learning-focused tone

Follow Google SRE and ITIL incident management best practices."""
```

Key design choices:
- **Blameless tone**: The AI is instructed not to assign individual blame, producing reports appropriate for sharing widely
- **5-why methodology**: Root cause analysis follows a structured approach
- **Google SRE + ITIL**: Domain framing ensures industry-standard terminology (SEV levels, TTD, TTR)

---

## Environment Setup

```bash
cd /path/to/hack2/ps8
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

### Add new severity levels

```python
from typing import Literal

class IncidentReport(BaseModel):
    severity: Literal["SEV0", "SEV1", "SEV2", "SEV3", "SEV4"]
    ...
```

Update the severity icon map in `app/main.py`:
```python
sev_icon = {"SEV0": "⚫", "SEV1": "🔴", "SEV2": "🟠", "SEV3": "🟡", "SEV4": "🟢"}.get(report.severity, "⚪")
```

### Add MTTR/MTTD metrics tracking

After generating the report, persist metrics to a database for trend analysis:

```python
import sqlite3
from datetime import datetime

def track_metrics(report: IncidentReport):
    conn = sqlite3.connect("incidents.db")
    conn.execute("""
        INSERT INTO incident_metrics (incident_id, severity, time_to_detect, time_to_resolve, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (report.incident_id, report.severity, report.time_to_detect, report.time_to_resolve, datetime.now()))
    conn.commit()
```

### Export to Confluence

```python
import requests

def export_to_confluence(report: IncidentReport, confluence_url: str, auth: tuple):
    content = f"""
    <h1>{report.title}</h1>
    <p><strong>Severity:</strong> {report.severity} | <strong>Duration:</strong> {report.total_duration}</p>
    <h2>Executive Summary</h2>
    <p>{report.executive_summary}</p>
    <h2>Root Cause</h2>
    <p>{report.root_cause}</p>
    """
    requests.post(f"{confluence_url}/rest/api/content", json={
        "type": "page",
        "title": f"PIR: {report.title}",
        "body": {"storage": {"value": content, "representation": "storage"}},
    }, auth=auth)
```

### Integrate with PagerDuty for auto-import

```python
import pdpyras

def import_from_pagerduty(incident_id: str, api_token: str) -> str:
    session = pdpyras.APISession(api_token)
    incident = session.rget(f"/incidents/{incident_id}")
    log_entries = session.list_all("log_entries", params={"incident_id": incident_id})

    notes = f"Incident: {incident['title']}\n"
    notes += f"Started: {incident['created_at']}\n\n"
    for entry in log_entries:
        notes += f"{entry['created_at']} - {entry['summary']}\n"
    return notes
```

---

## Testing

### Test the agent in isolation

```python
import os
os.environ["OPENAI_API_KEY"] = "your_key"

from incident_report.agent import generate_incident_report

notes = """
14:32 - PagerDuty alert: Payment API error rate >5%
14:38 - DB connection errors identified in logs
14:45 - Root cause: DB connection pool changed from 100 to 10 (config typo)
14:48 - Rolled back deployment
14:52 - Error rate normal
Impact: 4,200 failed transactions, 127 support tickets
"""
report = generate_incident_report(notes, model_key="gpt-4o-mini", service_name="Payment API")
print(report.severity)
print(report.root_cause)
print(f"Action items: {len(report.action_items)}")
```

### Unit test with mocks

```python
from unittest.mock import MagicMock, patch
from incident_report.models import IncidentReport, TimelineEvent, ActionItem

mock_report = IncidentReport(
    incident_id="INC-2024-0315",
    title="Payment API Connection Pool Exhaustion",
    severity="SEV2",
    status="resolved",
    incident_start="14:20",
    incident_end="14:52",
    total_duration="32 minutes",
    time_to_detect="12 minutes",
    time_to_resolve="20 minutes",
    affected_services=["Payment API", "Checkout Service"],
    customer_impact="Payment processing failed for ~23 minutes",
    users_affected="~4,200 transactions",
    executive_summary="A misconfigured DB connection pool caused Payment API failures for 32 minutes.",
    timeline=[TimelineEvent(timestamp="14:32", event="PagerDuty alert fired", actor="system")],
    root_cause="Deployment at 14:20 changed DB connection pool from 100 to 10 due to config typo",
    contributing_factors=["No automated config validation", "Missing runbook for connection pool issues"],
    what_went_well=["Alert fired quickly", "DB team responded promptly"],
    what_went_wrong=["13 minutes to identify root cause", "No runbook existed"],
    action_items=[ActionItem(action="Add config validation to deployment pipeline",
                             owner="Platform Team", priority="P1", due_date="2024-03-22")],
    lessons_learned="Config changes need automated validation before deployment.",
)

with patch("incident_report.agent.get_llm_client") as mock_client:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = mock_report.model_dump_json()
    mock_client.return_value.chat.completions.create.return_value = mock_response

    from incident_report.agent import generate_incident_report
    result = generate_incident_report("any incident notes")
    assert result.severity == "SEV2"
    assert len(result.action_items) == 1
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
docker build -t ps8-incident-report .
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  -e OPENAI_BASE_URL=https://genailab.tcs.in \
  ps8-incident-report
```

### Production environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | TCS GenAI Lab API key |
| `OPENAI_BASE_URL` | TCS GenAI Lab proxy URL |
| `PYTHONHTTPSVERIFY` | Set to `0` to bypass self-signed cert |
