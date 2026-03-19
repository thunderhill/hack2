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
- Access to an Azure OpenAI deployment with one of: `gpt-4o`, `gpt-4o-mini`, or `gpt-35-turbo`
- Azure GenAI API credentials (key + endpoint)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps2
pip install -e .
```

**2. Create a `.env` file in the `ps2/` directory:**

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
cd ps2
streamlit run app/main.py
```

The app opens in your browser at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the Azure OpenAI model to use. `gpt-4o` is the most capable; `gpt-4o-mini` and `gpt-35-turbo` are faster and cheaper.

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

**`AZURE_GENAI_API_KEY is not set in environment`**
→ Ensure your `.env` file exists in the `ps2/` directory and contains `AZURE_GENAI_API_KEY`.

**`Analysis failed: ...` (API error)**
→ Check that your endpoint URL and API key are correct. Verify the deployment name exists in your Azure OpenAI resource.

**Empty or incomplete results**
→ The log may be too short or ambiguous. Include more context — at minimum, the error message and surrounding lines.

**App fails to start**
→ Run `pip install -e .` inside the `ps2/` directory to ensure all dependencies are installed.
