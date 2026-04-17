# EDA Report Generator — Design Spec

**Date:** 2026-04-17
**Project:** ps11 / Automated Exploratory Data Report Generator
**Hackathon:** AI Friday Season 2

---

## Problem

Data analysts spend excessive time on repetitive EDA tasks — computing distributions, checking data quality, building charts, and writing summaries — before any modeling can begin. Current tools lack natural language explanations tailored to each dataset. This app auto-generates comprehensive EDA reports combining statistical summaries, Plotly visualizations, and GenAI-written narratives to dramatically speed up data comprehension and stakeholder communication.

---

## Architecture: Option B — Layered Pipeline

Each module has one clear purpose. The Streamlit app orchestrates them in sequence. Follows the ps10 pattern exactly.

---

## Project Structure

```
ps11/
├── app_mcp.py                  # Streamlit entry point (SSL patch as first lines)
├── mcp_server.py               # MCP server exposing 3 tools
├── chroma_store.py             # ChromaDB wrapper for past report summaries
├── pyproject.toml
├── .env.example
├── data/
│   ├── retail_sales.csv        # Bundled demo dataset (~500 rows)
│   └── it_service_desk.csv     # Bundled demo dataset (~500 rows)
└── src/
    └── eda_report/
        ├── __init__.py
        ├── config.py           # OpenAI client, model map, get_llm_client()
        ├── models.py           # Pydantic: ColumnMeta, ColumnProfile, DatasetProfile, ExecutiveSummary
        ├── infer.py            # Type inference, ID/datetime/target column detection
        ├── preprocess.py       # Null imputation, outlier detection, column grouping
        ├── profile.py          # Statistical summaries → DatasetProfile
        ├── charts.py           # Plotly figure builders per chart type
        ├── insights.py         # LLM calls: per-section narratives + executive summary
        └── guardrails.py       # Input validation: file size, column count, PII flag
```

---

## UI Layout

### Sidebar — Two Zones

**Top (Controls):**
- Dataset source: radio — "Upload file" | "Use demo dataset"
- If demo: selectbox — "Retail Sales" | "IT Service Desk"
- If upload: `st.file_uploader` accepting `.csv` and `.xlsx`
- Model selector (same pattern as ps10: `gpt-4o-mini` default)
- "Generate Report" button (disabled until dataset selected)

**Bottom (Navigation — appears after report generated):**
Clickable section links stored in `st.session_state["active_section"]`:
1. Overview
2. Data Quality
3. Distributions
4. Correlations
5. Outliers & Anomalies
6. AI Insights
7. Export

### Main Area

Renders one section at a time based on `active_section`. Each section has:
- Colored gradient header band (section-specific accent color)
- Metric cards (teal for counts, amber for warnings, red for critical issues)
- Plotly charts (dark background)
- AI narrative card (dark card, purple left border, ✨ icon)

### Color Palette

| Token | Value | Usage |
|---|---|---|
| Background | `#0e0e1a` | Page background |
| Card background | `#1a1a2e → #252540` | Gradient card fill |
| Teal accent | `#00d4aa` | Counts, positive metrics |
| Purple accent | `#7c6bf2` | Recommendations, AI cards |
| Amber accent | `#ffc300` | Warnings, missing data |
| Coral accent | `#ff6b6b` | Errors, outliers, anomalies |
| Text primary | `#e0e0ff` | All body text |
| Grid/border | `#2a2a4a` | Card borders, chart gridlines |

Plotly chart theme: `paper_bgcolor="#0e0e1a"`, `plot_bgcolor="#1a1a2e"`, discrete palette `[#00d4aa, #7c6bf2, #ffc300, #ff6b6b, #00b4d8]`, continuous scale `Viridis`. Applied via shared `_apply_theme(fig)` helper in `charts.py`.

---

## Data Pipeline

### 1. `infer.py` — Type Inference

Produces a `ColumnMeta` for each column:

- **Dtype classification:** `numeric` | `categorical` | `datetime` | `boolean` | `text`
- **`is_id`:** high-cardinality unique strings or ints → excluded from analysis charts
- **`is_target`:** binary numeric with low cardinality → flagged as likely ML target
- **`is_datetime`:** auto-parsed date strings using `pd.to_datetime(errors='coerce')`
- **`role`:** `"dimension"` if <20 unique values, `"measure"` otherwise

### 2. `preprocess.py` — Cleaning

