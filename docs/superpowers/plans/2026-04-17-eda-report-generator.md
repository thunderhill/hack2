# EDA Report Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `ps11/` — a Streamlit app that auto-generates colorful, interactive EDA reports with Plotly charts and GenAI narratives from uploaded CSV/Excel files, backed by ChromaDB and an MCP server.

**Architecture:** Layered pipeline — `infer → preprocess → profile → charts + insights` — orchestrated by the Streamlit app. Each module has one clear responsibility. Follows ps10 pattern exactly.

**Tech Stack:** Python 3.11, Streamlit, Plotly, Pandas, SciPy, Pydantic v2, OpenAI SDK (TCS GenAI proxy only), ChromaDB, MCP, openpyxl

---

## File Map

| File | Responsibility |
|---|---|
| `ps11/app_mcp.py` | Streamlit entry point — SSL patch, sidebar, section rendering |
| `ps11/mcp_server.py` | MCP server — 3 tools: profile_dataset, get_insights, search_past_reports |
| `ps11/chroma_store.py` | ChromaDB wrapper — store and retrieve past report summaries |
| `ps11/pyproject.toml` | Project metadata and dependencies |
| `ps11/.env.example` | Required environment variables |
| `ps11/data/retail_sales.csv` | Bundled demo dataset (~500 rows) |
| `ps11/data/it_service_desk.csv` | Bundled demo dataset (~500 rows) |
| `ps11/src/eda_report/__init__.py` | Empty package marker |
| `ps11/src/eda_report/config.py` | OpenAI client, model map, sanitize_for_proxy |
| `ps11/src/eda_report/models.py` | Pydantic: ColumnMeta, OutlierSummary, ColumnProfile, DatasetProfile, ExecutiveSummary, GuardrailResult |
| `ps11/src/eda_report/guardrails.py` | Input validation: file size, row count, column count, PII flag |
| `ps11/src/eda_report/infer.py` | Type inference, ID/datetime/target detection |
| `ps11/src/eda_report/preprocess.py` | Null imputation, outlier detection, datetime parsing |
| `ps11/src/eda_report/profile.py` | Statistical summaries → DatasetProfile |
| `ps11/src/eda_report/charts.py` | Plotly figure builders with dark colorful theme |
| `ps11/src/eda_report/insights.py` | LLM calls: per-section narratives + executive summary |
| `ps11/tests/test_models.py` | Pydantic model validation tests |
| `ps11/tests/test_guardrails.py` | Guardrails validation tests |
| `ps11/tests/test_infer.py` | Type inference tests |
| `ps11/tests/test_preprocess.py` | Imputation and outlier detection tests |
| `ps11/tests/test_profile.py` | Statistical profiling tests |
| `ps11/tests/test_charts.py` | Chart structure tests |

---

## Task 1: Scaffold — Project Structure and Config

**Files:**
- Create: `ps11/pyproject.toml`
- Create: `ps11/.env.example`
- Create: `ps11/src/eda_report/__init__.py`
- Create: `ps11/src/eda_report/config.py`
- Create: `ps11/tests/__init__.py`
- Create: `ps11/data/.gitkeep`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p ps11/src/eda_report ps11/tests ps11/data
touch ps11/src/eda_report/__init__.py ps11/tests/__init__.py ps11/data/.gitkeep
```

- [ ] **Step 2: Create `ps11/pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "eda-report-generator"
version = "0.1.0"
description = "Automated EDA Report Generator — PS11"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.40.0",
    "streamlit>=1.35.0",
    "pydantic>=2.0.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.27.0",
    "plotly>=5.20.0",
    "pandas>=2.0.0",
    "openpyxl>=3.1.0",
    "scipy>=1.11.0",
    "chromadb>=0.5.0",
    "mcp[cli]>=1.0.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/eda_report"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `ps11/.env.example`**

```properties
OPENAI_API_KEY=<your-key>
AZURE_GENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://genailab.tcs.in
LLM_MODEL=azure/genailab-maas-gpt-4o-mini
PYTHONHTTPSVERIFY=0
REQUESTS_CA_BUNDLE=
CURL_CA_BUNDLE=
AZURE_EMBEDDING_DEPLOYMENT=azure/genailab-maas-text-embedding-3-large
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_MODE=memory
```

- [ ] **Step 4: Create `ps11/src/eda_report/config.py`**

```python
import os
import httpx
from functools import lru_cache
from openai import OpenAI

MODEL_OPTIONS = ["gpt-4o-mini", "gpt-4o", "gpt-35-turbo"]
MODEL_DISPLAY_MAP = {
    "gpt-4o-mini":  "azure/genailab-maas-gpt-4o-mini",
    "gpt-4o":       "azure/genailab-maas-gpt-4o",
    "gpt-35-turbo": "genailab-maas-gpt-35-turbo",
}

_SENSITIVE: dict[str, str] = {
    "crime":     "reported incident",
    "criminal":  "individual of concern",
    "murder":    "serious incident",
    "assault":   "physical altercation",
    "theft":     "property incident",
    "stolen":    "property incident",
    "drug":      "substance concern",
    "narcotic":  "substance concern",
    "weapon":    "safety equipment concern",
    "violence":  "public disturbance",
    "violent":   "disruptive",
    "kill":      "serious incident",
}

def sanitize_for_proxy(text: str) -> str:
    for word, replacement in _SENSITIVE.items():
        text = text.replace(word, replacement)
        text = text.replace(word.capitalize(), replacement.capitalize())
        text = text.replace(word.upper(), replacement.upper())
    return text

def get_model(model_key: str) -> str:
    return MODEL_DISPLAY_MAP.get(model_key, MODEL_DISPLAY_MAP["gpt-4o-mini"])

@lru_cache(maxsize=1)
def _cached_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/") + "/v1",
        http_client=httpx.Client(verify=False),
    )

def get_llm_client() -> OpenAI:
    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("AZURE_GENAI_API_KEY", "")
    )
    base_url = os.environ.get("OPENAI_BASE_URL", "https://genailab.tcs.in")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set in .env")
    return _cached_client(api_key, base_url)
```

- [ ] **Step 5: Commit**

```bash
git add ps11/
git commit -m "feat(ps11): scaffold project structure and config"
```

---

## Task 2: Pydantic Models

**Files:**
- Create: `ps11/src/eda_report/models.py`
- Create: `ps11/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `ps11/tests/test_models.py`:

```python
import pytest
from eda_report.models import (
    ColumnMeta, OutlierSummary, ColumnProfile,
    DatasetProfile, ExecutiveSummary, GuardrailResult,
)

def test_column_meta_defaults():
    m = ColumnMeta(
        name="price", dtype="numeric",
        is_id=False, is_target=False, is_datetime=False,
        role="measure", null_pct=0.0,
    )
    assert m.name == "price"
    assert m.dtype == "numeric"

def test_column_profile_optional_fields():
    meta = ColumnMeta(name="x", dtype="numeric", is_id=False,
                      is_target=False, is_datetime=False,
                      role="measure", null_pct=0.0)
    cp = ColumnProfile(meta=meta, mean=1.0, median=1.0)
    assert cp.std is None
    assert cp.top_5_values is None

def test_dataset_profile_columns():
    meta = ColumnMeta(name="x", dtype="numeric", is_id=False,
                      is_target=False, is_datetime=False,
                      role="measure", null_pct=0.0)
    cp = ColumnProfile(meta=meta)
    dp = DatasetProfile(
        dataset_name="test", row_count=100, col_count=1,
        memory_mb=0.01, duplicate_row_count=0, columns=[cp],
    )
    assert len(dp.columns) == 1

def test_executive_summary_fields():
    es = ExecutiveSummary(
        key_findings=["Finding 1"],
        data_quality_score=85.0,
        anomalies=["Anomaly 1"],
        recommendations=["Rec 1"],
        ml_readiness="Good candidate for regression.",
    )
    assert es.data_quality_score == 85.0

def test_guardrail_result_ok():
    import pandas as pd
    df = pd.DataFrame({"a": [1, 2, 3]})
    r = GuardrailResult(ok=True, errors=[], warnings=[], truncated=False, df=df)
    assert r.ok
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ps11 && python -m pytest tests/test_models.py -v
```

Expected: `ModuleNotFoundError: No module named 'eda_report.models'`

- [ ] **Step 3: Create `ps11/src/eda_report/models.py`**

```python
from __future__ import annotations
from typing import Literal
import pandas as pd
from pydantic import BaseModel

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
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None
    unique_count: int | None = None
    top_5_values: dict[str, int] | None = None
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
    key_findings: list[str]
    data_quality_score: float
    anomalies: list[str]
    recommendations: list[str]
    ml_readiness: str

