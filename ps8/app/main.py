import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Incident Report Generator", page_icon="🚨", layout="wide")
st.title("🚨 DevOps Incident Report Generator")
st.caption("Paste incident notes and timeline to auto-generate a professional post-incident report.")

from incident_report.config import MODEL_OPTIONS

with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    service_name = st.text_input("Service/System Name", placeholder="e.g., Payment API, Auth Service")

SAMPLE_NOTES = """Incident Date: 2024-03-15

14:32 - PagerDuty alert: Payment API error rate >5% (threshold: 1%)
14:33 - On-call engineer John D. acknowledged alert
14:35 - Checked dashboards: error rate at 23%, P99 latency 8s (normal: 200ms)
14:38 - Identified spike in DB connection errors in logs
14:42 - DB team contacted, confirmed connection pool exhaustion
14:45 - Root cause found: deployment at 14:20 changed DB connection pool size from 100 to 10 (config typo)
14:48 - Rolled back deployment to previous version
14:52 - Error rate dropped to <0.5%, latency normal
14:55 - Incident declared resolved
15:30 - Post-incident review meeting scheduled

Impact: Payment processing failed for ~23 minutes, estimated 4,200 transactions failed
Customers complained via support chat, 127 tickets opened
Revenue impact: ~$85,000 in failed transactions (users can retry)

Team notes: Alert fired quickly (good), but took 13 minutes to identify root cause. DB team very helpful.
No runbook existed for connection pool issues."""

incident_notes = st.text_area(
    "Incident Notes & Timeline",
    value=SAMPLE_NOTES,
    height=300,
    placeholder="Paste your incident timeline, Slack messages, alert history...",
)

if st.button("Generate Incident Report", type="primary") and incident_notes.strip():
    from incident_report.agent import generate_incident_report
    with st.spinner("Generating post-incident report..."):
        try:
            report = generate_incident_report(incident_notes, model_key, service_name)

            sev_icon = {"SEV1": "🔴", "SEV2": "🟠", "SEV3": "🟡", "SEV4": "🟢"}.get(report.severity, "⚪")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Incident ID", report.incident_id)
            col2.metric("Severity", f"{sev_icon} {report.severity}")
            col3.metric("Total Duration", report.total_duration)
            col4.metric("Users Affected", report.users_affected)

            st.subheader(report.title)
            st.info(report.executive_summary)

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Time to Detect", report.time_to_detect)
            col_b.metric("Time to Resolve", report.time_to_resolve)
            col_c.metric("Status", report.status.upper())

            tab1, tab2, tab3, tab4 = st.tabs(["Timeline", "Root Cause", "Response Quality", "Action Items"])

            with tab1:
                st.write(f"**Affected Services:** {', '.join(report.affected_services)}")
                st.write(f"**Customer Impact:** {report.customer_impact}")
                for event in report.timeline:
                    actor_icon = {"system": "🤖", "engineer": "👤", "automated": "⚙️"}.get(event.actor, "•")
                    st.write(f"`{event.timestamp}` {actor_icon} {event.event}")

            with tab2:
                st.subheader("Root Cause")
                st.error(report.root_cause)
                st.subheader("Contributing Factors")
                for factor in report.contributing_factors:
                    st.write(f"• {factor}")
                st.subheader("Lessons Learned")
                st.info(report.lessons_learned)

            with tab3:
                col_w, col_b2 = st.columns(2)
                with col_w:
                    st.subheader("✅ What Went Well")
                    for item in report.what_went_well:
                        st.write(f"• {item}")
                with col_b2:
                    st.subheader("❌ What Went Wrong")
                    for item in report.what_went_wrong:
                        st.write(f"• {item}")

            with tab4:
                for item in report.action_items:
                    priority_icon = {"P1": "🔴", "P2": "🟠", "P3": "🟡"}.get(item.priority, "⚪")
                    with st.expander(f"{priority_icon} {item.priority} | {item.action[:70]}"):
                        st.write(f"**Owner:** {item.owner}")
                        st.write(f"**Due:** {item.due_date}")
                        st.write(f"**Action:** {item.action}")
        except Exception as e:
            st.error(f"Report generation failed: {e}")
