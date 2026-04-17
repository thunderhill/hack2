import pandas as pd
import numpy as np
import plotly.graph_objects as go
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
