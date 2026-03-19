# PS9 — Travel Expense Report Summarizer: User Guide

## Overview

The Travel Expense Report Summarizer analyzes travel expense data, categorizes items, checks policy compliance, converts currencies to USD, and provides an approval recommendation. Paste expense details in any format and get a structured summary with itemized policy status and reimbursement breakdown.

**When to use it:**
- As a finance approver reviewing a submitted expense report
- As an employee checking your own expenses before submission
- To quickly identify policy violations and missing receipts in a report

---

## Prerequisites

- Python 3.11 or higher
- Access to the TCS GenAI Lab proxy at `https://genailab.tcs.in` (requires TCS VPN)
- TCS GenAI Lab API key (provided during hackathon)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps9
pip install -e .
```

**2. Create a `.env` file in the `ps9/` directory:**

```env
OPENAI_API_KEY=your-hackathon-api-key-here
OPENAI_BASE_URL=https://genailab.tcs.in
PYTHONHTTPSVERIFY=0
REQUESTS_CA_BUNDLE=
CURL_CA_BUNDLE=
```

| Variable | Required | Default |
|---|---|---|
| `OPENAI_API_KEY` | Yes | — |
| `OPENAI_BASE_URL` | No | `https://genailab.tcs.in` |
| `PYTHONHTTPSVERIFY` | No | `0` |

---

## Running the App

```bash
cd ps9
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the model. `gpt-4o` provides the most thorough policy analysis.
- **Additional Policy Notes (optional)** — Enter company-specific policy overrides (e.g., `Client entertainment approved up to $200, project code: PROJ-123`). These supplement the default policy rules.

**Main Panel:**

1. **Expense Report Data** — Paste itemized expense data. Include dates, descriptions, amounts, and currencies. A multi-currency travel expense example is pre-loaded.

2. **Analyze Expenses** — Click to submit.

3. **Results** — Four metrics at the top:
   - **Total Claimed** — Total amount submitted in USD
   - **Approved** — Amount recommended for approval (with rejected amount as delta)
   - **Recommendation** — ✅ APPROVE FULL / ⚠️ APPROVE PARTIAL / ❌ REJECT / ❓ NEEDS MORE INFO
   - **Policy Violations** — Count of policy violations found

   Below: Employee info bar, **Approval Notes**, and **Reimbursement Breakdown** summary.

   **Three tabs:**
   - **Expense Items** — Each item with policy status icon and receipt icon:
     - ✅ Within Policy
     - 🟠 Exceeds Limit
     - ⚠️ Needs Approval
     - ❌ Non-Reimbursable
   - **Policy Issues** — All violations and missing receipts listed
   - **Category Breakdown** — Total USD per category (flights, hotel, meals, transport, conference, other)

---

## Input/Output Reference

### What to paste

Include per-expense-item details:
- Date of expense
- Description (what it was for)
- Amount and currency
- Whether a receipt was provided

The AI handles free-form text — it does not require a specific format.

### Default policy rules applied

| Category | Limit |
|---|---|
| Meals | $75/day domestic, $100/day international |
| Hotel | $250/night domestic, $350/night international |
| Flights | Economy class only (business needs pre-approval) |
| Alcohol | Non-reimbursable |
| Receipts | Required for items over $25 |

Override these with the "Additional Policy Notes" sidebar field.

### Output fields

| Field | Description |
|---|---|
| `employee_name` | Name extracted from input |
| `trip_purpose` | Purpose of the trip |
| `total_claimed` | Total claimed in USD |
| `total_approved` | Total approved in USD |
| `total_rejected` | Total rejected in USD |
| `items[].category` | flights / hotel / meals / transport / conference / other |
| `items[].amount_usd` | Amount converted to USD |
| `items[].receipt_present` | Whether receipt was mentioned |
| `items[].policy_status` | within_policy / exceeds_limit / needs_approval / non_reimbursable |
| `items[].notes` | Notes about the specific item |
| `category_breakdown` | Total USD and count per category |
| `policy_violations` | List of policy violations |
| `missing_receipts` | Items missing required receipts |
| `approval_recommendation` | APPROVE_FULL / APPROVE_PARTIAL / REJECT / NEEDS_MORE_INFO |
| `approval_notes` | Explanation of the recommendation |
| `reimbursement_breakdown` | Summary of what is and isn't reimbursed |

---

## Troubleshooting

**`OPENAI_API_KEY is not set in .env`**
→ Ensure `.env` exists in the `ps9/` directory with `OPENAI_API_KEY` and `OPENAI_BASE_URL` set, and that TCS VPN is active.

**`Analysis failed: ...`**
→ Check that `.env` has the correct `OPENAI_API_KEY` and `OPENAI_BASE_URL=https://genailab.tcs.in`, and that TCS VPN is active.

**Currency conversion seems inaccurate**
→ The AI uses approximate exchange rates from its training data. For precise conversions, pre-convert amounts to USD before pasting.

**Custom policy rules not applied**
→ Paste your company's specific policy limits into the "Additional Policy Notes" sidebar field before running the analysis.
