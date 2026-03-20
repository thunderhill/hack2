"""Pydantic models for Performance Bottleneck Explanation Bot."""

from pydantic import BaseModel, Field


class MetricsInput(BaseModel):
    app_name: str
    environment: str
    app_type: str
    cpu_current_pct: float
    cpu_avg_1h_pct: float
    cpu_peak_pct: float
    memory_used_mb: int
    memory_total_mb: int
    gc_pause_count: int
    gc_pause_avg_ms: float
    response_avg_ms: float
    response_p95_ms: float
    response_p99_ms: float
    slowest_endpoint: str
    error_logs: str
    trace_data: str
    thread_pool_size: int
    db_pool_size: int
    cache_enabled: bool
    timeout_ms: int


class CpuFindings(BaseModel):
    bottleneck_detected: bool
    severity: str
    findings: list[str] = Field(default_factory=list)
    likely_cause: str
    recommendation: str


class MemoryFindings(BaseModel):
    bottleneck_detected: bool
    severity: str
    findings: list[str] = Field(default_factory=list)
    gc_pressure: bool
    likely_cause: str
    recommendation: str


class TraceFindings(BaseModel):
    bottleneck_detected: bool
    severity: str
    findings: list[str] = Field(default_factory=list)
    slow_path: str
    likely_cause: str
    recommendation: str


class LogFindings(BaseModel):
    bottleneck_detected: bool
    severity: str
    findings: list[str] = Field(default_factory=list)
    error_patterns: list[str] = Field(default_factory=list)
    likely_cause: str
    recommendation: str


class RemediationStep(BaseModel):
    priority: int
    title: str
    description: str
    effort: str       # Low | Medium | High
    impact: str       # Low | Medium | High
    code_snippet: str


class BottleneckReport(BaseModel):
    app_name: str
    severity: str     # Critical | High | Medium | Low
    root_cause_summary: str
    bottlenecks: list[str] = Field(default_factory=list)
    cascade_explanation: str
    remediations: list[RemediationStep] = Field(default_factory=list)
    diagnosis_time_ms: int
    model_used: str
