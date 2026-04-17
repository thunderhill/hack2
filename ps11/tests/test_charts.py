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

def test_scatter_pair_returns_figure():
    df = pd.DataFrame({"price": [10, 20, 30, 40, 50], "revenue": [100, 200, 300, 400, 500]})
    fig = charts.scatter_pair(df, "price", "revenue")
    assert isinstance(fig, go.Figure)

def test_outlier_pct_bar_returns_figure():
    fig = charts.outlier_pct_bar(_make_profile())
    assert isinstance(fig, go.Figure)
