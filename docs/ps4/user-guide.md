# PS4 — Quality Inspection Assistant: User Guide

## Overview

The Quality Inspection Assistant analyzes manufacturing quality inspection data and generates comprehensive quality reports. Enter observations, measurements, and defect descriptions, and the tool returns a structured report with a quality score, defect catalog, root cause analysis, and disposition recommendation.

**When to use it:**
- After a physical inspection to produce a structured quality report
- To classify defects by type and severity automatically
- To get corrective and preventive action recommendations based on ISO 9001 standards

---

## Prerequisites

- Python 3.11 or higher
- Access to the TCS GenAI Lab proxy at `https://genailab.tcs.in` (requires TCS VPN)
- TCS GenAI Lab API key (provided during hackathon)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps4
pip install -e .
```

**2. Create a `.env` file in the `ps4/` directory:**

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
cd ps4
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the model. `gpt-4o` provides the most accurate quality assessments.
- **Product Type (optional)** — Provide context like `Automotive brake pad` or `Electronic PCB` to improve analysis accuracy.

**Main Panel:**

1. **Inspection Data** — Enter your inspection observations. Include defect counts, measurements, test results, and any deviations from spec. A brake pad inspection example is pre-loaded.

2. **Generate Report** — Click to submit. The AI generates a structured quality report.

3. **Results** — Four metrics at the top:
   - **Status** — `PASS`, `FAIL`, or `CONDITIONAL_PASS`
   - **Quality Score** — 0.0 to 100.0
   - **Defects Found** — Total count of identified defects
   - **Disposition** — `rework`, `scrap`, `accept`, or `quarantine`

   Below:
   - **Defect Catalog** — Expandable list of individual defects with severity icons:
     - 🔴 Critical — product-safety or function-critical defects
     - 🟠 Major — significant defects affecting performance
     - 🟡 Minor — cosmetic or low-impact defects
   - **Root Cause Analysis** — Probable causes of the defects found
   - **Corrective Actions** — Immediate steps to address the current batch
   - **Preventive Measures** — Long-term process improvements
   - **Inspector Notes** — Additional AI-generated observations

---

## Input/Output Reference

### What to enter

Include any combination of:
- Defect counts and descriptions (e.g., "23 units show surface cracks 2-5mm")
- Measurement deviations (e.g., "thickness 9.2mm vs required 10.0mm ±0.2mm")
- Test failures (e.g., "2 units failed shear strength: 850N vs 1000N minimum")
- Process parameter exceedances (e.g., "cure temperature reached 185°C, limit 180°C")
- Batch metadata (product ID, date, batch size, inspector)

### Output fields

| Field | Description |
|---|---|
| `product_id` | Product or batch identifier extracted from input |
| `overall_quality_status` | `PASS` / `FAIL` / `CONDITIONAL_PASS` |
| `quality_score` | 0.0–100.0 quality score |
| `defect_count` | Total number of defects identified |
| `defects[].defect_type` | dimensional / surface / material / functional / cosmetic |
| `defects[].severity` | critical / major / minor |
| `defects[].affected_component` | Which part is affected |
| `root_cause_analysis` | Probable root causes |
| `corrective_actions` | Immediate actions required |
| `preventive_measures` | Long-term preventive measures |
| `disposition` | rework / scrap / accept / quarantine |
| `inspector_notes` | Additional observations |

---

## Troubleshooting

**`OPENAI_API_KEY is not set in .env`**
→ Ensure `.env` exists in the `ps4/` directory and contains `OPENAI_API_KEY` and `OPENAI_BASE_URL`. Verify that TCS VPN is active.

**`Report generation failed: ...`**
→ Check that your `.env` has the correct `OPENAI_API_KEY` and `OPENAI_BASE_URL=https://genailab.tcs.in`. Verify that TCS VPN is active.

**Quality score seems too high/low**
→ Provide more complete data including measurements, pass/fail results, and defect counts. Vague descriptions produce less precise scores.

**Defects not categorized correctly**
→ Use the "Product Type" hint in the sidebar to give context about the product being inspected.
