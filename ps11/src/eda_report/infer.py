import warnings
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
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    parsed = pd.to_datetime(non_null, errors="coerce")
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
            # measure if high cardinality ratio OR many absolute unique values
            cardinality_ratio = n_unique / max(n_total, 1)
            role = "measure" if (cardinality_ratio > 0.5 or n_unique >= 20) else "dimension"
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
