from __future__ import annotations
from typing import Literal
import pandas as pd
from pydantic import BaseModel


class ColumnMeta(BaseModel):
    name: str
    dtype: Literal["numeric", "categorical", "datetime", "boolean", "text"]
    is_id: bool
    is_target: bool
    is_datetime: bool
    role: Literal["dimension", "measure"]
    null_pct: float


class OutlierSummary(BaseModel):
    count: int
    pct: float
    lower_bound: float
    upper_bound: float


class ColumnProfile(BaseModel):
    meta: ColumnMeta
    outlier: OutlierSummary | None = None
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None
    unique_count: int | None = None
    top_5_values: dict[str, int] | None = None
    date_min: str | None = None
    date_max: str | None = None
    inferred_freq: str | None = None


class DatasetProfile(BaseModel):
    dataset_name: str
    row_count: int
    col_count: int
    memory_mb: float
    duplicate_row_count: int
    columns: list[ColumnProfile]


class ExecutiveSummary(BaseModel):
    key_findings: list[str]
    data_quality_score: float
    anomalies: list[str]
    recommendations: list[str]
    ml_readiness: str


class GuardrailResult(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
    truncated: bool
    df: object  # pd.DataFrame — excluded from serialization

    model_config = {"arbitrary_types_allowed": True}
