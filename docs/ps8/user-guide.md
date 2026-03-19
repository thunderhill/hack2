# PS8 — DevOps Incident Report Generator: User Guide

## Overview

The DevOps Incident Report Generator creates professional post-incident reports (PIRs) from raw incident notes, Slack messages, PagerDuty alerts, and timeline entries. It follows Google SRE and ITIL incident management best practices and produces a blameless, structured report suitable for sharing with stakeholders.

**When to use it:**
- After resolving an incident and conducting a post-mortem
- Converting messy Slack threads and alert history into a formal PIR
- Generating action items and lessons learned automatically from incident notes

---

## Prerequisites

- Python 3.11 or higher
- Access to the TCS GenAI Lab proxy at `https://genailab.tcs.in` (requires TCS VPN)
- TCS GenAI Lab API key (provided during hackathon)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps8
pip install -e .
```

**2. Create a `.env` file in the `ps8/` directory:**

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
cd ps8
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the model. `gpt-4o` generates the most complete reports.
- **Service/System Name** — Optionally specify the affected service (e.g., `Payment API`, `Auth Service`) to improve title and context generation.

**Main Panel:**

1. **Incident Notes & Timeline** — Paste any combination of: Slack messages, PagerDuty alert history, raw timeline notes, runbook annotations, or team communications. A payment API incident example is pre-loaded.

2. **Generate Incident Report** — Click to generate. The AI reconstructs the incident from the notes and creates a complete report.

3. **Results** — Four metrics at the top:
   - **Incident ID** — Extracted or generated identifier
   - **Severity** — 🔴 SEV1 / 🟠 SEV2 / 🟡 SEV3 / 🟢 SEV4
   - **Total Duration** — Full incident duration
   - **Users Affected** — Estimated affected user count

   Below the metrics: Incident title, executive summary, and detection/resolution/status metrics.

   **Four tabs:**
   - **Timeline** — Affected services, customer impact, chronological events with actor icons (🤖 system, 👤 engineer, ⚙️ automated)
   - **Root Cause** — Root cause, contributing factors, lessons learned
   - **Response Quality** — What went well (✅) and what went wrong (❌)
   - **Action Items** — Prioritized follow-up items with owner and due date (🔴 P1 / 🟠 P2 / 🟡 P3)

---

## Input/Output Reference

### What to paste

Include as much context as available:
- Timestamped alert history (e.g., `14:32 - PagerDuty alert: error rate >5%`)
- On-call engineer actions and observations
- Root cause findings (even preliminary)
- Customer impact data (ticket counts, revenue impact, user counts)
- Team notes from retrospective discussion

### Output fields

| Field | Description |
|---|---|
| `incident_id` | Incident identifier |
| `title` | Concise incident title |
| `severity` | SEV1 / SEV2 / SEV3 / SEV4 |
| `status` | resolved / monitoring / ongoing |
| `total_duration` | Full incident duration |
| `time_to_detect` | Time from start to first alert |
| `time_to_resolve` | Time from detection to resolution |
| `affected_services` | List of impacted services |
| `customer_impact` | Description of user/customer impact |
| `users_affected` | Estimated affected users |
| `executive_summary` | 2–3 sentence summary for stakeholders |
| `timeline[].timestamp` | Event timestamp |
| `timeline[].event` | What happened |
| `timeline[].actor` | system / engineer / automated |
| `root_cause` | Root cause (5-why methodology) |
| `contributing_factors` | Secondary factors |
| `what_went_well` | Positive aspects of the response |
| `what_went_wrong` | Areas for improvement |
| `lessons_learned` | Key takeaways |
| `action_items[].action` | Specific follow-up action |
| `action_items[].owner` | Responsible team or role |
| `action_items[].priority` | P1 / P2 / P3 |
| `action_items[].due_date` | Target completion date |

### Severity guide

| Level | Criteria |
|---|---|
| SEV1 | Complete service outage, major revenue impact |
| SEV2 | Significant degradation, partial outage |
| SEV3 | Minor degradation, workaround available |
| SEV4 | Minimal impact, cosmetic issue |

---

## Troubleshooting

**`OPENAI_API_KEY is not set in .env`**
→ Ensure `.env` exists in the `ps8/` directory with `OPENAI_API_KEY` and `OPENAI_BASE_URL` set, and that TCS VPN is active.

**`Report generation failed: ...`**
→ Check that `.env` has the correct `OPENAI_API_KEY` and `OPENAI_BASE_URL=https://genailab.tcs.in`, and that TCS VPN is active.

**Timeline events are out of order**
→ The AI reconstructs the timeline from unstructured notes. For best results, include timestamps with each event.

**Action items lack specific owners**
→ Include team names or roles in your notes (e.g., "DB team investigated", "on-call engineer John D.").
