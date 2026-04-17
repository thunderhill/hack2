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
