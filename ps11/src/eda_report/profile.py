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
