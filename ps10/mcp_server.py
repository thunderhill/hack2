"""MCP Server for Performance Bottleneck Explanation Bot — exposes analyze_performance as MCP tool."""

import os, ssl, warnings

os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

load_dotenv(override=True)

from mcp.server.fastmcp import FastMCP

from perf_bot.agent import run_analysis
from perf_bot.config import MODEL_OPTIONS
from perf_bot.guardrails import run_input_guardrails
from perf_bot.models import MetricsInput
from chroma_store import ChromaStore

mcp = FastMCP("Performance Bottleneck Explanation Bot")
store = ChromaStore("perf_bot")


@mcp.tool()
def analyze_performance(
    app_name: str,
    environment: str,
    app_type: str,
    cpu_current_pct: float,
    cpu_avg_1h_pct: float,
    cpu_peak_pct: float,
    memory_used_mb: int,
    memory_total_mb: int,
    gc_pause_count: int,
    gc_pause_avg_ms: float,
    response_avg_ms: float,
    response_p95_ms: float,
    response_p99_ms: float,
    slowest_endpoint: str,
    error_logs: str = "",
    trace_data: str = "",
    thread_pool_size: int = 200,
    db_pool_size: int = 10,
    cache_enabled: bool = False,
    timeout_ms: int = 30000,
    model_key: str = "gpt-4o-mini",
) -> dict:
    """Analyze application performance metrics and produce root-cause explanations with remediation steps.

    Args:
        app_name: Name of the application
        environment: Deployment environment (prod/staging/dev)
        app_type: Application runtime (Java/Python/Node/Other)
        cpu_current_pct: Current CPU utilization percentage
        cpu_avg_1h_pct: Average CPU utilization over the last hour
        cpu_peak_pct: Peak CPU utilization observed
        memory_used_mb: Memory currently in use (MB)
        memory_total_mb: Total available memory (MB)
        gc_pause_count: Number of GC pauses in the observation window
        gc_pause_avg_ms: Average GC pause duration (ms)
        response_avg_ms: Average response time (ms)
        response_p95_ms: 95th percentile response time (ms)
        response_p99_ms: 99th percentile response time (ms)
        slowest_endpoint: Path of the slowest API endpoint
        error_logs: Paste of relevant log lines
        trace_data: Distributed trace spans/output
        thread_pool_size: Application thread pool size
        db_pool_size: Database connection pool size
        cache_enabled: Whether caching is enabled
        timeout_ms: Request timeout in ms
        model_key: LLM model (gpt-4o, gpt-4o-mini, gpt-35-turbo)
    """
    # Guardrails on free-text fields
    for field_value in [error_logs, trace_data]:
        if field_value:
            guard = run_input_guardrails(field_value)
            if guard.blocked:
                return {"error": f"Input blocked by guardrails: {guard.block_reason}"}

    metrics = MetricsInput(
        app_name=app_name,
        environment=environment,
        app_type=app_type,
        cpu_current_pct=cpu_current_pct,
        cpu_avg_1h_pct=cpu_avg_1h_pct,
        cpu_peak_pct=cpu_peak_pct,
        memory_used_mb=memory_used_mb,
        memory_total_mb=memory_total_mb,
        gc_pause_count=gc_pause_count,
        gc_pause_avg_ms=gc_pause_avg_ms,
        response_avg_ms=response_avg_ms,
        response_p95_ms=response_p95_ms,
        response_p99_ms=response_p99_ms,
        slowest_endpoint=slowest_endpoint,
        error_logs=error_logs,
        trace_data=trace_data,
        thread_pool_size=thread_pool_size,
        db_pool_size=db_pool_size,
        cache_enabled=cache_enabled,
        timeout_ms=timeout_ms,
    )

    report = run_analysis(metrics, model_key)
    result_dict = report.model_dump()
    store.add(f"{app_name} {environment} cpu={cpu_current_pct}%", result_dict, model_key)
    return result_dict


@mcp.tool()
def search_past_analyses(query: str, n_results: int = 5) -> list:
    """Search past performance analyses by semantic similarity.

    Args:
        query: Search query text
        n_results: Number of results to return (default 5)
    """
    return store.search(query, n_results)


@mcp.tool()
def get_recent_analyses(n: int = 10) -> list:
    """Get the most recent performance analyses.

    Args:
        n: Number of recent analyses to return (default 10)
    """
    return store.get_recent(n)


@mcp.tool()
def list_models() -> list:
    """List available LLM models."""
    return MODEL_OPTIONS


if __name__ == "__main__":
    mcp.run()
