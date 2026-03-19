# PS2 — Pipeline Anomaly Explainer: User Guide

## Overview

The Pipeline Anomaly Explainer analyzes CI/CD pipeline logs to identify anomalies and provide actionable remediation advice. Paste a log snippet from any CI/CD system (GitHub Actions, Jenkins, GitLab CI, etc.) and the tool returns a structured analysis including severity, root cause, and step-by-step fixes.

**When to use it:**
- A pipeline build failed and you're not sure why
- You want a quick summary of what went wrong before digging into logs
- You need to communicate the issue to teammates unfamiliar with the pipeline

---

## Prerequisites

- Python 3.11 or higher
- Access to the TCS GenAI Lab proxy at `https://genailab.tcs.in` (requires TCS VPN)
- TCS GenAI Lab API key (provided during hackathon)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps2
pip install -e .
```

**2. Create a `.env` file in the `ps2/` directory:**

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
cd ps2
streamlit run app/main.py
```

The app opens in your browser at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the LLM model to use. `gpt-4o` is the most capable; `gpt-4o-mini` and `gpt-35-turbo` are faster and cheaper.

**Main Panel:**

1. **Pipeline Log Snippet** — Paste your CI/CD log output into the text area. A sample Maven/npm dependency conflict log is pre-loaded. Clear it and paste your own log.

2. **Analyze Anomaly** — Click this button to submit the log for analysis. A spinner appears while the AI processes the input.

3. **Results** — After analysis, three metrics appear at the top:
   - **Anomaly Type** — Category of failure (e.g., "Dependency Conflict", "Compilation Error")
   - **Severity** — `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW`
   - **Affected Stage** — The pipeline stage where the failure occurred (e.g., "install-dependencies")

   Below the metrics:
   - **Plain English Summary** — Non-technical description of what went wrong
   - **Root Cause** — Technical explanation of the underlying cause
   - **Remediation Steps** — Numbered list of steps to fix the issue
   - **Prevention Tips** — Bulleted list of practices to prevent recurrence

---

## Input/Output Reference

### What to paste

Paste raw log output from your CI/CD system. The more complete the log, the better the analysis. Good inputs include:
- Full build stage output with timestamps
- Error messages and stack traces
- Exit codes and stage names
- Tool output (npm, Maven, Docker, etc.)

### Output fields

| Field | Description |
|---|---|
| `anomaly_type` | Short label for the failure category |
| `severity` | `critical` / `high` / `medium` / `low` |
| `affected_stage` | The pipeline stage where the failure occurred |
| `plain_english_summary` | Clear explanation for any audience |
| `root_cause` | Technical root cause of the anomaly |
| `remediation_steps` | Ordered list of steps to resolve the issue |
| `prevention_tips` | Long-term tips to prevent recurrence |

---

## Troubleshooting

**`OPENAI_API_KEY is not set in .env`**
→ Ensure your `.env` file exists in the `ps2/` directory and contains `OPENAI_API_KEY` and `OPENAI_BASE_URL`. Verify that TCS VPN is active.

**`Analysis failed: ...` (API error)**
→ Check that your `.env` has the correct `OPENAI_API_KEY` and `OPENAI_BASE_URL=https://genailab.tcs.in`. Verify that TCS VPN is active.

**Empty or incomplete results**
→ The log may be too short or ambiguous. Include more context — at minimum, the error message and surrounding lines.

**App fails to start**
→ Run `pip install -e .` inside the `ps2/` directory to ensure all dependencies are installed.
