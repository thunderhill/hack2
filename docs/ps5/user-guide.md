# PS5 — Infrastructure Change Explainer: User Guide

## Overview

The Infrastructure Change Explainer translates infrastructure changes into plain English and provides a risk assessment with an approval recommendation. Paste a Terraform plan, Kubernetes diff, Ansible playbook, or CloudFormation changeset, and get a structured explanation suitable for both technical reviewers and non-infrastructure stakeholders.

**When to use it:**
- Reviewing an infrastructure change before approving it
- Explaining a Terraform plan to a non-technical stakeholder
- Generating a change advisory board (CAB) review summary
- Assessing rollback feasibility before applying a change

---

## Prerequisites

- Python 3.11 or higher
- Access to an Azure OpenAI deployment with one of: `gpt-4o`, `gpt-4o-mini`, or `gpt-35-turbo`
- Azure GenAI API credentials (key + endpoint)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps5
pip install -e .
```

**2. Create a `.env` file in the `ps5/` directory:**

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
cd ps5
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the model. `gpt-4o` gives the most thorough risk assessments.
- **Target Environment** — Optionally specify the target environment (e.g., `Production`, `Staging`). This gives the AI context to weight risks appropriately.

**Main Panel:**

1. **Infrastructure Change Request** — Paste the change definition. A Terraform plan showing a security group and autoscaling group change is pre-loaded. Replace it with your own.

2. **Explain & Assess Change** — Click to analyze. The AI evaluates the change and returns a structured assessment.

3. **Results** — Four metrics at the top:
   - **Change Type** — TERRAFORM / KUBERNETES / ANSIBLE / CLOUDFORMATION / FIREWALL / NETWORK / OTHER
   - **Risk Level** — 🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / 🟢 LOW
   - **Nature** — additive / destructive / modifying / scaling / security / configuration
   - **Recommendation** — ✅ APPROVE / ⚠️ APPROVE_WITH_CONDITIONS / ❌ REJECT / ❓ NEEDS_MORE_INFO

   Below:
   - **Summary** — One-sentence summary of what the change does
   - **Plain English Explanation** — Detailed explanation for non-infrastructure experts
   - **Resources Affected** — List of infrastructure resources being changed
   - **Risk Assessment** — Expandable risk items with likelihood and impact ratings
   - **Rollback** — Whether rollback is possible and the rollback procedure
   - **Review Checklist** — Checklist of items reviewers should verify before approving

---

## Input/Output Reference

### What to paste

Any infrastructure change definition format:
- `terraform plan` output
- `kubectl diff` output
- Ansible playbook YAML
- AWS CloudFormation changeset
- Firewall rule changes
- Network configuration diffs

### Output fields

| Field | Description |
|---|---|
| `change_type` | terraform / kubernetes / ansible / cloudformation / firewall / network / other |
| `summary` | One-sentence summary |
| `plain_english` | Detailed plain-English explanation |
| `resources_affected` | List of affected resources |
| `change_nature` | additive / destructive / modifying / scaling / security / configuration |
| `risk_level` | critical / high / medium / low |
| `risks[].risk` | Description of a specific risk |
| `risks[].likelihood` | high / medium / low |
| `risks[].impact` | high / medium / low |
| `rollback_possible` | true / false |
| `rollback_procedure` | How to roll back (or `N/A`) |
| `review_checklist` | Items to verify before approving |
| `approval_recommendation` | APPROVE / APPROVE_WITH_CONDITIONS / REJECT / NEEDS_MORE_INFO |

---

## Troubleshooting

**`AZURE_GENAI_API_KEY is not set in environment`**
→ Ensure `.env` exists in the `ps5/` directory with the correct key.

**`Analysis failed: ...`**
→ Check Azure credentials. Verify the deployment is active.

**Change type detected incorrectly**
→ The AI infers the type from the content. If it's ambiguous, add a comment at the top of your pasted change (e.g., `# Kubernetes deployment diff`).

**Risk level seems too low**
→ Specify the target environment in the sidebar (`Production`) to get more conservative risk ratings.