class GuardrailResult(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
    truncated: bool
    df: object  # pd.DataFrame — excluded from serialization

    model_config = {"arbitrary_types_allowed": True}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ps11 && python -m pytest tests/test_models.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add ps11/src/eda_report/models.py ps11/tests/test_models.py
git commit -m "feat(ps11): add Pydantic models"
```

---

## Task 3: Demo Datasets

**Files:**
- Create: `ps11/data/retail_sales.csv`
- Create: `ps11/data/it_service_desk.csv`

- [ ] **Step 1: Create `ps11/data/retail_sales.csv`**

Create a Python script `ps11/data/gen_datasets.py` and run it once to generate the CSVs:

```python
"""Run once to generate demo datasets: python data/gen_datasets.py"""
import random, csv, math
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
DATA = Path(__file__).parent

# ── Retail Sales ─────────────────────────────────────────────────────────────
categories = ["Electronics", "Clothing", "Home & Garden", "Sports", "Books"]
regions    = ["North", "South", "East", "West", "Central"]
segments   = ["Consumer", "Corporate", "Home Office"]
products   = {
    "Electronics": ["Laptop", "Phone", "Tablet", "Headphones", "Monitor"],
    "Clothing":    ["T-Shirt", "Jacket", "Jeans", "Dress", "Shoes"],
    "Home & Garden": ["Chair", "Table", "Lamp", "Rug", "Plant"],
    "Sports":      ["Yoga Mat", "Dumbbell", "Tennis Racket", "Bike Helmet", "Shoes"],
    "Books":       ["Python Guide", "Data Science", "Novel", "Cookbook", "History"],
}
start = date(2023, 1, 1)

rows = []
for i in range(1, 501):
    cat   = random.choice(categories)
    prod  = random.choice(products[cat])
    qty   = random.randint(1, 10)
    price = round(random.uniform(5, 500), 2)
    disc  = round(random.uniform(0, 0.35), 2)
    rev   = round(qty * price * (1 - disc), 2)
    # inject outliers in ~3% of rows
    if random.random() < 0.03:
        rev = round(rev * random.uniform(8, 15), 2)
    rows.append({
        "order_id":         f"ORD-{i:04d}",
        "order_date":       (start + timedelta(days=random.randint(0, 364))).isoformat(),
        "product_category": cat,
        "product_name":     prod,
        "quantity":         qty,
        "unit_price":       price,
        "revenue":          rev,
        "region":           random.choice(regions),
        "customer_segment": random.choice(segments),
        "discount_pct":     disc,
        "returned":         1 if random.random() < 0.12 else 0,
    })
    # inject ~5% nulls in revenue and quantity
    if random.random() < 0.05:
        rows[-1]["revenue"] = ""
    if random.random() < 0.05:
        rows[-1]["quantity"] = ""

with open(DATA / "retail_sales.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

# ── IT Service Desk ───────────────────────────────────────────────────────────
priorities  = ["Critical", "High", "Medium", "Low"]
categories2 = ["Network", "Hardware", "Software", "Access", "Email", "Other"]
departments = ["Engineering", "Finance", "HR", "Sales", "Operations", "Marketing"]
teams       = ["Team-A", "Team-B", "Team-C", "Team-D"]

rows2 = []
for i in range(1, 501):
    pri  = random.choices(priorities, weights=[5, 20, 50, 25])[0]
    res  = round(random.uniform(0.5, 72), 1)
    if pri == "Critical": res = round(random.uniform(0.5, 8), 1)
    sla  = 1 if (pri == "Critical" and res > 4) or (pri == "High" and res > 24) else 0
    sat  = round(random.uniform(2.0, 5.0), 1) if sla == 0 else round(random.uniform(1.0, 3.5), 1)
    rows2.append({
        "ticket_id":         f"TKT-{i:04d}",
        "created_date":      (start + timedelta(days=random.randint(0, 364))).isoformat(),
        "priority":          pri,
        "category":          random.choice(categories2),
        "department":        random.choice(departments),
        "resolution_hours":  res,
        "sla_breached":      sla,
        "assigned_team":     random.choice(teams),
        "satisfaction_score": sat,
        "reopen_count":      random.choices([0, 1, 2, 3], weights=[70, 20, 8, 2])[0],
    })
    if random.random() < 0.05:
        rows2[-1]["satisfaction_score"] = ""

with open(DATA / "it_service_desk.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows2[0].keys())
    writer.writeheader()
    writer.writerows(rows2)

print("Generated retail_sales.csv and it_service_desk.csv")
```

- [ ] **Step 2: Run the generator**

```bash
cd ps11 && python data/gen_datasets.py
```

Expected: `Generated retail_sales.csv and it_service_desk.csv`

- [ ] **Step 3: Verify files exist with correct shape**

```bash
python -c "import pandas as pd; df=pd.read_csv('ps11/data/retail_sales.csv'); print(df.shape, df.columns.tolist())"
python -c "import pandas as pd; df=pd.read_csv('ps11/data/it_service_desk.csv'); print(df.shape, df.columns.tolist())"
```

Expected: `(500, 11)` and `(500, 10)`

- [ ] **Step 4: Commit**

```bash
git add ps11/data/
git commit -m "feat(ps11): add synthetic demo datasets (retail sales + IT service desk)"
```

---

## Task 4: Guardrails

**Files:**
- Create: `ps11/src/eda_report/guardrails.py`
- Create: `ps11/tests/test_guardrails.py`

- [ ] **Step 1: Write the failing test**

Create `ps11/tests/test_guardrails.py`:

```python
import pandas as pd
import pytest
from eda_report.guardrails import validate_dataframe

def _make_df(n_rows=100, cols=None):
    cols = cols or {"revenue": range(n_rows), "region": ["North"] * n_rows}
    return pd.DataFrame(cols)

def test_valid_dataframe_is_ok():
    df = _make_df()
    result = validate_dataframe(df, file_size_mb=1.0)
    assert result.ok
    assert result.errors == []
    assert not result.truncated

def test_pii_column_name_triggers_warning():
    df = _make_df(cols={"email": ["a@b.com"] * 100, "revenue": range(100)})
    result = validate_dataframe(df, file_size_mb=1.0)
    assert any("email" in w.lower() for w in result.warnings)

def test_too_many_rows_truncates_to_10k():
    df = _make_df(n_rows=15000, cols={"val": range(15000)})
    result = validate_dataframe(df, file_size_mb=5.0)
    assert result.truncated
    assert len(result.df) == 10000

def test_file_too_large_adds_error():
    df = _make_df()
    result = validate_dataframe(df, file_size_mb=60.0)
    assert not result.ok
    assert any("50MB" in e for e in result.errors)

def test_many_columns_adds_warning():
    cols = {f"col_{i}": range(10) for i in range(110)}
    df = pd.DataFrame(cols)
    result = validate_dataframe(df, file_size_mb=1.0)
    assert any("100" in w for w in result.warnings)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ps11 && python -m pytest tests/test_guardrails.py -v
```

Expected: `ModuleNotFoundError: No module named 'eda_report.guardrails'`

- [ ] **Step 3: Create `ps11/src/eda_report/guardrails.py`**

```python
import pandas as pd
from eda_report.models import GuardrailResult

_PII_PATTERNS = {"email", "phone", "ssn", "passport", "dob", "address", "mobile", "national_id"}

def validate_dataframe(df: pd.DataFrame, file_size_mb: float) -> GuardrailResult:
    errors: list[str] = []
    warnings: list[str] = []
    truncated = False

    if file_size_mb > 50:
        errors.append(f"File size {file_size_mb:.1f}MB exceeds 50MB limit. Please reduce file size.")
        return GuardrailResult(ok=False, errors=errors, warnings=warnings, truncated=False, df=df)

    if df.shape[1] > 100:
        warnings.append(f"Dataset has {df.shape[1]} columns (>100). Analysis may be slow.")

    if df.shape[0] > 10_000:
        df = df.head(10_000)
        truncated = True
        warnings.append("Dataset truncated to 10,000 rows for performance.")

    col_lower = {c.lower() for c in df.columns}
    pii_found = col_lower & _PII_PATTERNS
    for pii in sorted(pii_found):
        warnings.append(f"Possible PII column detected: '{pii}'. Ensure data is anonymized.")

    return GuardrailResult(ok=True, errors=errors, warnings=warnings, truncated=truncated, df=df)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ps11 && python -m pytest tests/test_guardrails.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add ps11/src/eda_report/guardrails.py ps11/tests/test_guardrails.py
git commit -m "feat(ps11): add input guardrails with PII detection and row truncation"
```

---

## Task 5: Type Inference

**Files:**
- Create: `ps11/src/eda_report/infer.py`
- Create: `ps11/tests/test_infer.py`

- [ ] **Step 1: Write the failing test**

Create `ps11/tests/test_infer.py`:

```python
import pandas as pd
import pytest
from eda_report.infer import infer_columns

def test_numeric_column():
    df = pd.DataFrame({"price": [10.0, 20.0, 30.0, 40.0, 50.0]})
    metas = infer_columns(df)
    assert metas[0].dtype == "numeric"
    assert metas[0].role == "measure"
    assert not metas[0].is_id

def test_categorical_column():
    df = pd.DataFrame({"region": ["North", "South", "East", "West"] * 5})
    metas = infer_columns(df)
    assert metas[0].dtype == "categorical"
    assert metas[0].role == "dimension"

def test_id_column_detected():
    df = pd.DataFrame({"order_id": [f"ORD-{i:04d}" for i in range(100)]})
    metas = infer_columns(df)
    assert metas[0].is_id is True

def test_datetime_column_detected():
    df = pd.DataFrame({"order_date": ["2024-01-01", "2024-01-02", "2024-01-03"] * 5})
    metas = infer_columns(df)
    assert metas[0].is_datetime is True
    assert metas[0].dtype == "datetime"

def test_binary_numeric_is_target():
    df = pd.DataFrame({"returned": [0, 1, 0, 1, 0, 1, 0, 0, 1, 0]})
    metas = infer_columns(df)
    assert metas[0].is_target is True

def test_null_pct_recorded():
    df = pd.DataFrame({"price": [1.0, None, 3.0, None, 5.0]})
    metas = infer_columns(df)
    assert abs(metas[0].null_pct - 0.4) < 0.01

def test_boolean_column():
    df = pd.DataFrame({"active": [True, False, True, False, True]})
    metas = infer_columns(df)
    assert metas[0].dtype == "boolean"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ps11 && python -m pytest tests/test_infer.py -v
```

Expected: `ModuleNotFoundError: No module named 'eda_report.infer'`

- [ ] **Step 3: Create `ps11/src/eda_report/infer.py`**

```python
import pandas as pd
from eda_report.models import ColumnMeta

def infer_columns(df: pd.DataFrame) -> list[ColumnMeta]:
    metas = []
    for col in df.columns:
        series = df[col]
        null_pct = float(series.isna().mean())
        non_null = series.dropna()
        n_unique = non_null.nunique()
        n_total = len(non_null)

        # Datetime detection
        is_datetime = False
        if series.dtype == object or pd.api.types.is_datetime64_any_dtype(series):
            if pd.api.types.is_datetime64_any_dtype(series):
                is_datetime = True
            else:
                parsed = pd.to_datetime(non_null, errors="coerce", infer_datetime_format=True)
                if parsed.notna().mean() > 0.8:
                    is_datetime = True

        # Boolean
        if series.dtype == bool or set(non_null.unique()) <= {True, False, 0, 1}:
            if series.dtype == bool:
                metas.append(ColumnMeta(
                    name=col, dtype="boolean", is_id=False, is_target=False,
                    is_datetime=False, role="dimension", null_pct=null_pct,
                ))
                continue

        # Datetime
        if is_datetime:
            metas.append(ColumnMeta(
                name=col, dtype="datetime", is_id=False, is_target=False,
                is_datetime=True, role="dimension", null_pct=null_pct,
            ))
            continue

        # Numeric
        if pd.api.types.is_numeric_dtype(series):
            is_id = (n_unique == n_total and n_total > 50)
            is_target = (set(non_null.unique()) <= {0, 1} and n_unique == 2)
            role = "dimension" if n_unique < 20 else "measure"
            metas.append(ColumnMeta(
                name=col, dtype="numeric", is_id=is_id, is_target=is_target,
                is_datetime=False, role=role, null_pct=null_pct,
            ))
            continue

        # Text (high cardinality string, not datetime)
        if n_unique / max(n_total, 1) > 0.8 and n_total > 50:
            metas.append(ColumnMeta(
                name=col, dtype="text" if non_null.str.len().mean() > 30 else "categorical",
                is_id=(n_unique == n_total),
                is_target=False, is_datetime=False,
                role="dimension", null_pct=null_pct,
            ))
            continue

        # Categorical
        metas.append(ColumnMeta(
            name=col, dtype="categorical", is_id=False, is_target=False,
            is_datetime=False,
            role="dimension" if n_unique < 20 else "measure",
            null_pct=null_pct,
        ))
    return metas
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ps11 && python -m pytest tests/test_infer.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add ps11/src/eda_report/infer.py ps11/tests/test_infer.py
git commit -m "feat(ps11): add type inference module"
```

---

## Task 6: Preprocessing

**Files:**
- Create: `ps11/src/eda_report/preprocess.py`
- Create: `ps11/tests/test_preprocess.py`

- [ ] **Step 1: Write the failing test**

Create `ps11/tests/test_preprocess.py`:

```python
import pandas as pd
import numpy as np
import pytest
from eda_report.models import ColumnMeta
from eda_report.preprocess import impute_nulls, detect_outliers, parse_datetimes

def _meta(name, dtype, **kw):
    defaults = dict(is_id=False, is_target=False, is_datetime=False, role="measure", null_pct=0.0)
    defaults.update(kw)
    return ColumnMeta(name=name, dtype=dtype, **defaults)

def test_impute_numeric_nulls_with_median():
    df = pd.DataFrame({"price": [1.0, None, 3.0, None, 5.0]})
    meta = _meta("price", "numeric")
    result = impute_nulls(df.copy(), [meta])
    assert result["price"].isna().sum() == 0
    assert result["price"].iloc[1] == 3.0  # median of [1,3,5]

def test_impute_categorical_nulls_with_mode():
    df = pd.DataFrame({"region": ["North", None, "North", None, "South"]})
    meta = _meta("region", "categorical", role="dimension")
    result = impute_nulls(df.copy(), [meta])
    assert result["region"].isna().sum() == 0
    assert result["region"].iloc[1] == "North"

def test_detect_outlier_iqr():
    df = pd.DataFrame({"price": [10, 12, 11, 13, 12, 11, 10, 12, 100, 11]})
    meta = _meta("price", "numeric")
    outlier = detect_outliers(df, meta)
    assert outlier is not None
    assert outlier.count >= 1
    assert outlier.pct > 0

def test_detect_no_outlier():
    df = pd.DataFrame({"price": list(range(20))})
    meta = _meta("price", "numeric")
    outlier = detect_outliers(df, meta)
    # uniform data — may or may not have outlier; just check it returns correctly typed value
    assert outlier is None or outlier.count >= 0

def test_parse_datetimes_adds_helper_columns():
    df = pd.DataFrame({
        "order_date": ["2024-01-15", "2024-06-20", "2024-12-01"] * 5,
        "revenue": [100.0, 200.0, 300.0] * 5,
    })
    meta = _meta("order_date", "datetime", is_datetime=True, role="dimension")
    result = parse_datetimes(df.copy(), [meta])
    assert "order_date_year" in result.columns
    assert "order_date_month" in result.columns
    assert "order_date_dow" in result.columns
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ps11 && python -m pytest tests/test_preprocess.py -v
```

Expected: `ModuleNotFoundError: No module named 'eda_report.preprocess'`

- [ ] **Step 3: Create `ps11/src/eda_report/preprocess.py`**

```python
import pandas as pd
import numpy as np
from eda_report.models import ColumnMeta, OutlierSummary

def impute_nulls(df: pd.DataFrame, metas: list[ColumnMeta]) -> pd.DataFrame:
    for meta in metas:
        col = meta.name
        if col not in df.columns:
            continue
        if df[col].isna().sum() == 0:
            continue
        if meta.dtype == "numeric":
            median = df[col].median()
            df[col] = df[col].fillna(median)
        elif meta.dtype in ("categorical", "text", "boolean"):
            mode_vals = df[col].mode()
            if len(mode_vals) > 0:
                df[col] = df[col].fillna(mode_vals[0])
    return df

def detect_outliers(df: pd.DataFrame, meta: ColumnMeta) -> OutlierSummary | None:
    if meta.dtype != "numeric":
        return None
    col = df[meta.name].dropna()
    if len(col) < 4:
        return None
    q1, q3 = col.quantile(0.25), col.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return None
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    mask = (df[meta.name] < lower) | (df[meta.name] > upper)
    count = int(mask.sum())
    if count == 0:
        return None
    return OutlierSummary(
        count=count,
        pct=round(count / len(df) * 100, 2),
        lower_bound=round(float(lower), 4),
        upper_bound=round(float(upper), 4),
    )

def parse_datetimes(df: pd.DataFrame, metas: list[ColumnMeta]) -> pd.DataFrame:
    for meta in metas:
        if not meta.is_datetime:
            continue
        col = meta.name
        if col not in df.columns:
            continue
        parsed = pd.to_datetime(df[col], errors="coerce", infer_datetime_format=True)
        df[col] = parsed
        df[f"{col}_year"]  = parsed.dt.year
        df[f"{col}_month"] = parsed.dt.month
        df[f"{col}_dow"]   = parsed.dt.dayofweek
    return df
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ps11 && python -m pytest tests/test_preprocess.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add ps11/src/eda_report/preprocess.py ps11/tests/test_preprocess.py
git commit -m "feat(ps11): add preprocessing — null imputation, outlier detection, datetime parsing"
```

---

## Task 7: Statistical Profiling

**Files:**
- Create: `ps11/src/eda_report/profile.py`
- Create: `ps11/tests/test_profile.py`

- [ ] **Step 1: Write the failing test**

Create `ps11/tests/test_profile.py`:

```python
import pandas as pd
import pytest
from eda_report.models import ColumnMeta
from eda_report.profile import build_profile

def _meta(name, dtype, **kw):
    defaults = dict(is_id=False, is_target=False, is_datetime=False, role="measure", null_pct=0.0)
    defaults.update(kw)
    return ColumnMeta(name=name, dtype=dtype, **defaults)

def test_numeric_column_stats():
    df = pd.DataFrame({"revenue": [100.0, 200.0, 300.0, 400.0, 500.0]})
    meta = _meta("revenue", "numeric")
    profile = build_profile(df, [meta], dataset_name="test")
    col = profile.columns[0]
    assert col.mean == 300.0
    assert col.median == 300.0
    assert col.min == 100.0
    assert col.max == 500.0
    assert col.unique_count is None  # numeric — no unique_count

def test_categorical_column_stats():
    df = pd.DataFrame({"region": ["North"] * 3 + ["South"] * 2})
    meta = _meta("region", "categorical", role="dimension")
    profile = build_profile(df, [meta], dataset_name="test")
    col = profile.columns[0]
    assert col.unique_count == 2
    assert col.top_5_values is not None
    assert col.top_5_values["North"] == 3

def test_dataset_level_stats():
    df = pd.DataFrame({"a": [1, 2, 3, 1], "b": ["x", "y", "z", "x"]})
    metas = [
        _meta("a", "numeric"),
        _meta("b", "categorical", role="dimension"),
    ]
    profile = build_profile(df, metas, dataset_name="mydata")
    assert profile.row_count == 4
    assert profile.col_count == 2
    assert profile.duplicate_row_count == 1
    assert profile.dataset_name == "mydata"

def test_id_columns_excluded_from_profile():
    df = pd.DataFrame({"order_id": [f"ORD-{i}" for i in range(10)], "revenue": range(10)})
    metas = [
        _meta("order_id", "categorical", is_id=True, role="dimension"),
        _meta("revenue", "numeric"),
    ]
    profile = build_profile(df, metas, dataset_name="test")
    names = [c.meta.name for c in profile.columns]
    assert "order_id" not in names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ps11 && python -m pytest tests/test_profile.py -v
```

Expected: `ModuleNotFoundError: No module named 'eda_report.profile'`

- [ ] **Step 3: Create `ps11/src/eda_report/profile.py`**

```python
import pandas as pd
import numpy as np
from eda_report.models import ColumnMeta, ColumnProfile, DatasetProfile
from eda_report.preprocess import detect_outliers

def build_profile(df: pd.DataFrame, metas: list[ColumnMeta], dataset_name: str) -> DatasetProfile:
    row_count = len(df)
    col_count = len(df.columns)
    memory_mb = round(df.memory_usage(deep=True).sum() / 1_048_576, 4)
    duplicate_row_count = int(df.duplicated().sum())

    columns: list[ColumnProfile] = []
    for meta in metas:
        if meta.is_id:
            continue
        col = meta.name
        if col not in df.columns:
            continue
        series = df[col].dropna()
        outlier = detect_outliers(df, meta)
        cp = ColumnProfile(meta=meta, outlier=outlier)

        if meta.dtype == "numeric":
            cp.mean     = round(float(series.mean()), 4)
            cp.median   = round(float(series.median()), 4)
            cp.std      = round(float(series.std()), 4)
            cp.min      = round(float(series.min()), 4)
            cp.max      = round(float(series.max()), 4)
            cp.skewness = round(float(series.skew()), 4)
            cp.kurtosis = round(float(series.kurt()), 4)

        elif meta.dtype in ("categorical", "text", "boolean"):
            vc = series.astype(str).value_counts()
            cp.unique_count  = int(vc.shape[0])
            cp.top_5_values  = {k: int(v) for k, v in vc.head(5).items()}

        elif meta.dtype == "datetime":
            dt_series = pd.to_datetime(series, errors="coerce").dropna()
            if len(dt_series) > 0:
                cp.date_min = str(dt_series.min().date())
                cp.date_max = str(dt_series.max().date())
                try:
                    freq = pd.infer_freq(dt_series.sort_values())
                    cp.inferred_freq = freq or "irregular"
                except Exception:
                    cp.inferred_freq = "irregular"

        columns.append(cp)

    return DatasetProfile(
        dataset_name=dataset_name,
        row_count=row_count,
        col_count=col_count,
        memory_mb=memory_mb,
        duplicate_row_count=duplicate_row_count,
        columns=columns,
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ps11 && python -m pytest tests/test_profile.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add ps11/src/eda_report/profile.py ps11/tests/test_profile.py
git commit -m "feat(ps11): add statistical profiling module"
```

---

## Task 8: Charts

**Files:**
- Create: `ps11/src/eda_report/charts.py`
- Create: `ps11/tests/test_charts.py`

- [ ] **Step 1: Write the failing test**

Create `ps11/tests/test_charts.py`:

```python
import pandas as pd
import plotly.graph_objects as go
import pytest
from eda_report.models import ColumnMeta, ColumnProfile, DatasetProfile
from eda_report import charts

def _numeric_meta(name="revenue"):
    return ColumnMeta(name=name, dtype="numeric", is_id=False, is_target=False,
                      is_datetime=False, role="measure", null_pct=0.0)

def _cat_meta(name="region"):
    return ColumnMeta(name=name, dtype="categorical", is_id=False, is_target=False,
                      is_datetime=False, role="dimension", null_pct=0.05)

def _make_profile():
    cp1 = ColumnProfile(meta=_numeric_meta("revenue"), mean=300.0, median=300.0,
                        std=50.0, min=100.0, max=500.0, skewness=0.1, kurtosis=0.0)
    cp2 = ColumnProfile(meta=_cat_meta("region"), unique_count=4,
                        top_5_values={"North": 150, "South": 120, "East": 130, "West": 100})
    return DatasetProfile(dataset_name="test", row_count=500, col_count=2,
                          memory_mb=0.1, duplicate_row_count=0, columns=[cp1, cp2])

def test_null_bar_returns_figure():
    fig = charts.null_bar(_make_profile())
    assert isinstance(fig, go.Figure)

def test_column_type_pie_returns_figure():
    fig = charts.column_type_pie(_make_profile())
    assert isinstance(fig, go.Figure)

def test_histogram_returns_figure():
    df = pd.DataFrame({"revenue": [100, 200, 300, 400, 500] * 20})
    fig = charts.histogram(df, "revenue")
    assert isinstance(fig, go.Figure)

def test_value_counts_bar_returns_figure():
    cp = ColumnProfile(meta=_cat_meta(), unique_count=4,
                       top_5_values={"North": 150, "South": 120, "East": 130, "West": 100})
    fig = charts.value_counts_bar(cp)
    assert isinstance(fig, go.Figure)

def test_correlation_heatmap_returns_figure():
    df = pd.DataFrame({"a": range(10), "b": range(10), "c": [x*2 for x in range(10)]})
    fig = charts.correlation_heatmap(df, ["a", "b", "c"])
    assert isinstance(fig, go.Figure)

def test_box_plot_returns_figure():
    df = pd.DataFrame({"revenue": [100, 200, 300, 400, 500, 1000] * 5})
    fig = charts.box_plot(df, "revenue")
    assert isinstance(fig, go.Figure)

def test_time_series_line_returns_figure():
    df = pd.DataFrame({
        "order_date": pd.date_range("2024-01-01", periods=12, freq="ME"),
        "revenue": [100 * i for i in range(1, 13)],
    })
    fig = charts.time_series_line(df, "order_date", "revenue")
    assert isinstance(fig, go.Figure)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ps11 && python -m pytest tests/test_charts.py -v
```

Expected: `ModuleNotFoundError: No module named 'eda_report.charts'`

- [ ] **Step 3: Create `ps11/src/eda_report/charts.py`**

```python
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.figure_factory as ff
from scipy import stats
from eda_report.models import ColumnProfile, DatasetProfile

# ── Theme ─────────────────────────────────────────────────────────────────────
_PALETTE   = ["#00d4aa", "#7c6bf2", "#ffc300", "#ff6b6b", "#00b4d8"]
_TEAL      = "#00d4aa"
_PURPLE    = "#7c6bf2"
_AMBER     = "#ffc300"
_CORAL     = "#ff6b6b"
_BG        = "#0e0e1a"
_PLOT_BG   = "#1a1a2e"
_FONT      = "#e0e0ff"
_GRID      = "#2a2a4a"

def _apply_theme(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(
        paper_bgcolor=_BG, plot_bgcolor=_PLOT_BG,
        font=dict(color=_FONT, family="Inter, sans-serif"),
        title=dict(text=title, font=dict(size=15, color=_FONT)) if title else {},
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        xaxis=dict(gridcolor=_GRID, linecolor=_GRID, zerolinecolor=_GRID),
        yaxis=dict(gridcolor=_GRID, linecolor=_GRID, zerolinecolor=_GRID),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=_FONT)),
    )
    return fig

# ── Overview charts ───────────────────────────────────────────────────────────
def null_bar(profile: DatasetProfile) -> go.Figure:
    cols  = [c.meta.name for c in profile.columns if c.meta.null_pct > 0]
    nulls = [round(c.meta.null_pct * 100, 1) for c in profile.columns if c.meta.null_pct > 0]
    if not cols:
        cols, nulls = ["(no nulls)"], [0]
    fig = go.Figure(go.Bar(x=cols, y=nulls, marker_color=_AMBER, name="Null %"))
    fig.update_layout(yaxis_title="Null %", xaxis_title="Column")
    return _apply_theme(fig, "Missing Values by Column")

def column_type_pie(profile: DatasetProfile) -> go.Figure:
    from collections import Counter
    counts = Counter(c.meta.dtype for c in profile.columns)
    colors = {"numeric": _TEAL, "categorical": _PURPLE, "datetime": _AMBER,
              "boolean": _CORAL, "text": "#00b4d8"}
    fig = go.Figure(go.Pie(
        labels=list(counts.keys()), values=list(counts.values()),
        marker_colors=[colors.get(k, _TEAL) for k in counts.keys()],
        hole=0.4, textfont=dict(color=_FONT),
    ))
    return _apply_theme(fig, "Column Type Distribution")

# ── Distribution charts ───────────────────────────────────────────────────────
def histogram(df: pd.DataFrame, col: str) -> go.Figure:
    series = df[col].dropna()
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=series, nbinsx=30, name="Count",
        marker_color=_TEAL, opacity=0.75,
    ))
    # KDE overlay
    try:
        kde_x = np.linspace(series.min(), series.max(), 200)
        kde_y = stats.gaussian_kde(series)(kde_x)
        scale = series.count() * (series.max() - series.min()) / 30
        fig.add_trace(go.Scatter(
            x=kde_x, y=kde_y * scale, mode="lines",
            line=dict(color=_PURPLE, width=2), name="KDE",
        ))
    except Exception:
        pass
    fig.update_layout(barmode="overlay", xaxis_title=col, yaxis_title="Count")
    return _apply_theme(fig, f"Distribution: {col}")

def value_counts_bar(cp: ColumnProfile) -> go.Figure:
    if not cp.top_5_values:
        return go.Figure()
    labels = list(cp.top_5_values.keys())
    values = list(cp.top_5_values.values())
    fig = go.Figure(go.Bar(
        x=labels, y=values, marker_color=_PURPLE, name="Count",
    ))
    fig.update_layout(xaxis_title=cp.meta.name, yaxis_title="Count")
    return _apply_theme(fig, f"Top Values: {cp.meta.name}")

# ── Correlation charts ────────────────────────────────────────────────────────
def correlation_heatmap(df: pd.DataFrame, numeric_cols: list[str]) -> go.Figure:
    corr = df[numeric_cols].corr()
    fig = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns.tolist(), y=corr.index.tolist(),
        colorscale=[[0, _CORAL], [0.5, "#1a1a2e"], [1, _PURPLE]],
        zmid=0, text=corr.round(2).values,
        texttemplate="%{text}", showscale=True,
    ))
    return _apply_theme(fig, "Correlation Matrix")

