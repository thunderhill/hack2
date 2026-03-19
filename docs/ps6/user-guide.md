# PS6 — Capacity Planning Advisor: User Guide

## Overview

The Capacity Planning Advisor analyzes your current infrastructure metrics and provides specific scaling recommendations with cost estimates. Enter CPU, memory, storage, and network utilization data, optionally add growth projections and SLA requirements, and get a prioritized capacity plan.

**When to use it:**
- Infrastructure utilization is high and you need to plan for scaling
- Preparing a quarterly capacity review for your team or management
- Evaluating the cost of scaling before committing to changes
- Identifying optimization opportunities to reduce cloud spend

---

## Prerequisites

- Python 3.11 or higher
- Access to an Azure OpenAI deployment with one of: `gpt-4o`, `gpt-4o-mini`, or `gpt-35-turbo`
- Azure GenAI API credentials (key + endpoint)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps6
pip install -e .
```

**2. Create a `.env` file in the `ps6/` directory:**

```env
AZURE_GENAI_API_KEY=your_api_key_here
AZURE_GENAI_ENDPOINT=https://genailab-maas.services.ai.azure.com
AZURE_GENAI_API_VERSION=2024-08-01-preview
```

| Variable | Required | Default |
|---|---|---|
| `AZURE_GENAI_API_KEY` | Yes | — |
| `AZURE_GENAI_ENDPOINT` | No | `https://genailab-maas.services.ai.azure.com` |
| `AZURE_GENAI_API_VERSION` | No | `2024-08-01-preview` |

---

## Running the App

```bash
cd ps6
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the model. `gpt-4o` provides the most thorough analysis.
- **Growth Projection** — Optionally describe expected growth (e.g., `40% user growth in 6 months`).
- **SLA Requirements** — Optionally specify SLA targets (e.g., `99.9% uptime, <200ms response`).

**Main Panel:**

1. **Current Infrastructure Metrics** — Paste your current utilization data. Include compute, database, cache, storage, and network metrics. An AWS production environment example is pre-loaded.

2. **Generate Capacity Plan** — Click to submit. The AI analyzes the metrics and generates a prioritized capacity plan.

3. **Results** — Four metrics at the top:
   - **Risk Level** — 🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / 🟢 LOW
   - **Scaling Strategy** — VERTICAL / HORIZONTAL / HYBRID / SERVERLESS
   - **Cost Estimate** — Total estimated monthly cost of recommended changes
   - **Timeline** — Recommended implementation timeframe

   Below:
   - **Executive Summary** — 2–3 sentence overview of the capacity situation
   - **Current Bottlenecks** — Resources at or near capacity limits
   - **Recommendations** — Expandable cards per resource type, color-coded by urgency:
     - 🔴 Immediate — act within days
     - 🟠 Within Month
     - 🟡 Within Quarter
     - 🟢 Planned — backlog item
   - **Cost Optimizations** — Opportunities to reduce spend
   - **Risk of Inaction** — Consequences if no action is taken

---

## Input/Output Reference

### What to enter

Include current utilization metrics for each resource tier:
- **Compute** — Instance types, vCPU/RAM, average and peak CPU%, current cost
- **Database** — Instance type, CPU%, storage used/allocated, replica status, cost
- **Cache** — Memory usage%, cache hit rate, cost
- **Storage** — Used/total capacity, growth rate, cost
- **Network** — Requests/minute average and peak, cost

### Output fields

| Field | Description |
|---|---|
| `capacity_risk_level` | critical / high / medium / low |
| `bottlenecks` | Current or near-term capacity constraints |
| `recommendations[].resource_type` | compute / memory / storage / network / database |
| `recommendations[].current_state` | Current resource configuration |
| `recommendations[].recommended_state` | What to change to |
| `recommendations[].urgency` | immediate / within_month / within_quarter / planned |
| `recommendations[].estimated_cost_impact` | Monthly cost change (e.g., `+$500/month`) |
| `scaling_strategy` | vertical / horizontal / hybrid / serverless |
| `timeline` | Recommended implementation timeline |
| `total_cost_estimate` | Total monthly cost of all recommended changes |
| `optimization_opportunities` | Cost reduction suggestions |
| `risk_if_not_acted` | Consequences of inaction |
| `executive_summary` | 2–3 sentence summary |

---

## Troubleshooting

**`AZURE_GENAI_API_KEY is not set in environment`**
→ Ensure `.env` exists in the `ps6/` directory with the correct key.

**`Planning failed: ...`**
→ Check Azure credentials and endpoint. Verify the deployment is active.

**Recommendations seem too aggressive**
→ If you have conservative SLA requirements or budget constraints, add them to the "SLA Requirements" sidebar field.

**Missing cost estimates**
→ Include current monthly costs for each resource tier in your input. The AI uses these to project cost impact.
