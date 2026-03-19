"""Streamlit UI for Capacity Planning Advisor with MCP agent + ChromaDB history."""

import os, ssl, warnings

os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

from capacity_planning.agent import generate_capacity_plan
from capacity_planning.config import MODEL_OPTIONS
from capacity_planning.guardrails import run_input_guardrails, run_output_guardrails
from chroma_store import ChromaStore

store = ChromaStore("capacity_planning")

st.set_page_config(page_title="Capacity Planning Advisor (MCP)", page_icon="📊", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    growth_projection = st.text_input("Growth Projection", placeholder="e.g., 40% user growth in 6 months")
    sla_requirements = st.text_input("SLA Requirements", placeholder="e.g., 99.9% uptime, <200ms response")
    st.divider()
    st.metric("Analyses Stored", store.count())

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_analyze, tab_history, tab_search = st.tabs(["Analyze", "History", "Search"])

# ── Analyze Tab ──────────────────────────────────────────────────────────────
with tab_analyze:
    st.title("📊 Infrastructure Capacity Planning Advisor")
    st.caption("Enter current metrics and growth projections for AI-powered capacity recommendations.")

    SAMPLE_METRICS = """Infrastructure: AWS Production Environment
Date: 2024-03-15

Compute (EC2):
- Web tier: 4x m5.large (8 vCPU, 32GB RAM) — Avg CPU: 78%, Peak: 94%
- App tier: 3x m5.xlarge (16 vCPU, 64GB RAM) — Avg CPU: 65%, Peak: 89%
- Current cost: $2,200/month

Database (RDS PostgreSQL):
- Instance: db.r5.2xlarge (8 vCPU, 64GB RAM)
- CPU utilization: 82% average, 98% peak during business hours
- Storage: 1.8TB used of 2TB allocated
- Read replica: 1x db.r5.large (overloaded, CPU 91%)
- Current cost: $1,800/month

Cache (ElastiCache Redis):
- 2x cache.r6g.large — Memory: 87% used
- Cache hit rate: 72% (target: >90%)
- Current cost: $320/month

Storage (S3 + EBS):
- S3: 45TB used, growing ~500GB/week
- EBS volumes: 8TB total, 78% used
- Current cost: $980/month

Network:
- Load balancer: 12,000 req/min avg, 35,000 req/min peak
- Current cost: $180/month

Total monthly infrastructure cost: $5,480"""

    metrics_input = st.text_area(
        "Current Infrastructure Metrics",
        value=SAMPLE_METRICS,
        height=320,
        placeholder="Enter current CPU, memory, storage, network utilization and costs...",
    )

    if st.button("Generate Capacity Plan", type="primary") and metrics_input.strip():
        # ── Input Guardrails ─────────────────────────────────────────
        guard = run_input_guardrails(metrics_input)
        with st.expander("Guardrail Checks", expanded=not guard.passed):
            for check in guard.checks:
                icon = "✅" if check.passed else "❌"
                st.write(f"{icon} **{check.name}**: {check.message}")
            if guard.pii_detected:
                st.warning(f"PII detected and masked: {', '.join(guard.pii_detected)}")
            if guard.warnings:
                for w in guard.warnings:
                    st.caption(f"⚠️ {w}")

        if guard.blocked:
            st.error(f"Input blocked: {guard.block_reason}")
        else:
          with st.spinner("Generating capacity plan..."):
            try:
                plan = generate_capacity_plan(metrics_input, model_key, growth_projection, sla_requirements)
                result_dict = plan.model_dump()

                # ── Output Guardrails ────────────────────────────────
                out_guard = run_output_guardrails(plan)
                if out_guard.warnings:
                    with st.expander("Output Guardrail Warnings"):
                        for w in out_guard.warnings:
                            st.warning(w)

                # Store in ChromaDB
                store.add(metrics_input, result_dict, model_key)

                risk_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(plan.capacity_risk_level, "⚪")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Risk Level", f"{risk_icon} {plan.capacity_risk_level.upper()}")
                col2.metric("Scaling Strategy", plan.scaling_strategy.upper())
                col3.metric("Cost Estimate", plan.total_cost_estimate)
                col4.metric("Timeline", plan.timeline)

                st.subheader("Executive Summary")
                st.info(plan.executive_summary)

                st.subheader("Current Bottlenecks")
                for bottleneck in plan.bottlenecks:
                    st.error(f"⚠️ {bottleneck}")

                st.subheader("Recommendations")
                for rec in plan.recommendations:
                    urgency_color = {"immediate": "🔴", "within_month": "🟠", "within_quarter": "🟡", "planned": "🟢"}.get(rec.urgency, "⚪")
                    with st.expander(f"{urgency_color} {rec.resource_type.upper()} — {rec.urgency.replace('_', ' ').title()} | {rec.estimated_cost_impact}"):
                        col_a, col_b = st.columns(2)
                        col_a.write(f"**Current:** {rec.current_state}")
                        col_b.write(f"**Recommended:** {rec.recommended_state}")

                col_c, col_d = st.columns(2)
                with col_c:
                    st.subheader("Cost Optimizations")
                    for opt in plan.optimization_opportunities:
                        st.write(f"💡 {opt}")
                with col_d:
                    st.subheader("Risk of Inaction")
                    st.error(plan.risk_if_not_acted)
            except Exception as e:
                st.error(f"Planning failed: {e}")

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.title("📋 Analysis History")
    st.caption("Browse past capacity planning analyses stored in ChromaDB.")

    recent = store.get_recent(20)
    if not recent:
        st.info("No analyses yet. Run an analysis from the Analyze tab to get started.")
    for item in recent:
        r = item["result"]
        risk_level = r.get("capacity_risk_level", "N/A")
        risk_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(risk_level, "⚪")
        with st.expander(
            f"**{risk_icon} {risk_level.upper()}** — {r.get('scaling_strategy', 'N/A').upper()} | {item['timestamp'][:19]}"
        ):
            st.text_area("Input Metrics", item["input"], height=120, disabled=True, key=f"hist_{item['id']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Risk Level", risk_level.upper())
            col2.metric("Scaling Strategy", r.get("scaling_strategy", "N/A").upper())
            col3.metric("Cost Estimate", r.get("total_cost_estimate", "N/A"))
            col4.metric("Timeline", r.get("timeline", "N/A"))
            st.info(r.get("executive_summary", ""))
            st.subheader("Bottlenecks")
            for b in r.get("bottlenecks", []):
                st.error(f"⚠️ {b}")
            st.subheader("Recommendations")
            for rec in r.get("recommendations", []):
                st.write(f"- **{rec.get('resource_type', 'N/A')}**: {rec.get('current_state', '')} → {rec.get('recommended_state', '')} ({rec.get('estimated_cost_impact', '')})")
            st.caption(f"Model: {item.get('model_key', 'N/A')}")

# ── Search Tab ───────────────────────────────────────────────────────────────
with tab_search:
    st.title("🔎 Search Past Analyses")
    st.caption("Semantic search across all stored capacity planning analyses using ChromaDB.")

    query = st.text_input("Search query", placeholder="e.g. database CPU bottleneck")
    n_results = st.slider("Max results", 1, 20, 5)

    if st.button("Search", type="primary") and query.strip():
        results = store.search(query, n_results)
        if not results:
            st.warning("No matching analyses found.")
        for item in results:
            r = item["result"]
            risk_level = r.get("capacity_risk_level", "N/A")
            risk_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(risk_level, "⚪")
            similarity = f"{(1 - item.get('distance', 0)) * 100:.0f}%" if item.get("distance") is not None else "N/A"
            with st.expander(
                f"**{risk_icon} {risk_level.upper()}** — Similarity: {similarity} | {item['timestamp'][:19]}"
            ):
                st.text_area("Input Metrics", item["input"], height=120, disabled=True, key=f"search_{item['id']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Risk Level", risk_level.upper())
                col2.metric("Scaling Strategy", r.get("scaling_strategy", "N/A").upper())
                col3.metric("Cost Estimate", r.get("total_cost_estimate", "N/A"))
                col4.metric("Timeline", r.get("timeline", "N/A"))
                st.info(r.get("executive_summary", ""))
                for b in r.get("bottlenecks", []):
                    st.error(f"⚠️ {b}")
