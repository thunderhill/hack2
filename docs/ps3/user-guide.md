# PS3 — Build Failure Diagnosis: User Guide

## Overview

The Build Failure Diagnosis tool diagnoses compilation and build errors from build tool output and provides concrete fix instructions. Paste output from Maven, Gradle, npm, pip, cargo, make, or any other build tool, and the AI returns the error location, a clear diagnosis, and a code-level fix.

**When to use it:**
- A build is failing and the error message is unclear
- You're working in an unfamiliar language or build tool
- You want a code-level fix suggestion, not just a diagnosis

---

## Prerequisites

- Python 3.11 or higher
- Access to an Azure OpenAI deployment with one of: `gpt-4o`, `gpt-4o-mini`, or `gpt-35-turbo`
- Azure GenAI API credentials (key + endpoint)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps3
pip install -e .
```

**2. Create a `.env` file in the `ps3/` directory:**

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
cd ps3
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the model. `gpt-4o` gives the best code fix suggestions.
- **Language/Framework (optional)** — Provide a hint like `Java Spring Boot` or `Python Flask` to improve accuracy.

**Main Panel:**

1. **Build Output** — Paste the raw output from your build tool. A Maven compilation error example is pre-loaded.

2. **Diagnose Build Failure** — Click to submit. The AI analyzes the output and returns a structured diagnosis.

3. **Results** — Four metrics at the top:
   - **Build Tool** — Detected tool (MAVEN, GRADLE, NPM, PIP, CARGO, MAKE, OTHER)
   - **Language** — Detected language (Java, Python, JavaScript, Rust, C++, other)
   - **Error Type** — compilation / dependency / configuration / linking / syntax / runtime
   - **Est. Fix Time** — Estimated time to resolve (minutes / hours / days)

   Below:
   - **Error Location** — File path, line number, and column where the error occurred
   - **Core Error** — The extracted error message
   - **Diagnosis** — Why the build failed
   - **How to Fix** — Step-by-step fix explanation
   - **Code Fix** — Concrete code or config change to apply (when applicable)

---

## Input/Output Reference

### What to paste

Paste the complete output from your build command. Useful sources:
- `mvn compile` / `mvn package` output
- `gradle build` output
- `npm install` / `npm run build` output
- `pip install` / `python setup.py` output
- `cargo build` output
- `make` output with error lines

Include the full error block, not just the final "BUILD FAILED" line.

### Output fields

| Field | Description |
|---|---|
| `build_tool` | Detected build tool |
| `language` | Detected programming language |
| `error_type` | compilation / dependency / configuration / linking / syntax / runtime |
| `error_message` | The core error extracted from the output |
| `error_location.file_path` | File where the error occurred |
| `error_location.line_number` | Line number of the error |
| `error_location.column` | Column number |
| `diagnosis` | Why the build failed |
| `fix_explanation` | How to fix it, step by step |
| `code_fix` | Concrete code or config to change (or `N/A`) |
| `estimated_fix_time` | minutes / hours / days |

---

## Troubleshooting

**`AZURE_GENAI_API_KEY is not set in environment`**
→ Ensure `.env` exists in the `ps3/` directory with the correct key.

**`Diagnosis failed: ...`**
→ Check your Azure credentials and endpoint. Ensure the deployment name is active.

**Error location shows `unknown`**
→ The build output may not include file/line information. Paste more complete output including the compiler error section.

**Wrong language or tool detected**
→ Use the "Language/Framework" hint in the sidebar to guide the AI.