- **Nulls:** median imputation for numeric, mode for categorical; original null % stored in `ColumnMeta.null_pct`
- **Outliers:** IQR method — flags values beyond 1.5×IQR into `OutlierSummary(count, pct, lower_bound, upper_bound)`
- **Datetime:** parsed to `pd.Timestamp`; helper columns `_year`, `_month`, `_dow` added for time-series plots

### 3. `profile.py` — Statistical Summary

Builds a `DatasetProfile` Pydantic model:

- **Dataset-level:** `row_count`, `col_count`, `memory_mb`, `duplicate_row_count`
- **Per-column `ColumnProfile`:**
  - Numeric: `mean`, `median`, `std`, `min`, `max`, `skewness`, `kurtosis`
  - Categorical: `unique_count`, `top_5_values: dict[str, int]`
  - Datetime: `date_min`, `date_max`, `inferred_freq`
- **Section bundles:** groups columns by type for each report section

`DatasetProfile` stored in `st.session_state["profile"]` — navigating sections never re-runs the pipeline.

### Pydantic Models (`models.py`)

```python
class ColumnMeta(BaseModel):
    name: str
    dtype: Literal["numeric", "categorical", "datetime", "boolean", "text"]
    is_id: bool
    is_target: bool
    is_datetime: bool
    role: Literal["dimension", "measure"]
    null_pct: float

class OutlierSummary(BaseModel):
    count: int
    pct: float
    lower_bound: float
    upper_bound: float

class ColumnProfile(BaseModel):
    meta: ColumnMeta
    outlier: OutlierSummary | None = None
    # numeric fields
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None
    # categorical fields
    unique_count: int | None = None
    top_5_values: dict[str, int] | None = None
    # datetime fields
    date_min: str | None = None
    date_max: str | None = None
    inferred_freq: str | None = None

class DatasetProfile(BaseModel):
    dataset_name: str
    row_count: int
    col_count: int
    memory_mb: float
    duplicate_row_count: int
    columns: list[ColumnProfile]

class ExecutiveSummary(BaseModel):
    key_findings: list[str]        # 5-7 bullet discoveries
    data_quality_score: float      # 0–100
    anomalies: list[str]           # notable outliers/patterns
    recommendations: list[str]     # 3-5 next steps
    ml_readiness: str              # one-paragraph ML suitability assessment
```

---

## Charts (`charts.py`)

All return `plotly.graph_objects.Figure`. Rendered via `st.plotly_chart(fig, use_container_width=True)`.

| Section | Chart | Details |
|---|---|---|
| Overview | Null % bar chart | Amber bars, columns on x-axis |
| Overview | Column type pie | Teal/purple/coral/amber slices |
| Distributions | Histogram + KDE per numeric col | Teal fill, purple KDE line |
| Distributions | Top-10 value counts bar (categorical) | Purple bars |
| Correlations | Correlation heatmap | Purple-to-coral diverging scale |
| Correlations | Scatter matrix (top-4 correlated pairs) | Teal markers |
| Outliers | Box plots per numeric col | Coral outlier markers |
| Outliers | Outlier % bar per column | Red gradient |
| Time Series | Line chart over time (if datetime detected) | Teal line, amber anomaly markers |

---

## AI Insights (`insights.py`)

### Per-Section Narratives

One LLM call per section. Input: relevant slice of `DatasetProfile` serialized as JSON. Output: 2-4 sentence narrative string. Cached in `st.session_state["narratives"][section_name]`. On LLM error, renders a styled "AI analysis unavailable" placeholder so the report section still displays its charts and stats.

Uses `client.chat.completions.create` (NOT `.beta.parse`) per CLAUDE.md §4.

Prompt structure:
```
System: You are a senior data analyst. Given the dataset statistics below, write 2-4 sentences
        explaining the key patterns for the {section} section. Use business-friendly language.
        Avoid technical jargon. Respond with plain text only.
User: {DatasetProfile section JSON}
```

### Executive Summary

One LLM call with full `DatasetProfile` JSON. Returns JSON string, manually parsed into `ExecutiveSummary`. Strips markdown fences before parsing.

Prompt instructs: "Respond ONLY with valid JSON. No markdown, no explanation."

Rendered as:
- Key findings → teal cards
- Anomalies → coral cards  
- Recommendations → purple cards
- ML readiness → styled paragraph
- Data quality score → large metric display

