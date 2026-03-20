"""Orchestrator: runs the 6 analysis tools in sequence and assembles the BottleneckReport."""

import time
from collections.abc import Callable

from .config import get_model
from .models import BottleneckReport, MetricsInput, RemediationStep
from .tools import (
    analyze_cpu,
    analyze_logs,
    analyze_memory,
    analyze_traces,
    correlate_bottlenecks,
    generate_remediation,
)


def run_analysis(
    metrics: MetricsInput,
    model_key: str = "gpt-4o-mini",
    on_step_complete: Callable[[str, object], None] | None = None,
) -> BottleneckReport:
    """Run all 6 tools sequentially. Calls on_step_complete(step_name, result) after each."""
    start_ms = int(time.time() * 1000)

    # Tool 1 — CPU
    cpu = analyze_cpu(metrics, model_key)
    if on_step_complete:
        on_step_complete("cpu", cpu)

    # Tool 2 — Memory
    memory = analyze_memory(metrics, model_key)
    if on_step_complete:
        on_step_complete("memory", memory)

    # Tool 3 — Traces
    traces = analyze_traces(metrics, model_key)
    if on_step_complete:
        on_step_complete("traces", traces)

    # Tool 4 — Logs
    logs = analyze_logs(metrics, model_key)
    if on_step_complete:
        on_step_complete("logs", logs)

    # Tool 5 — Correlation
    correlation = correlate_bottlenecks(cpu, memory, traces, logs, metrics, model_key)
    if on_step_complete:
        on_step_complete("correlate", correlation)

    # Tool 6 — Remediation
    remediation_raw = generate_remediation(correlation, metrics, model_key)
    if on_step_complete:
        on_step_complete("remediation", remediation_raw)

    elapsed_ms = int(time.time() * 1000) - start_ms

    remediations = [RemediationStep(**r) for r in remediation_raw]

    return BottleneckReport(
        app_name=metrics.app_name,
        severity=correlation.get("severity", "High"),
        root_cause_summary=correlation.get("root_cause_summary", ""),
        bottlenecks=correlation.get("bottlenecks", []),
        cascade_explanation=correlation.get("cascade_explanation", ""),
        remediations=remediations,
        diagnosis_time_ms=elapsed_ms,
        model_used=get_model(model_key),
    )