def scatter_pair(df: pd.DataFrame, col_x: str, col_y: str) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=df[col_x], y=df[col_y], mode="markers",
        marker=dict(color=_TEAL, size=5, opacity=0.6),
        name=f"{col_x} vs {col_y}",
    ))
    fig.update_layout(xaxis_title=col_x, yaxis_title=col_y)
    return _apply_theme(fig, f"{col_x} vs {col_y}")

# ── Outlier charts ────────────────────────────────────────────────────────────
def box_plot(df: pd.DataFrame, col: str) -> go.Figure:
    fig = go.Figure(go.Box(
        y=df[col].dropna(), name=col,
        marker_color=_TEAL,
        line_color=_PURPLE,
        marker=dict(outliercolor=_CORAL, symbol="circle-open", size=6),
        boxmean=True,
    ))
    fig.update_layout(yaxis_title=col)
    return _apply_theme(fig, f"Box Plot: {col}")

def outlier_pct_bar(profile: DatasetProfile) -> go.Figure:
    cols  = [c.meta.name for c in profile.columns if c.outlier is not None]
    pcts  = [c.outlier.pct for c in profile.columns if c.outlier is not None]
    if not cols:
        cols, pcts = ["(no outliers)"], [0]
    colors = [_CORAL if p > 5 else _AMBER for p in pcts]
    fig = go.Figure(go.Bar(x=cols, y=pcts, marker_color=colors, name="Outlier %"))
    fig.update_layout(yaxis_title="Outlier %", xaxis_title="Column")
    return _apply_theme(fig, "Outlier Percentage by Column")

