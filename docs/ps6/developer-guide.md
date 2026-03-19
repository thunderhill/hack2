# PS6 — Capacity Planning Advisor: Developer Guide

## Architecture Overview

```
User (Browser)
     │
     ▼
┌──────────────────────────────────────────────┐
│  app/main.py  (Streamlit UI)                 │
│  - Renders metrics textarea                  │
│  - Accepts growth projection + SLA in sidebar│
│  - Calls generate_capacity_plan()            │
│  - Displays CapacityPlan fields              │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  src/capacity_planning/agent.py              │
│  generate_capacity_plan(metrics, model, ...) │
│  - Builds messages from prompts              │
│  - Calls Azure OpenAI with parse()           │
│  - Returns CapacityPlan                      │
└──────┬───────────────────┬────────────────────┘
       │                   │
       ▼                   ▼
┌────────────┐    ┌──────────────────────────────┐
│ config.py  │    │ prompts.py                   │
│ OpenAI     │    │ SYSTEM_PROMPT                │
│ client     │    │ build_user_message()         │
└────────────┘    │ (combines metrics + growth + │
                  │  SLA into one message)       │
                  └──────────────────────────────┘
       │
       ▼
TCS GenAI Lab API (genailab.tcs.in)
(structured output → CapacityPlan)
       │
       ▼
┌─────────────────────────────────────────────┐
│  src/capacity_planning/models.py            │
│  CapacityPlan + ResourceRecommendation      │
└─────────────────────────────────────────────┘
```

---

## Project Structure

```
ps6/
├── app/
│   └── main.py                       # Streamlit app — rendering only
├── src/
│   └── capacity_planning/
│       ├── __init__.py
│       ├── agent.py                  # Single function: generate_capacity_plan()
│       ├── config.py                 # OpenAI client factory (TCS proxy) + model map
│       ├── models.py                 # CapacityPlan + ResourceRecommendation
│       └── prompts.py                # System prompt + multi-context message builder
└── pyproject.toml                    # Package: capacity-planning, Python 3.11+
```

---

## Core Components

### `agent.py`

```python
def generate_capacity_plan(
    metrics_data: str,
    model_key: str = "gpt-4o",
    growth_projection: str = "",
    sla_requirements: str = ""
) -> CapacityPlan:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(metrics_data, growth_projection, sla_requirements)},
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
    return CapacityPlan(**data)
```

Uses `client.chat.completions.create()` with a JSON-only instruction appended to the system prompt. The response is manually parsed from JSON and validated against the Pydantic model. This is required because the TCS GenAI Lab proxy does not support the `.beta.parse()` structured output endpoint.

### `models.py`

```python
class ResourceRecommendation(BaseModel):
    resource_type: str          # compute | memory | storage | network | database
    current_state: str          # Current configuration description
    recommended_state: str      # What to change to
    urgency: str                # immediate | within_month | within_quarter | planned
    estimated_cost_impact: str  # e.g., "+$500/month"

class CapacityPlan(BaseModel):
    assessment_period: str                        # Timeframe assessed
    capacity_risk_level: str                      # critical | high | medium | low
    bottlenecks: list[str]                        # Current constraints
    recommendations: list[ResourceRecommendation] # Per-resource recommendations
    scaling_strategy: str                         # vertical | horizontal | hybrid | serverless
    timeline: str                                 # Implementation timeline
    total_cost_estimate: str                      # Total monthly cost of changes
    risk_if_not_acted: str                        # Consequences of inaction
    optimization_opportunities: list[str]         # Cost reduction suggestions
    executive_summary: str                        # 2–3 sentence summary
```

### `prompts.py`

The `build_user_message()` function is the most complex message builder across the PS projects — it conditionally assembles multiple context blocks:

```python
def build_user_message(metrics_data: str, growth_projection: str = "", sla_requirements: str = "") -> str:
    context_parts = [f"--- CURRENT METRICS ---\n{metrics_data}\n--- END METRICS ---"]
    if growth_projection:
        context_parts.append(f"\nGrowth projection: {growth_projection}")
    if sla_requirements:
        context_parts.append(f"\nSLA requirements: {sla_requirements}")
    return "\n".join(context_parts) + "\n\nProvide a comprehensive capacity plan..."
```