All prompts use service-outcome language. Column names and top categorical values included in prompts are passed through `sanitize_for_proxy()` per CLAUDE.md §5 before being forwarded to the API.

---

## ChromaDB (`chroma_store.py`)

After report generation, the executive summary is embedded and stored:

```python
metadata = {
    "dataset_name": str,
    "row_count": int,
    "col_count": int,
    "timestamp": str,   # ISO format
}
document = executive_summary.model_dump_json()
```

Collection: `"eda_reports"`

**Similar Past Reports panel** in AI Insights section:
- Query: `f"{dataset_name} {row_count} rows {col_count} columns"`
- Returns top-3 nearest past summaries with dataset name + timestamp displayed as expandable cards

---

## MCP Server (`mcp_server.py`)

Exposes 3 tools following ps10 pattern:

| Tool | Input | Output |
|---|---|---|
| `profile_dataset` | `csv_content: str`, `dataset_name: str` | `DatasetProfile` as JSON string |
| `get_insights` | `profile_json: str`, `section: str` | Narrative string |
| `search_past_reports` | `query: str` | Top-3 past report summaries as JSON |

---

## Export

Two `st.download_button` elements in the Export section (no server-side file I/O):

- **"Download Report (HTML)"** — all sections + Plotly charts (`fig.to_html(include_plotlyjs="cdn")`) stitched with AI narratives into a single self-contained HTML file
- **"Download CSV Summary"** — `DatasetProfile` stats as a flat CSV

---

## Demo Datasets

### `data/retail_sales.csv` (~500 rows)
Synthetic columns: `order_id`, `order_date`, `product_category`, `product_name`, `quantity`, `unit_price`, `revenue`, `region`, `customer_segment`, `discount_pct`, `returned`

Designed to showcase: datetime time-series, categorical distributions, numeric correlations (price × revenue), outliers in discount/quantity, binary target (`returned`).

### `data/it_service_desk.csv` (~500 rows)
Synthetic columns: `ticket_id`, `created_date`, `priority`, `category`, `department`, `resolution_hours`, `sla_breached`, `assigned_team`, `satisfaction_score`, `reopen_count`

Designed to showcase: SLA compliance patterns, resolution time outliers, department/priority breakdowns, satisfaction score distribution.

---

## Guardrails (`guardrails.py`)

Input validation before pipeline runs:
- File size: reject if >50MB
- Column count: warn if >100 columns (performance)
- Row count: warn if >10,000 rows (truncate to 10k with notice)
- PII flag: warn if column names match common PII patterns (`email`, `phone`, `ssn`, `passport`, `dob`, `address`)

---

## Config (`config.py`)

Follows CLAUDE.md §2 exactly:
- `openai.OpenAI` with `httpx.Client(verify=False)`
- `base_url = OPENAI_BASE_URL.rstrip("/") + "/v1"`
- Default model: `azure/genailab-maas-gpt-4o-mini`
- Model display map: `gpt-4o-mini`, `gpt-4o`, `gpt-35-turbo`

---

## Dependencies (`pyproject.toml`)

```toml
dependencies = [
    "openai>=1.40.0",
    "streamlit>=1.35.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
    "plotly>=5.20.0",
    "pandas>=2.0.0",
    "openpyxl>=3.1.0",       # Excel support
    "scipy>=1.11.0",          # KDE for histograms
    "chromadb>=0.5.0",
    "mcp[cli]>=1.0.0",
]
```

---

## Success Criteria

- Upload a CSV → full report generated in <30 seconds
- All 7 sidebar sections render without error
- GenAI narratives appear in every section
- Executive summary renders with all 5 fields populated
- Past report retrieval returns results after 2+ reports generated
- HTML export opens correctly in browser with all charts visible
- Both demo datasets produce interesting, distinct reports

---

## Compliance Checklist (CLAUDE.md)

- [ ] SSL patch as first lines of `app_mcp.py`
- [ ] `openai.OpenAI` client with `httpx.Client(verify=False)`
- [ ] No `.beta.chat.completions.parse` calls
- [ ] System prompts contain no blocked keywords
- [ ] `sanitize_for_proxy()` applied to user-supplied column names/values
- [ ] `OPENAI_BASE_URL=https://genailab.tcs.in` in `.env.example`
- [ ] Default model: `azure/genailab-maas-gpt-4o-mini`