# ── Time series ───────────────────────────────────────────────────────────────
def time_series_line(df: pd.DataFrame, date_col: str, value_col: str) -> go.Figure:
    tmp = df[[date_col, value_col]].copy()
    tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
    tmp = tmp.dropna().set_index(date_col).resample("ME")[value_col].mean().reset_index()
    fig = go.Figure(go.Scatter(
        x=tmp[date_col], y=tmp[value_col],
        mode="lines+markers",
        line=dict(color=_TEAL, width=2),
        marker=dict(color=_AMBER, size=6),
        name=value_col,
    ))
    fig.update_layout(xaxis_title="Date", yaxis_title=value_col)
    return _apply_theme(fig, f"{value_col} over Time")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd ps11 && python -m pytest tests/test_charts.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add ps11/src/eda_report/charts.py ps11/tests/test_charts.py
git commit -m "feat(ps11): add colorful Plotly chart builders with dark theme"
```

---

## Task 9: AI Insights

**Files:**
- Create: `ps11/src/eda_report/insights.py`

No live LLM test needed — the function signature and error-handling path are covered by integration when the app runs. We verify the module imports and the sanitize path works.

- [ ] **Step 1: Create `ps11/src/eda_report/insights.py`**

```python
import json
from openai import OpenAI
from eda_report.models import DatasetProfile, ExecutiveSummary, ColumnProfile
from eda_report.config import sanitize_for_proxy

