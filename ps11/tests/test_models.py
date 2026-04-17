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
