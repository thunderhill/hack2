import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Capacity Planning Advisor", page_icon="📊", layout="wide")
st.title("📊 Infrastructure Capacity Planning Advisor")
st.caption("Enter current metrics and growth projections for AI-powered capacity recommendations.")

from capacity_planning.config import MODEL_OPTIONS

with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    growth_projection = st.text_input("Growth Projection", placeholder="e.g., 40% user growth in 6 months")
    sla_requirements = st.text_input("SLA Requirements", placeholder="e.g., 99.9% uptime, <200ms response")

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
    from capacity_planning.agent import generate_capacity_plan
    with st.spinner("Generating capacity plan..."):
        try:
            plan = generate_capacity_plan(metrics_input, model_key, growth_projection, sla_requirements)

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
