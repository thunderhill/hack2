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
