# PS5 — Infrastructure Change Explainer: Developer Guide

## Architecture Overview

```
User (Browser)
     │
     ▼
┌─────────────────────────────────────────┐
│  app/main.py  (Streamlit UI)            │
│  - Renders change request textarea      │
│  - Accepts optional environment hint    │
│  - Calls explain_change()               │
│  - Displays ChangeExplanation fields    │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  src/infra_explainer/agent.py           │
│  explain_change(request, model, env)    │
│  - Builds messages from prompts         │
│  - Calls Azure OpenAI with parse()      │
│  - Returns ChangeExplanation            │
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
Azure OpenAI API (senior infra engineer + CAB expert persona)
(structured output → ChangeExplanation)
       │
       ▼
┌─────────────────────────────────────────┐
│  src/infra_explainer/models.py          │
│  ChangeExplanation + RiskItem           │
└─────────────────────────────────────────┘
```

---

## Project Structure

```
ps5/
├── app/
│   └── main.py                      # Streamlit app — rendering only
├── src/
│   └── infra_explainer/
│       ├── __init__.py
│       ├── agent.py                 # Single function: explain_change()
│       ├── config.py                # Azure OpenAI client factory + model map
│       ├── models.py                # ChangeExplanation + RiskItem
│       └── prompts.py               # System prompt + user message builder
└── pyproject.toml                   # Package: infra-explainer, Python 3.11+
```

---

## Core Components

### `agent.py`

```python
def explain_change(change_request: str, model_key: str = "gpt-4o", environment: str = "") -> ChangeExplanation:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(change_request, environment)},
        ],
        response_format=ChangeExplanation,
    )
    return response.choices[0].message.parsed
```

### `models.py`

```python
class RiskItem(BaseModel):
    risk: str          # Description of the specific risk
    likelihood: str    # high | medium | low
    impact: str        # high | medium | low

class ChangeExplanation(BaseModel):
    change_type: str              # terraform | kubernetes | ansible | cloudformation | firewall | network | other
    summary: str                  # One-sentence summary
    plain_english: str            # Detailed explanation for non-infra audience
    resources_affected: list[str] # List of infrastructure resources
    change_nature: str            # additive | destructive | modifying | scaling | security | configuration
    risk_level: str               # critical | high | medium | low
    risks: list[RiskItem]         # Specific identified risks
    rollback_possible: bool       # Whether rollback is feasible
    rollback_procedure: str       # How to roll back, or "N/A"
    review_checklist: list[str]   # Items for reviewers to verify
    approval_recommendation: str  # APPROVE | APPROVE_WITH_CONDITIONS | REJECT | NEEDS_MORE_INFO
```

Note that `rollback_possible` is a `bool` — the only non-string field. The OpenAI structured output API handles this correctly since Pydantic's JSON schema includes the boolean type.

### `prompts.py`

The system prompt frames the AI as a "senior infrastructure engineer and change advisory board expert" with specific attention to "security, availability, and compliance implications." This framing produces more conservative risk assessments appropriate for infrastructure change review.

The `environment` parameter (e.g., `Production`) is injected into the user message to weight risk assessments: a change to production warrants higher risk ratings than the same change to staging.

---

## Environment Setup

```bash
cd /path/to/hack2/ps5
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

### Add a new change type

`change_type` is a free-form string detected by the LLM. To constrain it to known values:

```python
from typing import Literal

class ChangeExplanation(BaseModel):
    change_type: Literal["terraform", "kubernetes", "ansible", "cloudformation", "firewall", "network", "helm", "pulumi", "other"]
    ...
```

### Add a compliance assessment section

```python
class ComplianceItem(BaseModel):
    standard: str      # e.g., "SOC 2", "PCI DSS", "GDPR"
    impact: str        # How this change affects compliance
    action_required: str  # What needs to be done for compliance

class ChangeExplanation(BaseModel):
    ...
    compliance_impacts: list[ComplianceItem] = Field(
        description="Compliance implications of this change"
    )
```

Update `SYSTEM_PROMPT` to request compliance analysis.

### Add risk scoring

Add a numeric risk score alongside the qualitative level:

```python
class ChangeExplanation(BaseModel):
    ...
    risk_score: int = Field(description="Numeric risk score 1-10, where 10 is highest risk")
```

### Integrate with a ticketing system

After `explain_change()` returns, create a change ticket automatically:

```python
def create_change_ticket(result: ChangeExplanation, change_text: str) -> str:
    # POST to Jira/ServiceNow/etc.
    ticket_body = f"""
    Summary: {result.summary}
    Risk Level: {result.risk_level}
    Recommendation: {result.approval_recommendation}

    Plain English: {result.plain_english}

    Review Checklist:
    {chr(10).join(f'- {item}' for item in result.review_checklist)}
    """
    # ... API call to ticketing system
    return ticket_url
```

---

## Testing

### Test the agent in isolation

```python
import os
os.environ["AZURE_GENAI_API_KEY"] = "your_key"

from infra_explainer.agent import explain_change

terraform_plan = """
  # aws_security_group.web_sg will be updated in-place
  ~ ingress {
      ~ cidr_blocks = ["10.0.0.0/8"] -> ["0.0.0.0/0"]
    }
"""
result = explain_change(terraform_plan, model_key="gpt-4o-mini", environment="Production")
print(result.risk_level)
print(result.approval_recommendation)
print(result.rollback_possible)
```

### Unit test with mocks

```python
from unittest.mock import MagicMock, patch
from infra_explainer.models import ChangeExplanation, RiskItem

mock_result = ChangeExplanation(
    change_type="terraform",
    summary="Opens HTTPS port to internet from internal-only",
    plain_english="This change removes IP restrictions on port 443, allowing anyone on the internet to reach your web servers.",
    resources_affected=["aws_security_group.web_sg"],
    change_nature="security",
    risk_level="high",
    risks=[RiskItem(risk="Exposes web tier to internet", likelihood="high", impact="high")],
    rollback_possible=True,
    rollback_procedure="Revert the CIDR block to 10.0.0.0/8",
    review_checklist=["Verify WAF is in place", "Confirm load balancer handles TLS termination"],
    approval_recommendation="APPROVE_WITH_CONDITIONS",
)

with patch("infra_explainer.agent.get_llm_client") as mock_client:
    mock_response = MagicMock()
    mock_response.choices[0].message.parsed = mock_result
    mock_client.return_value.beta.chat.completions.parse.return_value = mock_response

    from infra_explainer.agent import explain_change
    result = explain_change("any terraform plan")
    assert result.risk_level == "high"
    assert result.rollback_possible is True
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
docker build -t ps5-infra-explainer .
docker run -p 8501:8501 \
  -e AZURE_GENAI_API_KEY=your_key \
  -e AZURE_GENAI_ENDPOINT=https://genailab-maas.services.ai.azure.com \
  ps5-infra-explainer
```

### Production environment variables

| Variable | Description |
|---|---|
| `AZURE_GENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_GENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_GENAI_API_VERSION` | API version (default: `2024-08-01-preview`) |