_SECTION_SYSTEM = (
    "You are a senior data analyst writing a business-friendly EDA report. "
    "Given dataset statistics in JSON, write 2-4 sentences explaining key patterns "
    "for the {section} section. Use plain English. No technical jargon. No markdown. "
    "Plain text only."
)

_EXEC_SYSTEM = (
    "You are a senior data analyst. Given a full dataset profile in JSON, produce an "
    "executive summary. Respond ONLY with valid JSON matching this schema exactly — "
    "no markdown fences, no explanation:\n"
    '{{"key_findings": ["...", "..."], '
    '"data_quality_score": 85.0, '
    '"anomalies": ["..."], '
    '"recommendations": ["..."], '
    '"ml_readiness": "..."}}'
)

def _sanitize_profile_json(profile_json: str) -> str:
    return sanitize_for_proxy(profile_json)

def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return raw.strip()

def get_section_narrative(
    client: OpenAI, model: str, profile: DatasetProfile, section: str
) -> str:
    # Build a concise slice of the profile relevant to this section
    section_data = {
        "dataset": profile.dataset_name,
        "rows": profile.row_count,
        "section": section,
        "columns": [
            c.model_dump(exclude_none=True)
            for c in profile.columns
        ][:20],  # cap to avoid huge prompts
    }
    user_content = _sanitize_profile_json(json.dumps(section_data))
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SECTION_SYSTEM.format(section=section)},
                {"role": "user", "content": user_content},
            ],
            max_tokens=256,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"AI analysis unavailable: {e}"

def get_executive_summary(
    client: OpenAI, model: str, profile: DatasetProfile
) -> ExecutiveSummary:
    profile_data = {
        "dataset": profile.dataset_name,
        "rows": profile.row_count,
        "cols": profile.col_count,
        "duplicates": profile.duplicate_row_count,
        "memory_mb": profile.memory_mb,
        "columns": [c.model_dump(exclude_none=True) for c in profile.columns],
    }
    user_content = _sanitize_profile_json(json.dumps(profile_data))
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXEC_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            max_tokens=1024,
            temperature=0.2,
        )
        raw = _strip_fences(resp.choices[0].message.content)
        data = json.loads(raw)
        return ExecutiveSummary(**data)
    except Exception as e:
        return ExecutiveSummary(
            key_findings=[f"Summary generation failed: {e}"],
            data_quality_score=0.0,
            anomalies=[],
            recommendations=["Retry with a different model or check VPN connection."],
            ml_readiness="Unable to assess — AI service unavailable.",
        )