Optional parameters are only included when non-empty, keeping the prompt clean and avoiding "no growth projection provided" as context.

---

## Environment Setup

```bash
cd /path/to/hack2/ps6
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

### Add new resource types

```python
class ResourceRecommendation(BaseModel):
    resource_type: str = Field(
        description="Resource type: compute | memory | storage | network | database | cdn | messaging | container_orchestration"
    )
    ...
```

Update `SYSTEM_PROMPT` to list the new resource types.

### Integrate with AWS Cost Explorer for live metrics

Replace the manual metrics textarea with live data:

```python
import boto3

def get_aws_metrics() -> str:
    ce = boto3.client("ce", region_name="us-east-1")
    # Fetch last 30 days of costs by service
    response = ce.get_cost_and_usage(
        TimePeriod={"Start": "2024-02-15", "End": "2024-03-15"},
        Granularity="MONTHLY",
        Metrics=["BlendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    # Format into text for the prompt
    ...
    return formatted_metrics
```

Then pre-populate the textarea with live data instead of a static sample.

### Add a cost projection chart

After getting the plan, render a bar chart of current vs. recommended costs:

```python
import streamlit as st
import pandas as pd

def render_cost_chart(plan: CapacityPlan):
    data = []
    for rec in plan.recommendations:
        # Parse cost impact strings like "+$500/month"
        data.append({"Resource": rec.resource_type, "Impact": rec.estimated_cost_impact})
    df = pd.DataFrame(data)
    st.bar_chart(df.set_index("Resource"))
```

---

## Testing

### Test the agent in isolation

```python
import os
os.environ["OPENAI_API_KEY"] = "your_key"

from capacity_planning.agent import generate_capacity_plan

metrics = """
Web tier: 4x m5.large — Avg CPU: 78%, Peak: 94%
Database: db.r5.2xlarge — CPU: 82% avg, 98% peak
"""
plan = generate_capacity_plan(
    metrics,
    model_key="gpt-4o-mini",
    growth_projection="30% traffic growth in Q2",
    sla_requirements="99.9% uptime"
)
print(plan.capacity_risk_level)
print(plan.scaling_strategy)
for rec in plan.recommendations:
    print(f"{rec.resource_type}: {rec.urgency} | {rec.estimated_cost_impact}")
```

### Unit test with mocks

```python
from unittest.mock import MagicMock, patch
from capacity_planning.models import CapacityPlan, ResourceRecommendation

mock_plan = CapacityPlan(
    assessment_period="March 2024",
    capacity_risk_level="high",
    bottlenecks=["Database CPU at 98% peak", "Web tier CPU at 94% peak"],
    recommendations=[
        ResourceRecommendation(
            resource_type="database",
            current_state="db.r5.2xlarge, 1 read replica",
            recommended_state="db.r5.4xlarge, 2 read replicas",
            urgency="immediate",
            estimated_cost_impact="+$800/month",
        )
    ],
    scaling_strategy="vertical",
    timeline="2-4 weeks",
    total_cost_estimate="+$1,200/month",
    risk_if_not_acted="Database outage within 30-60 days under current growth",
    optimization_opportunities=["Switch to Reserved Instances for 30% savings"],
    executive_summary="Infrastructure is under significant stress. Immediate action required on database tier.",
)

with patch("capacity_planning.agent.get_llm_client") as mock_client:
    mock_response = MagicMock()
    mock_response.choices[0].message.content = mock_plan.model_dump_json()
    mock_client.return_value.chat.completions.create.return_value = mock_response

    from capacity_planning.agent import generate_capacity_plan
    result = generate_capacity_plan("any metrics")
    assert result.capacity_risk_level == "high"
    assert len(result.recommendations) == 1
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
docker build -t ps6-capacity-planning .
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=your_key \
  -e OPENAI_BASE_URL=https://genailab.tcs.in \
  ps6-capacity-planning
```

### Production environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | TCS GenAI Lab API key |
| `OPENAI_BASE_URL` | TCS GenAI Lab proxy URL |
| `PYTHONHTTPSVERIFY` | Set to `0` to bypass self-signed cert |
