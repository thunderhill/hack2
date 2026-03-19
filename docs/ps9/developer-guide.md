# PS9 — Travel Expense Report Summarizer: Developer Guide

## Architecture Overview

```
User (Browser)
     │
     ▼
┌──────────────────────────────────────────────┐
│  app/main.py  (Streamlit UI)                 │
│  - Expense report textarea                   │
│  - Optional policy notes in sidebar          │
│  - Calls summarize_expenses()                │
│  - Renders 3-tab expense view                │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  src/expense_report/agent.py                 │
│  summarize_expenses(data, model, policy)     │
│  - Builds messages from prompts              │
│  - Calls Azure OpenAI with parse()           │
│  - Returns ExpenseSummary                    │
└──────┬───────────────────┬────────────────────┘
       │                   │
       ▼                   ▼
┌────────────┐    ┌──────────────────────────────┐
│ config.py  │    │ prompts.py                   │
│ AzureOpenAI│    │ SYSTEM_PROMPT                │
│ client     │    │ (corporate expense auditor,  │
└────────────┘    │  default policy rules built  │
                  │  into the prompt)            │
                  └──────────────────────────────┘
       │
       ▼
Azure OpenAI API
(structured output → ExpenseSummary)
       │
       ▼
┌────────────────────────────────────────────────┐
│  src/expense_report/models.py                  │
│  ExpenseSummary + ExpenseItem + CategorySummary│
└────────────────────────────────────────────────┘
```

---

## Project Structure

```
ps9/
├── app/
│   └── main.py                       # Streamlit app — 3-tab expense rendering
├── src/
│   └── expense_report/
│       ├── __init__.py
│       ├── agent.py                  # Single function: summarize_expenses()
│       ├── config.py                 # Azure OpenAI client factory + model map
│       ├── models.py                 # ExpenseSummary + ExpenseItem + CategorySummary
│       └── prompts.py                # System prompt with built-in policy rules
└── pyproject.toml                    # Package: expense-report, Python 3.11+
```

---

## Core Components

### `agent.py`

```python
def summarize_expenses(expense_data: str, model_key: str = "gpt-4o", company_policy_notes: str = "") -> ExpenseSummary:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(expense_data, company_policy_notes)},
        ],
        response_format=ExpenseSummary,
    )
    return response.choices[0].message.parsed
```

The `company_policy_notes` parameter allows runtime policy customization without modifying the system prompt. It's appended to the user message, effectively overriding or supplementing the default policy rules.

### `models.py`

```python
class ExpenseItem(BaseModel):
    date: str               # Date of expense
    category: str           # flights | hotel | meals | transport | conference | other
    description: str        # What it was for
    amount: float           # Original amount
    currency: str           # Currency code (USD, INR, EUR, etc.)
    amount_usd: float       # Converted to USD
    receipt_present: bool   # Whether receipt was mentioned
    policy_status: str      # within_policy | exceeds_limit | needs_approval | non_reimbursable
    notes: str              # Notes about this item

class CategorySummary(BaseModel):
    category: str
    total_usd: float
    item_count: int

class ExpenseSummary(BaseModel):
    employee_name: str
    trip_purpose: str
    trip_dates: str
    destination: str
    total_claimed: float           # Total claimed in USD
    total_approved: float          # Recommended approval amount
    total_rejected: float          # Rejected amount
    items: list[ExpenseItem]       # Itemized expenses
    category_breakdown: list[CategorySummary]
    policy_violations: list[str]   # Human-readable violation descriptions
    missing_receipts: list[str]    # Items missing required receipts
    approval_recommendation: str   # APPROVE_FULL | APPROVE_PARTIAL | REJECT | NEEDS_MORE_INFO
    approval_notes: str            # Explanation for the approver
    reimbursement_breakdown: str   # What is/isn't reimbursed
```

Notable: `ExpenseItem` contains two numeric fields (`amount`, `amount_usd`) and one boolean (`receipt_present`). The AI performs currency conversion using training data exchange rates — not live rates.

### `prompts.py`

Unlike other PS projects, the system prompt in PS9 **encodes default policy rules directly**:

```python
SYSTEM_PROMPT = """You are a corporate travel expense auditor with expertise in expense policy compliance.
Given expense data, you:
1. Categorize and itemize all expenses
2. Check compliance against standard corporate travel policies:
   - Meals: max $75/day for domestic, $100/day for international
   - Hotel: max $250/night domestic, $350/night international
   - Flights: economy class only (business class needs pre-approval)
   - Alcohol is non-reimbursable
   - Receipts required for items over $25
3. Flag policy violations and missing receipts
4. Calculate approved vs. rejected amounts
5. Provide clear approval recommendation with justification

Be fair but thorough in your policy review."""
```

This means default policy is baked into the system prompt. Additional policy rules from the user are injected via the user message, effectively acting as per-request overrides.

---

## Environment Setup

