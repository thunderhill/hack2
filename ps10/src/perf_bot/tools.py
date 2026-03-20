"""Six LLM-backed tool functions for the Performance Bottleneck Explanation Bot.

Each function sanitizes input, calls the LLM, manually parses JSON, and returns a Pydantic model.
"""

import json

from .config import get_llm_client, get_model
from .guardrails import sanitize_for_proxy
from .models import (
    CpuFindings,
    LogFindings,
    MemoryFindings,
    MetricsInput,
    TraceFindings,
)
from .prompts import (
    CORRELATION_PROMPT,
    CPU_ANALYSIS_PROMPT,
    LOG_ANALYSIS_PROMPT,
    MEMORY_ANALYSIS_PROMPT,
    REMEDIATION_PROMPT,
    TRACE_ANALYSIS_PROMPT,
)


def _call_llm(system_prompt: str, user_content: str, model_key: str) -> dict:
    """Call LLM, strip markdown fences, parse JSON."""
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": sanitize_for_proxy(user_content)},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def analyze_cpu(metrics: MetricsInput, model_key: str = "gpt-4o-mini") -> CpuFindings:
    """Tool 1: Analyze CPU metrics for bottlenecks."""
    user_content = f"""CPU Metrics for {metrics.app_name} ({metrics.environment}):
- Current CPU utilization: {metrics.cpu_current_pct}%
- Average CPU over last hour: {metrics.cpu_avg_1h_pct}%
- Peak CPU: {metrics.cpu_peak_pct}%
- Number of CPU cores: {metrics.thread_pool_size // 4 or 4}
- Thread pool size: {metrics.thread_pool_size}
- Application type: {metrics.app_type}
"""
    data = _call_llm(CPU_ANALYSIS_PROMPT, user_content, model_key)
    return CpuFindings(**data)


def analyze_memory(metrics: MetricsInput, model_key: str = "gpt-4o-mini") -> MemoryFindings:
    """Tool 2: Analyze memory metrics for bottlenecks."""
    memory_pct = round(metrics.memory_used_mb / max(metrics.memory_total_mb, 1) * 100, 1)
    user_content = f"""Memory Metrics for {metrics.app_name} ({metrics.environment}):
- Memory used: {metrics.memory_used_mb} MB
- Total memory: {metrics.memory_total_mb} MB
- Memory utilization: {memory_pct}%
- GC pause count: {metrics.gc_pause_count}
- GC pause average: {metrics.gc_pause_avg_ms} ms
- Application type: {metrics.app_type}
- Cache enabled: {metrics.cache_enabled}
"""
    data = _call_llm(MEMORY_ANALYSIS_PROMPT, user_content, model_key)
    return MemoryFindings(**data)


def analyze_traces(metrics: MetricsInput, model_key: str = "gpt-4o-mini") -> TraceFindings:
    """Tool 3: Analyze trace data and response times for latency bottlenecks."""
    user_content = f"""Response Time & Trace Data for {metrics.app_name} ({metrics.environment}):
- Average response time: {metrics.response_avg_ms} ms
- p95 response time: {metrics.response_p95_ms} ms
- p99 response time: {metrics.response_p99_ms} ms
- Slowest endpoint: {metrics.slowest_endpoint}
- Timeout configuration: {metrics.timeout_ms} ms
- DB connection pool size: {metrics.db_pool_size}

Trace data:
{metrics.trace_data or "No trace data provided"}
"""
    data = _call_llm(TRACE_ANALYSIS_PROMPT, user_content, model_key)
    return TraceFindings(**data)


def analyze_logs(metrics: MetricsInput, model_key: str = "gpt-4o-mini") -> LogFindings:
    """Tool 4: Analyze log output for error patterns and performance issues."""
    user_content = f"""Application Log Output for {metrics.app_name} ({metrics.environment}):
Application type: {metrics.app_type}
DB pool size: {metrics.db_pool_size}, Thread pool size: {metrics.thread_pool_size}

Log snippet:
{metrics.error_logs or "No log data provided"}
"""
    data = _call_llm(LOG_ANALYSIS_PROMPT, user_content, model_key)
    return LogFindings(**data)


def correlate_bottlenecks(
    cpu: CpuFindings,
    memory: MemoryFindings,
    traces: TraceFindings,
    logs: LogFindings,
    metrics: MetricsInput,
    model_key: str = "gpt-4o-mini",
) -> dict:
    """Tool 5: Correlate findings from all four analyses into unified root-cause narrative."""
    user_content = f"""Application: {metrics.app_name} ({metrics.app_type}, {metrics.environment})

=== CPU Analysis ===
Severity: {cpu.severity} | Bottleneck detected: {cpu.bottleneck_detected}
Findings: {'; '.join(cpu.findings)}
Likely cause: {cpu.likely_cause}

=== Memory Analysis ===
Severity: {memory.severity} | Bottleneck detected: {memory.bottleneck_detected} | GC pressure: {memory.gc_pressure}
Findings: {'; '.join(memory.findings)}
Likely cause: {memory.likely_cause}

=== Trace / Latency Analysis ===
Severity: {traces.severity} | Bottleneck detected: {traces.bottleneck_detected}
Slow path: {traces.slow_path}
Findings: {'; '.join(traces.findings)}
Likely cause: {traces.likely_cause}

=== Log Analysis ===
Severity: {logs.severity} | Bottleneck detected: {logs.bottleneck_detected}
Error patterns: {'; '.join(logs.error_patterns)}
Findings: {'; '.join(logs.findings)}
Likely cause: {logs.likely_cause}

Configuration context:
- DB pool size: {metrics.db_pool_size}
- Thread pool size: {metrics.thread_pool_size}
- Cache enabled: {metrics.cache_enabled}
- Timeout: {metrics.timeout_ms} ms
"""
    return _call_llm(CORRELATION_PROMPT, user_content, model_key)


def generate_remediation(
    correlation: dict,
    metrics: MetricsInput,
    model_key: str = "gpt-4o-mini",
) -> list[dict]:
    """Tool 6: Generate prioritized remediation steps with code snippets."""
    user_content = f"""Application: {metrics.app_name} ({metrics.app_type}, {metrics.environment})

=== Correlated Bottleneck Analysis ===
Severity: {correlation.get('severity', 'Unknown')}
Root cause: {correlation.get('root_cause_summary', '')}
Bottlenecks: {'; '.join(correlation.get('bottlenecks', []))}
Cascade explanation: {correlation.get('cascade_explanation', '')}

Current configuration:
- DB pool size: {metrics.db_pool_size}
- Thread pool size: {metrics.thread_pool_size}
- Cache enabled: {metrics.cache_enabled}
- Timeout: {metrics.timeout_ms} ms
- Memory: {metrics.memory_used_mb}/{metrics.memory_total_mb} MB
- CPU avg: {metrics.cpu_avg_1h_pct}%
"""
    data = _call_llm(REMEDIATION_PROMPT, user_content, model_key)
    return data.get("remediations", [])
