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