```bash
cd /path/to/hack2/ps9
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

### Change default policy rules

Edit the numbered list in `SYSTEM_PROMPT` in `prompts.py`. Each rule is applied to every analysis unless overridden by the user's `company_policy_notes`.

Example — stricter meal limits:
```python
SYSTEM_PROMPT = """...
2. Check compliance against standard corporate travel policies:
   - Meals: max $50/day for domestic, $75/day for international
   - Hotel: max $200/night domestic, $300/night international
   ...
"""
```

### Add new expense categories

```python
class ExpenseItem(BaseModel):
    category: str = Field(
        description="Category: flights | hotel | meals | transport | conference | entertainment | telecom | other"
    )
```

Update `SYSTEM_PROMPT` to list the new category and its policy rules.

### Integrate live currency conversion

Replace LLM-based conversion with a real FX API:

```python
import requests

def get_exchange_rate(from_currency: str, to_currency: str = "USD") -> float:
    response = requests.get(f"https://api.exchangerate.host/latest?base={from_currency}&symbols={to_currency}")
    return response.json()["rates"][to_currency]

def convert_to_usd(amount: float, currency: str) -> float:
    if currency == "USD":
        return amount
    rate = get_exchange_rate(currency)
    return round(amount * rate, 2)
```

Pre-process the expense text to inject USD equivalents before sending to the LLM, or post-process the `ExpenseItem.amount_usd` fields after parsing.

### Integrate with SAP Concur

```python
import requests

def fetch_concur_report(report_id: str, concur_token: str) -> str:
    headers = {"Authorization": f"Bearer {concur_token}", "Accept": "application/json"}
    response = requests.get(
        f"https://www.concursolutions.com/api/v3.0/expense/reports/{report_id}",
        headers=headers
    )
    report = response.json()
    # Format into text for the prompt
    lines = [f"Employee: {report['OwnerName']}", f"Report: {report['Name']}"]
    for entry in report.get("Entries", []):
        lines.append(f"{entry['TransactionDate']} - {entry['BusinessPurpose']} - {entry['TransactionAmount']} {entry['CurrencyCode']}")
    return "\n".join(lines)
```

---

## Testing

### Test the agent in isolation

```python
import os
os.environ["AZURE_GENAI_API_KEY"] = "your_key"

from expense_report.agent import summarize_expenses

expenses = """
Employee: John Smith
Trip: New York client meeting, March 5-7, 2024

1. Mar 5 - Flight NYC economy - $420
2. Mar 5 - Hotel Marriott - $320/night x2 = $640 (receipt attached)
3. Mar 5 - Team dinner - $180 for 3 people (receipt attached)
4. Mar 6 - Taxi - $35 (receipt attached)
5. Mar 6 - Minibar - $28
Total: $1,303
"""
summary = summarize_expenses(expenses, model_key="gpt-4o-mini")
print(f"Total claimed: ${summary.total_claimed:.2f}")
print(f"Approved: ${summary.total_approved:.2f}")
print(f"Violations: {summary.policy_violations}")
print(f"Recommendation: {summary.approval_recommendation}")
```

### Unit test with mocks

```python
from unittest.mock import MagicMock, patch
from expense_report.models import ExpenseSummary, ExpenseItem, CategorySummary

mock_summary = ExpenseSummary(
    employee_name="John Smith",
    trip_purpose="Client meeting",
    trip_dates="March 5-7, 2024",
    destination="New York",
    total_claimed=1303.0,
    total_approved=1275.0,
    total_rejected=28.0,
    items=[
        ExpenseItem(date="Mar 5", category="flights", description="Flight NYC economy",
                    amount=420.0, currency="USD", amount_usd=420.0,
                    receipt_present=False, policy_status="within_policy", notes=""),
        ExpenseItem(date="Mar 5", category="other", description="Minibar",
                    amount=28.0, currency="USD", amount_usd=28.0,
                    receipt_present=False, policy_status="non_reimbursable",
                    notes="Alcohol/minibar charges are non-reimbursable"),
    ],
    category_breakdown=[CategorySummary(category="flights", total_usd=420.0, item_count=1)],
    policy_violations=["Minibar charge ($28) is non-reimbursable"],
    missing_receipts=["Flight ($420) — receipt not mentioned"],
    approval_recommendation="APPROVE_PARTIAL",
    approval_notes="Approve $1,275. Reject $28 minibar charge (non-reimbursable).",
    reimbursement_breakdown="Flight: $420, Hotel: $640, Dinner: $180, Taxi: $35. Excluding: Minibar $28.",
)

with patch("expense_report.agent.get_llm_client") as mock_client:
    mock_response = MagicMock()
    mock_response.choices[0].message.parsed = mock_summary
    mock_client.return_value.beta.chat.completions.parse.return_value = mock_response

    from expense_report.agent import summarize_expenses
    result = summarize_expenses("any expense data")
    assert result.approval_recommendation == "APPROVE_PARTIAL"
    assert result.total_rejected == 28.0
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
docker build -t ps9-expense-report .
docker run -p 8501:8501 \
  -e AZURE_GENAI_API_KEY=your_key \
  -e AZURE_GENAI_ENDPOINT=https://genailab-maas.services.ai.azure.com \
  ps9-expense-report
```

### Production environment variables

| Variable | Description |
|---|---|
| `AZURE_GENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_GENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_GENAI_API_VERSION` | API version (default: `2024-08-01-preview`) |