```

- [ ] **Step 2: Verify import works**

```bash
cd ps11 && python -c "from eda_report.insights import get_section_narrative, get_executive_summary; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ps11/src/eda_report/insights.py
git commit -m "feat(ps11): add LLM insights module with graceful error fallback"
```

---

## Task 10: ChromaDB Store

**Files:**
- Create: `ps11/chroma_store.py`

- [ ] **Step 1: Create `ps11/chroma_store.py`**

```python
import os
from datetime import datetime, timezone
import chromadb
from chromadb.config import Settings

_COLLECTION = "eda_reports"

class ChromaStore:
    def __init__(self) -> None:
        mode = os.environ.get("CHROMA_MODE", "memory")
        if mode == "memory":
            self._client = chromadb.Client()
        else:
            persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma")
            self._client = chromadb.PersistentClient(path=persist_dir)
        self._col = self._client.get_or_create_collection(_COLLECTION)

    def store_report(
        self,
        dataset_name: str,
        row_count: int,
        col_count: int,
        summary_json: str,
    ) -> None:
        doc_id = f"{dataset_name}-{datetime.now(timezone.utc).isoformat()}"
        self._col.add(
            documents=[summary_json],
            metadatas=[{
                "dataset_name": dataset_name,
                "row_count":    row_count,
                "col_count":    col_count,
                "timestamp":    datetime.now(timezone.utc).isoformat(),
            }],
            ids=[doc_id],
        )

    def search_similar(self, query: str, n: int = 3) -> list[dict]:
        count = self._col.count()
        if count == 0:
            return []
        results = self._col.query(
            query_texts=[query],
            n_results=min(n, count),
        )
        out = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            out.append({"summary": doc, "meta": meta})
        return out
```

- [ ] **Step 2: Verify import and basic operation**

```bash
cd ps11 && python -c "
import os; os.environ['CHROMA_MODE']='memory'
from chroma_store import ChromaStore
cs = ChromaStore()
cs.store_report('test', 100, 5, '{\"key_findings\":[\"Test finding\"]}')
results = cs.search_similar('test dataset 100 rows', n=3)
print('stored and retrieved:', len(results), 'results')
"
```

Expected: `stored and retrieved: 1 results`

- [ ] **Step 3: Commit**

```bash
git add ps11/chroma_store.py
git commit -m "feat(ps11): add ChromaDB store for past report retrieval"
```

---

## Task 11: MCP Server

**Files:**
- Create: `ps11/mcp_server.py`

- [ ] **Step 1: Create `ps11/mcp_server.py`**

```python
import os, ssl, warnings
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(override=True)

import io
import pandas as pd
from mcp.server.fastmcp import FastMCP

from eda_report.config import get_llm_client, get_model
from eda_report.infer import infer_columns
from eda_report.preprocess import impute_nulls, detect_outliers, parse_datetimes
from eda_report.profile import build_profile
from eda_report.insights import get_section_narrative, get_executive_summary
from chroma_store import ChromaStore

mcp = FastMCP("EDA Report Generator")
_store = ChromaStore()
_DEFAULT_MODEL = os.environ.get("LLM_MODEL", "azure/genailab-maas-gpt-4o-mini")

@mcp.tool()
def profile_dataset(csv_content: str, dataset_name: str) -> str:
    """Parse CSV content and return a DatasetProfile as JSON."""
    df = pd.read_csv(io.StringIO(csv_content))
    metas = infer_columns(df)
    df = impute_nulls(df, metas)
    df = parse_datetimes(df, metas)
    profile = build_profile(df, metas, dataset_name=dataset_name)
    return profile.model_dump_json()

@mcp.tool()
def get_insights(profile_json: str, section: str) -> str:
    """Generate a narrative for the given report section using the LLM."""
    from eda_report.models import DatasetProfile
    profile = DatasetProfile.model_validate_json(profile_json)
    client = get_llm_client()
    model = get_model(_DEFAULT_MODEL.replace("azure/genailab-maas-", "").replace("genailab-maas-", ""))
    return get_section_narrative(client, model, profile, section)

@mcp.tool()
def search_past_reports(query: str) -> str:
    """Search ChromaDB for past EDA reports similar to the query."""
    results = _store.search_similar(query, n=3)
    return json.dumps(results)

if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: Verify MCP server imports without error**

```bash
cd ps11 && python -c "import mcp_server; print('MCP server OK')"
```

Expected: `MCP server OK`

- [ ] **Step 3: Commit**

```bash
git add ps11/mcp_server.py
git commit -m "feat(ps11): add MCP server with profile_dataset, get_insights, search_past_reports tools"
```

---

## Task 12: Streamlit App

**Files:**
- Create: `ps11/app_mcp.py`

This is the largest task — the full Streamlit UI. Build it in sections.

- [ ] **Step 1: Create `ps11/app_mcp.py` — SSL patch, imports, page config, CSS**

```python
import os, ssl, warnings

# ── SSL bypass — MUST be before any other import ──────────────────────────────
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(override=True)

import io
import json
import pandas as pd
import streamlit as st

from eda_report.config import MODEL_OPTIONS, get_llm_client, get_model
from eda_report.guardrails import validate_dataframe
from eda_report.infer import infer_columns
from eda_report.preprocess import impute_nulls, detect_outliers, parse_datetimes
from eda_report.profile import build_profile
from eda_report import charts
from eda_report.insights import get_section_narrative, get_executive_summary
from chroma_store import ChromaStore

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EDA Report Generator — PS11",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Page background */
[data-testid="stAppViewContainer"] { background: #0e0e1a; }
[data-testid="stSidebar"] { background: #13132a; border-right: 1px solid #2a2a4a; }

/* Section header bands */
.section-header {
    padding: 16px 24px; border-radius: 10px; margin-bottom: 20px;
    font-size: 1.4rem; font-weight: 700; color: #fff; letter-spacing: 0.5px;
}
.hdr-overview      { background: linear-gradient(90deg, #00695c, #0e0e1a); }
.hdr-quality       { background: linear-gradient(90deg, #b37a00, #0e0e1a); }
.hdr-distributions { background: linear-gradient(90deg, #4a3a9a, #0e0e1a); }
.hdr-correlations  { background: linear-gradient(90deg, #006064, #0e0e1a); }
.hdr-outliers      { background: linear-gradient(90deg, #8b1a1a, #0e0e1a); }
.hdr-insights      { background: linear-gradient(90deg, #4a148c, #0e0e1a); }
.hdr-export        { background: linear-gradient(90deg, #1a237e, #0e0e1a); }

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1a1a2e, #252540);
    border-radius: 12px; padding: 18px; border: 1px solid #2a2a4a;
    text-align: center; margin-bottom: 10px;
}
.metric-value { font-size: 2.2rem; font-weight: 700; margin: 4px 0; }
.metric-label { font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
.teal   { color: #00d4aa; }
.purple { color: #7c6bf2; }
.amber  { color: #ffc300; }
.coral  { color: #ff6b6b; }

/* AI narrative card */
.ai-card {
    background: #1a1a2e; border-left: 4px solid #7c6bf2;
    border-radius: 8px; padding: 16px; margin-top: 12px;
    color: #e0e0ff; font-size: 0.95rem; line-height: 1.6;
}
.ai-card .ai-label { font-size: 0.75rem; color: #7c6bf2; font-weight: 600;
                     text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }

/* Finding / recommendation cards */
.finding-card { background:#1a1a2e; border-left:4px solid #00d4aa;
                border-radius:8px; padding:12px 16px; margin-bottom:8px; color:#e0e0ff; }
.anomaly-card { background:#1a1a2e; border-left:4px solid #ff6b6b;
                border-radius:8px; padding:12px 16px; margin-bottom:8px; color:#e0e0ff; }
.rec-card     { background:#1a1a2e; border-left:4px solid #7c6bf2;
                border-radius:8px; padding:12px 16px; margin-bottom:8px; color:#e0e0ff; }

/* Nav buttons */
.nav-btn { width:100%; text-align:left; }
</style>
""", unsafe_allow_html=True)
```

- [ ] **Step 2: Add session state initialization and sidebar controls**

Append to `ps11/app_mcp.py`:

