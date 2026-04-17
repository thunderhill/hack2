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
