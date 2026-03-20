import os, ssl, warnings

os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

load_dotenv(override=True)

import streamlit as st
import plotly.graph_objects as go

from perf_bot.agent import run_analysis
from perf_bot.config import MODEL_OPTIONS
from perf_bot.models import MetricsInput
from perf_bot.synthetic import generate_synthetic_data
from perf_bot.guardrails import run_input_guardrails
from chroma_store import ChromaStore

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Perf Bot — PS10",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid #3a3a5c;
    text-align: center;
    margin-bottom: 10px;
}
.metric-value { font-size: 2.4rem; font-weight: 700; margin: 4px 0; }
.metric-label { font-size: 0.85rem; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
.metric-green { color: #00d48b; }
.metric-yellow { color: #ffc300; }
.metric-red { color: #ff4b4b; }

/* Severity badges */
.badge-critical { background:#ff4b4b; color:#fff; padding:3px 10px; border-radius:12px; font-size:0.8rem; }
.badge-high { background:#ff8c00; color:#fff; padding:3px 10px; border-radius:12px; font-size:0.8rem; }
.badge-medium { background:#ffc300; color:#000; padding:3px 10px; border-radius:12px; font-size:0.8rem; }
.badge-low { background:#00d48b; color:#000; padding:3px 10px; border-radius:12px; font-size:0.8rem; }

/* Remediation cards */
.rem-card {
    background: #1e1e2e;
    border-left: 4px solid #7c6bf2;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 14px;
}
.rem-title { font-size: 1.1rem; font-weight: 600; color: #e0e0ff; margin-bottom: 6px; }
.rem-meta { font-size: 0.8rem; color: #aaa; margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
if "metrics" not in st.session_state:
    st.session_state.metrics = None
if "report" not in st.session_state:
    st.session_state.report = None
if "step_results" not in st.session_state:
    st.session_state.step_results = {}
if "analysis_running" not in st.session_state:
    st.session_state.analysis_running = False

STEPS = ["cpu", "memory", "traces", "logs", "correlate", "remediation"]
STEP_LABELS = {
    "cpu":        "1. Analyze CPU Metrics",
    "memory":     "2. Analyze Memory / GC",
    "traces":     "3. Analyze Distributed Traces",
    "logs":       "4. Analyze Error Logs",
    "correlate":  "5. Correlate Bottlenecks",
    "remediation":"6. Generate Remediation Plan",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_resource
def get_store() -> ChromaStore:
    persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma")
    return ChromaStore("perf_bot", persist_dir=persist_dir)


def severity_color(val: float, low: float, med: float) -> str:
    if val >= med:
        return "metric-red"
    if val >= low:
        return "metric-yellow"
    return "metric-green"


def metric_card(label: str, value: str, color_class: str) -> str:
    return f"""
<div class="metric-card">
  <div class="metric-label">{label}</div>
  <div class="metric-value {color_class}">{value}</div>
</div>
"""


def sparkline(values: list[float], color: str = "#7c6bf2") -> go.Figure:
    fig = go.Figure(go.Scatter(
        y=values, mode="lines", line=dict(color=color, width=2),
        fill="tozeroy", fillcolor=color.replace(")", ",0.15)").replace("rgb", "rgba") if color.startswith("rgb") else color + "26",
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        height=60,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


def build_metrics_from_form() -> MetricsInput:
    s = st.session_state
    return MetricsInput(
        app_name=s.get("f_app_name", "MyApp"),
        environment=s.get("f_environment", "prod"),
        app_type=s.get("f_app_type", "Java"),
        cpu_current_pct=s.get("f_cpu_current", 50.0),
        cpu_avg_1h_pct=s.get("f_cpu_avg", 45.0),
        cpu_peak_pct=s.get("f_cpu_peak", 70.0),
        memory_used_mb=s.get("f_mem_used", 4096),
        memory_total_mb=s.get("f_mem_total", 8192),
        gc_pause_count=s.get("f_gc_count", 10),
        gc_pause_avg_ms=s.get("f_gc_avg_ms", 50.0),
        response_avg_ms=s.get("f_resp_avg", 300.0),
        response_p95_ms=s.get("f_resp_p95", 800.0),
        response_p99_ms=s.get("f_resp_p99", 1500.0),
        slowest_endpoint=s.get("f_slowest_ep", "/api/data"),
        error_logs=s.get("f_error_logs", ""),
        trace_data=s.get("f_trace_data", ""),
        thread_pool_size=s.get("f_thread_pool", 200),
        db_pool_size=s.get("f_db_pool", 10),
        cache_enabled=s.get("f_cache_enabled", False),
        timeout_ms=s.get("f_timeout_ms", 30000),
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Simple_graph.svg/120px-Simple_graph.svg.png", width=40)
    st.title("⚡ Perf Bot")
    st.caption("PS10 — Performance Bottleneck Explanation Bot")
    st.divider()

    model_key = st.selectbox("LLM Model", MODEL_OPTIONS, index=1, key="sidebar_model")

    st.divider()
    st.subheader("Agent Activity")

    step_placeholders: dict[str, st.delta_generator.DeltaGenerator] = {}
    for step in STEPS:
        step_placeholders[step] = st.empty()
        result = st.session_state.step_results.get(step)
        if result is not None:
            step_placeholders[step].success(f"✅ {STEP_LABELS[step]}")
        elif st.session_state.analysis_running:
            step_placeholders[step].info(f"⏳ {STEP_LABELS[step]}")
        else:
            step_placeholders[step].markdown(f"⬜ {STEP_LABELS[step]}")

    if st.session_state.report:
        st.divider()
        st.caption(f"Diagnosis: {st.session_state.report.diagnosis_time_ms:,} ms")
        st.caption(f"Model: {st.session_state.report.model_used}")


# ── Main tabs ─────────────────────────────────────────────────────────────────
tab_dash, tab_input, tab_analysis, tab_remediation, tab_history = st.tabs(
    ["📊 Dashboard", "📋 Input", "🔍 Analysis", "🛠 Remediation", "📚 History"]
)

# ═══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Dashboard
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    st.header("Performance Dashboard")

    m = st.session_state.metrics

    if m is None:
        st.info("No metrics loaded. Use the **Input** tab or click **Load Synthetic Data** to get started.")
    else:
        # Metric cards row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            cc = severity_color(m.cpu_current_pct, 60, 80)
            st.markdown(metric_card("CPU Utilization", f"{m.cpu_current_pct:.1f}%", cc), unsafe_allow_html=True)
        with col2:
            mem_pct = m.memory_used_mb / max(m.memory_total_mb, 1) * 100
            mc = severity_color(mem_pct, 70, 85)
            st.markdown(metric_card("Memory Used", f"{mem_pct:.1f}%", mc), unsafe_allow_html=True)
        with col3:
            rc = severity_color(m.response_avg_ms, 500, 1500)
            st.markdown(metric_card("Avg Response", f"{m.response_avg_ms:.0f} ms", rc), unsafe_allow_html=True)
        with col4:
            # Derive error rate from GC pauses as proxy
            err_rate = min(m.gc_pause_count / 2.0, 100)
            ec = severity_color(err_rate, 5, 20)
            st.markdown(metric_card("GC Pauses / hr", f"{m.gc_pause_count}", ec), unsafe_allow_html=True)

        st.divider()

        # Sparkline charts
        st.subheader("Metric Trends (simulated 15-min window)")
        import random, math
        rng = random.Random(42)

        def sim_series(base: float, noise: float = 5.0, n: int = 20) -> list[float]:
            vals = []
            v = base * 0.7
            for i in range(n):
                v = v + (base - v) * 0.15 + rng.gauss(0, noise)
                v = max(0, v)
                vals.append(round(v, 1))
            return vals

        c1, c2 = st.columns(2)
        with c1:
            st.caption("CPU Utilization (%)")
            st.plotly_chart(sparkline(sim_series(m.cpu_current_pct, 8), "#ff4b4b"), use_container_width=True)
            st.caption("Avg Response Time (ms)")
            st.plotly_chart(sparkline(sim_series(m.response_avg_ms, 200), "#ffc300"), use_container_width=True)
        with c2:
            st.caption("Memory Utilization (%)")
            st.plotly_chart(sparkline(sim_series(mem_pct, 4), "#7c6bf2"), use_container_width=True)
            st.caption("GC Pause Duration (ms)")
            st.plotly_chart(sparkline(sim_series(m.gc_pause_avg_ms, 50), "#00d48b"), use_container_width=True)

        # App info
        st.divider()
        ci1, ci2, ci3 = st.columns(3)
        ci1.metric("Application", m.app_name)
        ci2.metric("Environment", m.environment.upper())
        ci3.metric("App Type", m.app_type)

        if st.session_state.report:
            sev = st.session_state.report.severity
            badge_cls = f"badge-{sev.lower()}"
            st.markdown(f"**Diagnosis:** <span class='{badge_cls}'>{sev}</span> — {st.session_state.report.root_cause_summary}", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Input
# ═══════════════════════════════════════════════════════════════════════════════
with tab_input:
    st.header("Application Metrics Input")

    load_col, _ = st.columns([1, 3])
    with load_col:
        if st.button("🎲 Load Synthetic Data", use_container_width=True):
            syn = generate_synthetic_data()
            # Copy to session state keys used by the form
            st.session_state["f_app_name"] = syn.app_name
            st.session_state["f_environment"] = syn.environment
            st.session_state["f_app_type"] = syn.app_type
            st.session_state["f_cpu_current"] = syn.cpu_current_pct
            st.session_state["f_cpu_avg"] = syn.cpu_avg_1h_pct
            st.session_state["f_cpu_peak"] = syn.cpu_peak_pct
            st.session_state["f_mem_used"] = syn.memory_used_mb
            st.session_state["f_mem_total"] = syn.memory_total_mb
            st.session_state["f_gc_count"] = syn.gc_pause_count
            st.session_state["f_gc_avg_ms"] = syn.gc_pause_avg_ms
            st.session_state["f_resp_avg"] = syn.response_avg_ms
            st.session_state["f_resp_p95"] = syn.response_p95_ms
            st.session_state["f_resp_p99"] = syn.response_p99_ms
            st.session_state["f_slowest_ep"] = syn.slowest_endpoint
            st.session_state["f_error_logs"] = syn.error_logs
            st.session_state["f_trace_data"] = syn.trace_data
            st.session_state["f_thread_pool"] = syn.thread_pool_size
            st.session_state["f_db_pool"] = syn.db_pool_size
            st.session_state["f_cache_enabled"] = syn.cache_enabled
            st.session_state["f_timeout_ms"] = syn.timeout_ms
            st.session_state.metrics = syn
            st.success("Synthetic data loaded — switch to the Analysis tab to run the bot.")

    st.divider()

    with st.form("metrics_form"):
        st.subheader("App Metadata")
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            app_name = st.text_input("App Name", value=st.session_state.get("f_app_name", "MyApp"), key="f_app_name")
        with mc2:
            environment = st.selectbox("Environment", ["prod", "staging", "dev"],
                                       index=["prod", "staging", "dev"].index(st.session_state.get("f_environment", "prod")),
                                       key="f_environment")
        with mc3:
            app_type = st.selectbox("App Type", ["Java", "Python", "Node", "Other"],
                                    index=["Java", "Python", "Node", "Other"].index(st.session_state.get("f_app_type", "Java")),
                                    key="f_app_type")

        st.subheader("CPU Metrics")
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            cpu_current = st.number_input("Current CPU %", 0.0, 100.0, st.session_state.get("f_cpu_current", 50.0), key="f_cpu_current")
        with cc2:
            cpu_avg = st.number_input("Avg CPU % (1h)", 0.0, 100.0, st.session_state.get("f_cpu_avg", 45.0), key="f_cpu_avg")
        with cc3:
            cpu_peak = st.number_input("Peak CPU %", 0.0, 100.0, st.session_state.get("f_cpu_peak", 70.0), key="f_cpu_peak")

        st.subheader("Memory Metrics")
        mem1, mem2, mem3, mem4 = st.columns(4)
        with mem1:
            mem_used = st.number_input("Used (MB)", 0, 1000000, st.session_state.get("f_mem_used", 4096), key="f_mem_used")
        with mem2:
            mem_total = st.number_input("Total (MB)", 1, 1000000, st.session_state.get("f_mem_total", 8192), key="f_mem_total")
        with mem3:
            gc_count = st.number_input("GC Pause Count", 0, 100000, st.session_state.get("f_gc_count", 10), key="f_gc_count")
        with mem4:
            gc_avg = st.number_input("GC Pause Avg (ms)", 0.0, 100000.0, st.session_state.get("f_gc_avg_ms", 50.0), key="f_gc_avg_ms")

        st.subheader("Response Times")
        rt1, rt2, rt3, rt4 = st.columns(4)
        with rt1:
            resp_avg = st.number_input("Avg (ms)", 0.0, 1000000.0, st.session_state.get("f_resp_avg", 300.0), key="f_resp_avg")
        with rt2:
            resp_p95 = st.number_input("p95 (ms)", 0.0, 1000000.0, st.session_state.get("f_resp_p95", 800.0), key="f_resp_p95")
        with rt3:
            resp_p99 = st.number_input("p99 (ms)", 0.0, 1000000.0, st.session_state.get("f_resp_p99", 1500.0), key="f_resp_p99")
        with rt4:
            slowest_ep = st.text_input("Slowest Endpoint", st.session_state.get("f_slowest_ep", "/api/data"), key="f_slowest_ep")

        st.subheader("Error Logs")
        error_logs = st.text_area("Paste log lines", st.session_state.get("f_error_logs", ""), height=150, key="f_error_logs")

        st.subheader("Trace Data")
        trace_data = st.text_area("Paste trace spans / output", st.session_state.get("f_trace_data", ""), height=150, key="f_trace_data")

        st.subheader("Configuration")
        cf1, cf2, cf3, cf4 = st.columns(4)
        with cf1:
            thread_pool = st.number_input("Thread Pool Size", 1, 10000, st.session_state.get("f_thread_pool", 200), key="f_thread_pool")
        with cf2:
            db_pool = st.number_input("DB Pool Size", 1, 1000, st.session_state.get("f_db_pool", 10), key="f_db_pool")
        with cf3:
            cache_enabled = st.checkbox("Cache Enabled", st.session_state.get("f_cache_enabled", False), key="f_cache_enabled")
        with cf4:
            timeout_ms = st.number_input("Timeout (ms)", 0, 300000, st.session_state.get("f_timeout_ms", 30000), key="f_timeout_ms")

        submitted = st.form_submit_button("💾 Save Metrics", use_container_width=True)
        if submitted:
            st.session_state.metrics = build_metrics_from_form()
            st.success("Metrics saved — switch to the Analysis tab.")


# ═══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Analysis
# ═══════════════════════════════════════════════════════════════════════════════
with tab_analysis:
    st.header("Bottleneck Analysis")

    if st.session_state.metrics is None:
        st.warning("No metrics loaded. Go to the **Input** tab first.")
    else:
        run_btn = st.button("▶ Run Analysis", type="primary", use_container_width=False)

        if run_btn:
            st.session_state.step_results = {}
            st.session_state.report = None
            st.session_state.analysis_running = True

            metrics = st.session_state.metrics
            model_key = st.session_state.get("sidebar_model", "gpt-4o-mini")

            # Output containers
            step_output_ph: dict[str, st.delta_generator.DeltaGenerator] = {}
            for step in STEPS:
                with st.expander(STEP_LABELS[step], expanded=False):
                    step_output_ph[step] = st.empty()

            correlation_ph = st.empty()
            status_ph = st.empty()

            def on_step(name: str, result) -> None:
                st.session_state.step_results[name] = result
                # Update sidebar checkmarks
                if name in step_placeholders:
                    step_placeholders[name].success(f"✅ {STEP_LABELS[name]}")
                # Show result in expander
                if name in step_output_ph:
                    if hasattr(result, "model_dump"):
                        step_output_ph[name].json(result.model_dump())
                    elif isinstance(result, dict):
                        step_output_ph[name].json(result)
                    elif isinstance(result, list):
                        step_output_ph[name].json(result)
                    else:
                        step_output_ph[name].write(result)
                # Show correlation narrative immediately
                if name == "correlate" and isinstance(result, dict):
                    correlation_ph.markdown(
                        f"**Root Cause:** {result.get('root_cause_summary', '')}\n\n"
                        f"**Cascade:** {result.get('cascade_explanation', '')}"
                    )

            with st.spinner("Running 6-tool analysis..."):
                try:
                    report = run_analysis(metrics, model_key, on_step_complete=on_step)
                    st.session_state.report = report
                    st.session_state.analysis_running = False
                    status_ph.success(f"✅ Analysis complete in {report.diagnosis_time_ms:,} ms — see Remediation tab for fixes.")
                except Exception as exc:
                    st.session_state.analysis_running = False
                    status_ph.error(f"Analysis failed: {exc}")

            # Store in ChromaDB
            if st.session_state.report:
                try:
                    store = get_store()
                    store.add(
                        f"{metrics.app_name} {metrics.environment}",
                        st.session_state.report.model_dump(),
                        model_key,
                    )
                except Exception:
                    pass

        elif st.session_state.report:
            report = st.session_state.report
            sev = report.severity
            badge_cls = f"badge-{sev.lower()}"
            st.markdown(f"### Severity: <span class='{badge_cls}'>{sev}</span>", unsafe_allow_html=True)
            st.markdown(f"**Root Cause:** {report.root_cause_summary}")
            st.markdown(f"**Cascade Explanation:** {report.cascade_explanation}")
            st.markdown("**Identified Bottlenecks:**")
            for b in report.bottlenecks:
                st.markdown(f"- {b}")
            with st.expander("Raw step results"):
                st.json(st.session_state.step_results)
        else:
            st.info("Click **Run Analysis** to start the 6-tool bottleneck diagnosis.")


# ═══════════════════════════════════════════════════════════════════════════════
# Tab 4 — Remediation
# ═══════════════════════════════════════════════════════════════════════════════
with tab_remediation:
    st.header("Remediation Plan")

    report = st.session_state.report
    if report is None:
        st.info("Run an analysis first to generate remediation steps.")
    else:
        sev = report.severity
        badge_cls = f"badge-{sev.lower()}"
        st.markdown(f"**{report.app_name}** — Severity: <span class='{badge_cls}'>{sev}</span>", unsafe_allow_html=True)
        st.caption(report.root_cause_summary)
        st.divider()

        if not report.remediations:
            st.warning("No remediation steps were generated.")
        else:
            for step in sorted(report.remediations, key=lambda s: s.priority):
                effort_color = {"Low": "green", "Medium": "orange", "High": "red"}.get(step.effort, "grey")
                impact_color = {"Low": "grey", "Medium": "orange", "High": "green"}.get(step.impact, "grey")

                st.markdown(f"""
<div class="rem-card">
  <div class="rem-title">Priority {step.priority}: {step.title}</div>
  <div class="rem-meta">
    Effort: <span style="color:{effort_color}">{step.effort}</span> &nbsp;|&nbsp;
    Impact: <span style="color:{impact_color}">{step.impact}</span>
  </div>
  <p style="color:#ccc; margin:6px 0 10px 0;">{step.description}</p>
</div>
""", unsafe_allow_html=True)

                if step.code_snippet:
                    lang = "yaml" if ":" in step.code_snippet and "=" not in step.code_snippet else "java" if report.app_name and "java" in str(st.session_state.metrics.app_type).lower() else "python"
                    st.code(step.code_snippet, language=lang)


# ═══════════════════════════════════════════════════════════════════════════════
# Tab 5 — History
# ═══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.header("Analysis History")

    store = get_store()
    total = store.count()
    st.caption(f"Total analyses stored: {total}")

    search_query = st.text_input("🔍 Search past analyses", placeholder="e.g. DB pool exhaustion, high GC, OrderService")

    if search_query:
        results = store.search(search_query, n_results=5)
        st.subheader(f"Results for: {search_query}")
    else:
        results = store.get_recent(n=10)
        st.subheader("Recent Analyses")

    if not results:
        st.info("No analyses stored yet. Run an analysis to populate history.")
    else:
        for item in results:
            result = item.get("result", {})
            app_name = result.get("app_name", item.get("input", "Unknown"))
            severity = result.get("severity", "?")
            timestamp = item.get("timestamp", "")[:19].replace("T", " ")
            model_key = item.get("model_key", "")

            with st.expander(f"[{severity}] {app_name} — {timestamp}"):
                st.caption(f"Model: {model_key} | ID: {item['id'][:8]}")
                st.write(result.get("root_cause_summary", ""))
                bottlenecks = result.get("bottlenecks", [])
                if bottlenecks:
                    for b in bottlenecks:
                        st.markdown(f"- {b}")
                if st.button("📥 Load this report", key=f"load_{item['id']}"):
                    from perf_bot.models import BottleneckReport, RemediationStep
                    rems = [RemediationStep(**r) for r in result.get("remediations", [])]
                    st.session_state.report = BottleneckReport(
                        app_name=result.get("app_name", ""),
                        severity=result.get("severity", ""),
                        root_cause_summary=result.get("root_cause_summary", ""),
                        bottlenecks=result.get("bottlenecks", []),
                        cascade_explanation=result.get("cascade_explanation", ""),
                        remediations=rems,
                        diagnosis_time_ms=result.get("diagnosis_time_ms", 0),
                        model_used=result.get("model_used", ""),
                    )
                    st.success("Report loaded — check the Remediation tab.")
