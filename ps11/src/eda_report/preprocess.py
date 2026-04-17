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
        parsed = pd.to_datetime(df[col], errors="coerce")
        df[col] = parsed
        df[f"{col}_year"]  = parsed.dt.year
        df[f"{col}_month"] = parsed.dt.month
        df[f"{col}_dow"]   = parsed.dt.dayofweek
    return df