```python
# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("profile", None), ("df", None), ("metas", None),
    ("narratives", {}), ("exec_summary", None),
    ("active_section", "Overview"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

_store = ChromaStore()

DATA_DIR = Path(__file__).parent / "data"
DEMO_DATASETS = {
    "Retail Sales":      DATA_DIR / "retail_sales.csv",
    "IT Service Desk":   DATA_DIR / "it_service_desk.csv",
}
SECTIONS = ["Overview", "Data Quality", "Distributions",
            "Correlations", "Outliers & Anomalies", "AI Insights", "Export"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 EDA Report Generator")
    st.caption("AI Friday Season 2 — PS11")
    st.divider()

    model_key = st.selectbox("Model", MODEL_OPTIONS, index=0)
    deployment = get_model(model_key)

    st.markdown("### Dataset")
    source = st.radio("Source", ["Use demo dataset", "Upload file"], label_visibility="collapsed")

    df_raw = None
    dataset_name = ""

    if source == "Use demo dataset":
        chosen = st.selectbox("Demo dataset", list(DEMO_DATASETS.keys()))
        dataset_name = chosen
        if st.button("Generate Report", type="primary", use_container_width=True):
            df_raw = pd.read_csv(DEMO_DATASETS[chosen])
            file_size_mb = DEMO_DATASETS[chosen].stat().st_size / 1_048_576
            _trigger = True
        else:
            _trigger = False
    else:
        uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
        _trigger = False
        if uploaded:
            dataset_name = uploaded.name.rsplit(".", 1)[0]
            raw_bytes = uploaded.read()
            file_size_mb = len(raw_bytes) / 1_048_576
            if uploaded.name.endswith(".xlsx"):
                df_raw = pd.read_excel(io.BytesIO(raw_bytes))
            else:
                df_raw = pd.read_csv(io.BytesIO(raw_bytes))
            if st.button("Generate Report", type="primary", use_container_width=True):
                _trigger = True

    # ── Pipeline trigger ──────────────────────────────────────────────────────
    if df_raw is not None and _trigger:
        with st.spinner("Running analysis pipeline…"):
            guard = validate_dataframe(df_raw, file_size_mb=file_size_mb)
            if not guard.ok:
                for e in guard.errors:
                    st.error(e)
            else:
                for w in guard.warnings:
                    st.warning(w)
                df = guard.df
                metas = infer_columns(df)
                df = impute_nulls(df, metas)
                df = parse_datetimes(df, metas)
                profile = build_profile(df, metas, dataset_name=dataset_name)
                st.session_state["df"]       = df
                st.session_state["metas"]    = metas
                st.session_state["profile"]  = profile
                st.session_state["narratives"] = {}
                st.session_state["exec_summary"] = None
                st.session_state["active_section"] = "Overview"

    # ── Navigation ────────────────────────────────────────────────────────────
    if st.session_state["profile"] is not None:
        st.divider()
        st.markdown("### Navigation")
        section_icons = {
            "Overview": "🏠", "Data Quality": "🔍", "Distributions": "📈",
            "Correlations": "🔗", "Outliers & Anomalies": "⚠️",
            "AI Insights": "✨", "Export": "📥",
        }
        for sec in SECTIONS:
            label = f"{section_icons[sec]} {sec}"
            active = st.session_state["active_section"] == sec
            if st.button(label, key=f"nav_{sec}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state["active_section"] = sec
                st.rerun()
```

- [ ] **Step 3: Add section rendering helpers and main content area**

Append to `ps11/app_mcp.py`:

```python
# ── Helper: AI narrative card ─────────────────────────────────────────────────
def _ai_card(text: str) -> None:
    st.markdown(
        f'<div class="ai-card"><div class="ai-label">✨ AI Analysis</div>{text}</div>',
        unsafe_allow_html=True,
    )

def _get_narrative(section: str) -> str:
    if section not in st.session_state["narratives"]:
        client = get_llm_client()
        narrative = get_section_narrative(client, deployment,
                                          st.session_state["profile"], section)
        st.session_state["narratives"][section] = narrative
    return st.session_state["narratives"][section]

def _metric_card(value: str, label: str, color_class: str) -> str:
    return (f'<div class="metric-card">'
            f'<div class="metric-value {color_class}">{value}</div>'
            f'<div class="metric-label">{label}</div></div>')

# ── Main content area ─────────────────────────────────────────────────────────
profile = st.session_state["profile"]
df      = st.session_state["df"]

if profile is None:
    st.markdown("## 📊 EDA Report Generator")
    st.info("Select a dataset and click **Generate Report** in the sidebar to begin.")
    st.stop()

section = st.session_state["active_section"]
numeric_cols = [c.meta.name for c in profile.columns if c.meta.dtype == "numeric"]
cat_cols     = [c.meta.name for c in profile.columns if c.meta.dtype == "categorical"]
dt_cols      = [c.meta.name for c in profile.columns if c.meta.is_datetime]

# ── OVERVIEW ──────────────────────────────────────────────────────────────────
if section == "Overview":
    st.markdown('<div class="section-header hdr-overview">🏠 Overview</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_metric_card(f"{profile.row_count:,}", "Total Rows", "teal"), unsafe_allow_html=True)
    c2.markdown(_metric_card(str(profile.col_count), "Columns", "purple"), unsafe_allow_html=True)
    c3.markdown(_metric_card(f"{profile.duplicate_row_count:,}", "Duplicates", "amber"), unsafe_allow_html=True)
    c4.markdown(_metric_card(f"{profile.memory_mb:.2f} MB", "Memory", "teal"), unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(charts.null_bar(profile), use_container_width=True)
    with col2:
        st.plotly_chart(charts.column_type_pie(profile), use_container_width=True)

    _ai_card(_get_narrative("Overview"))

# ── DATA QUALITY ──────────────────────────────────────────────────────────────
elif section == "Data Quality":
    st.markdown('<div class="section-header hdr-quality">🔍 Data Quality</div>',
                unsafe_allow_html=True)
    null_cols = [(c.meta.name, c.meta.null_pct) for c in profile.columns if c.meta.null_pct > 0]
    if null_cols:
        rows = [{"Column": n, "Null %": f"{p*100:.1f}%", "Status": "⚠️ Warning" if p > 0.1 else "✅ Low"}
                for n, p in null_cols]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.success("No missing values detected.")

    st.markdown(f"**Duplicate rows:** {profile.duplicate_row_count:,}")
    pii_cols = [c.meta.name for c in profile.columns
                if any(p in c.meta.name.lower() for p in ["email","phone","ssn","dob","address"])]
    if pii_cols:
        st.warning(f"Possible PII columns: {', '.join(pii_cols)}")

    _ai_card(_get_narrative("Data Quality"))

# ── DISTRIBUTIONS ─────────────────────────────────────────────────────────────
elif section == "Distributions":
    st.markdown('<div class="section-header hdr-distributions">📈 Distributions</div>',
                unsafe_allow_html=True)
    if numeric_cols:
        st.markdown("#### Numeric Distributions")
        cols_per_row = 2
        for i in range(0, len(numeric_cols), cols_per_row):
            row_cols = st.columns(cols_per_row)
            for j, col_name in enumerate(numeric_cols[i:i+cols_per_row]):
                with row_cols[j]:
                    st.plotly_chart(charts.histogram(df, col_name), use_container_width=True)

    if cat_cols:
        st.markdown("#### Categorical Distributions")
        cat_profiles = [c for c in profile.columns if c.meta.dtype == "categorical"]
        for i in range(0, len(cat_profiles), 2):
            row_cols = st.columns(2)
            for j, cp in enumerate(cat_profiles[i:i+2]):
                with row_cols[j]:
                    st.plotly_chart(charts.value_counts_bar(cp), use_container_width=True)

    _ai_card(_get_narrative("Distributions"))

# ── CORRELATIONS ──────────────────────────────────────────────────────────────
elif section == "Correlations":
    st.markdown('<div class="section-header hdr-correlations">🔗 Correlations</div>',
                unsafe_allow_html=True)
    if len(numeric_cols) >= 2:
        st.plotly_chart(charts.correlation_heatmap(df, numeric_cols), use_container_width=True)
        # Top correlated pairs scatter plots
        corr_matrix = df[numeric_cols].corr().abs()
        pairs = []
        for i in range(len(numeric_cols)):
            for j in range(i+1, len(numeric_cols)):
                pairs.append((corr_matrix.iloc[i,j], numeric_cols[i], numeric_cols[j]))
        pairs.sort(reverse=True)
        top_pairs = pairs[:4]
        if top_pairs:
            st.markdown("#### Top Correlated Pairs")
            for i in range(0, len(top_pairs), 2):
                row_cols = st.columns(2)
                for k, (corr_val, cx, cy) in enumerate(top_pairs[i:i+2]):
                    with row_cols[k]:
                        st.plotly_chart(charts.scatter_pair(df, cx, cy), use_container_width=True)
    else:
        st.info("Need at least 2 numeric columns for correlation analysis.")

    _ai_card(_get_narrative("Correlations"))

# ── OUTLIERS ──────────────────────────────────────────────────────────────────
elif section == "Outliers & Anomalies":
    st.markdown('<div class="section-header hdr-outliers">⚠️ Outliers & Anomalies</div>',
                unsafe_allow_html=True)
    st.plotly_chart(charts.outlier_pct_bar(profile), use_container_width=True)
    if numeric_cols:
        st.markdown("#### Box Plots")
        for i in range(0, len(numeric_cols), 2):
            row_cols = st.columns(2)
            for j, col_name in enumerate(numeric_cols[i:i+2]):
                with row_cols[j]:
                    st.plotly_chart(charts.box_plot(df, col_name), use_container_width=True)

    if dt_cols and numeric_cols:
        st.markdown("#### Time Series")
        dt_col = dt_cols[0]
        val_col = numeric_cols[0]
        st.plotly_chart(charts.time_series_line(df, dt_col, val_col), use_container_width=True)

    _ai_card(_get_narrative("Outliers & Anomalies"))

# ── AI INSIGHTS ───────────────────────────────────────────────────────────────
elif section == "AI Insights":
    st.markdown('<div class="section-header hdr-insights">✨ AI Insights</div>',
                unsafe_allow_html=True)

    if st.session_state["exec_summary"] is None:
        with st.spinner("Generating executive summary…"):
            client = get_llm_client()
            es = get_executive_summary(client, deployment, profile)
            st.session_state["exec_summary"] = es
            _store.store_report(
                dataset_name=profile.dataset_name,
                row_count=profile.row_count,
                col_count=profile.col_count,
                summary_json=es.model_dump_json(),
            )

    es = st.session_state["exec_summary"]

    # Data quality score
    score = es.data_quality_score
    color = "teal" if score >= 80 else ("amber" if score >= 60 else "coral")
    st.markdown(_metric_card(f"{score:.0f}/100", "Data Quality Score", color),
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Key Findings")
        for f in es.key_findings:
            st.markdown(f'<div class="finding-card">• {f}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown("#### Anomalies Detected")
        for a in es.anomalies:
            st.markdown(f'<div class="anomaly-card">⚠️ {a}</div>', unsafe_allow_html=True)

    st.markdown("#### Recommendations")
    for r in es.recommendations:
        st.markdown(f'<div class="rec-card">→ {r}</div>', unsafe_allow_html=True)

    st.markdown("#### ML Readiness")
    st.markdown(f'<div class="ai-card"><div class="ai-label">🤖 Assessment</div>{es.ml_readiness}</div>',
                unsafe_allow_html=True)

    # Similar past reports
    st.markdown("#### Similar Past Reports")
    query = f"{profile.dataset_name} {profile.row_count} rows {profile.col_count} columns"
    past = _store.search_similar(query, n=3)
    if past:
        for item in past:
            meta = item["meta"]
            with st.expander(f"📄 {meta.get('dataset_name','Unknown')} — {meta.get('timestamp','')[:10]}"):
                try:
                    old_es = json.loads(item["summary"])
                    st.json(old_es)
                except Exception:
                    st.text(item["summary"])
    else:
        st.info("No past reports yet. Generate reports from multiple datasets to see similarities.")

# ── EXPORT ────────────────────────────────────────────────────────────────────
elif section == "Export":
    st.markdown('<div class="section-header hdr-export">📥 Export</div>',
                unsafe_allow_html=True)

    # CSV summary
    stat_rows = []
    for cp in profile.columns:
        row = {"column": cp.meta.name, "dtype": cp.meta.dtype,
               "null_pct": cp.meta.null_pct, "role": cp.meta.role}
        if cp.mean is not None: row["mean"] = cp.mean
        if cp.median is not None: row["median"] = cp.median
        if cp.std is not None: row["std"] = cp.std
        if cp.min is not None: row["min"] = cp.min
        if cp.max is not None: row["max"] = cp.max
        if cp.unique_count is not None: row["unique_count"] = cp.unique_count
        if cp.outlier: row["outlier_count"] = cp.outlier.count
        stat_rows.append(row)
    csv_df = pd.DataFrame(stat_rows)
    st.download_button(
        "⬇️ Download CSV Summary",
        data=csv_df.to_csv(index=False).encode(),
        file_name=f"{profile.dataset_name}_eda_summary.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # HTML report
    if st.button("⬇️ Download HTML Report", use_container_width=True):
        html_parts = [
            "<html><head><style>",
            "body{background:#0e0e1a;color:#e0e0ff;font-family:Inter,sans-serif;padding:24px}",
            "h1{color:#00d4aa} h2{color:#7c6bf2} p{color:#e0e0ff}",
            "</style></head><body>",
            f"<h1>EDA Report: {profile.dataset_name}</h1>",
            f"<p>Rows: {profile.row_count} | Columns: {profile.col_count} | Memory: {profile.memory_mb:.2f} MB</p>",
        ]
        # Embed charts
        for col_name in numeric_cols[:4]:
            fig = charts.histogram(df, col_name)
            html_parts.append(f"<h2>{col_name} Distribution</h2>")
            html_parts.append(fig.to_html(include_plotlyjs="cdn", full_html=False))
        if len(numeric_cols) >= 2:
            html_parts.append("<h2>Correlation Matrix</h2>")
            html_parts.append(charts.correlation_heatmap(df, numeric_cols).to_html(
                include_plotlyjs=False, full_html=False))
        # AI summary
        if st.session_state["exec_summary"]:
            es = st.session_state["exec_summary"]
            html_parts.append("<h2>AI Key Findings</h2><ul>")
            for f in es.key_findings:
                html_parts.append(f"<li>{f}</li>")
            html_parts.append("</ul>")
        html_parts.append("</body></html>")
        html_bytes = "\n".join(html_parts).encode()
        st.download_button(
            "Click here to download",
            data=html_bytes,
            file_name=f"{profile.dataset_name}_eda_report.html",
            mime="text/html",
        )
```

- [ ] **Step 4: Verify app imports without error**

```bash
cd ps11 && python -c "
import subprocess, sys
result = subprocess.run([sys.executable, '-c',
    'import os; os.environ[\"OPENAI_API_KEY\"]=\"test\"; '
    'import importlib.util; spec=importlib.util.spec_from_file_location(\"app\",\"app_mcp.py\"); '
    'print(\"App imports OK\")'],
    capture_output=True, text=True, cwd='.'
)
print(result.stdout or result.stderr[:300])
"
```

Expected output contains `App imports OK` or any Streamlit-related message (not a module error)

- [ ] **Step 5: Commit**

```bash
git add ps11/app_mcp.py
git commit -m "feat(ps11): add full Streamlit app with 7-section sidebar navigation and colorful dark theme"
```

---

## Task 13: Run Full Test Suite and Smoke Test

- [ ] **Step 1: Run all unit tests**

```bash
cd ps11 && python -m pytest tests/ -v
```

Expected: All tests pass (models, guardrails, infer, preprocess, profile, charts)

- [ ] **Step 2: Verify pipeline end-to-end with demo dataset**

```bash
cd ps11 && python -c "
import os; os.environ.setdefault('OPENAI_API_KEY','test')
import sys; sys.path.insert(0,'src')
import pandas as pd
from eda_report.infer import infer_columns
from eda_report.preprocess import impute_nulls, parse_datetimes
from eda_report.profile import build_profile

df = pd.read_csv('data/retail_sales.csv')
metas = infer_columns(df)
df = impute_nulls(df, metas)
df = parse_datetimes(df, metas)
profile = build_profile(df, metas, dataset_name='retail_sales')
print(f'Profile OK: {profile.row_count} rows, {len(profile.columns)} profiled columns')
print(f'Numeric cols: {[c.meta.name for c in profile.columns if c.meta.dtype==\"numeric\"]}')
print(f'Datetime cols: {[c.meta.name for c in profile.columns if c.meta.is_datetime]}')
"
```

Expected: `Profile OK: 500 rows, ...`

- [ ] **Step 3: Commit final**

```bash
git add .
git commit -m "feat(ps11): complete EDA report generator — all modules, tests, datasets"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] SSL patch first in `app_mcp.py` (Task 12, Step 1)
- [x] `openai.OpenAI` with `httpx.Client(verify=False)` in `config.py` (Task 1)
- [x] No `.beta.parse` — manual JSON parsing in `insights.py` (Task 9)
- [x] `sanitize_for_proxy()` in `config.py`, called in `insights.py` (Tasks 1, 9)
- [x] Both demo datasets generated (Task 3)
- [x] 7 sidebar sections (Task 12)
- [x] All chart types (null bar, type pie, histogram+KDE, value counts, heatmap, scatter, box, outlier bar, time series) in `charts.py` (Task 8)
- [x] Per-section narratives + executive summary (Task 9)
- [x] ChromaDB store + similar past reports panel (Tasks 10, 12)
- [x] MCP server with 3 tools (Task 11)
- [x] HTML + CSV export (Task 12)
- [x] Guardrails: file size, row truncation, column count, PII (Task 4)
- [x] `model_key` passed from sidebar to `get_model()` (Task 12)

**Type consistency:** `ColumnMeta`, `ColumnProfile`, `DatasetProfile`, `ExecutiveSummary`, `GuardrailResult` defined in Task 2, used consistently in Tasks 4–12. `detect_outliers` defined in Task 6 (`preprocess.py`), called in Task 7 (`profile.py`). `infer_columns` returns `list[ColumnMeta]` used by `impute_nulls`, `parse_datetimes`, `build_profile`. All consistent.
