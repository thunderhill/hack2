"""Streamlit UI for DevOps Incident Report Generator with MCP agent + ChromaDB history."""

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

from incident_report.agent import generate_incident_report
from incident_report.config import MODEL_OPTIONS
from chroma_store import ChromaStore

store = ChromaStore("incident_report")

st.set_page_config(page_title="Incident Report Generator (MCP)", page_icon="🚨", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    service_name = st.text_input("Service/System Name", placeholder="e.g., Payment API, Auth Service")
    st.divider()
    st.metric("Reports Stored", store.count())

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_generate, tab_history, tab_search = st.tabs(["Generate", "History", "Search"])

# ── Generate Tab ─────────────────────────────────────────────────────────────
with tab_generate:
    st.title("🚨 DevOps Incident Report Generator")
    st.caption("Paste incident notes and timeline to auto-generate a professional post-incident report.")

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
        with st.spinner("Generating post-incident report..."):
            try:
                report = generate_incident_report(incident_notes, model_key, service_name)
                result_dict = report.model_dump()

                # Store in ChromaDB
                store.add(incident_notes, result_dict, model_key)

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

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.title("📋 Report History")
    st.caption("Browse past incident reports stored in ChromaDB.")

    recent = store.get_recent(20)
    if not recent:
        st.info("No reports yet. Generate a report from the Generate tab to get started.")
    for item in recent:
        r = item["result"]
        sev_icon = {"SEV1": "🔴", "SEV2": "🟠", "SEV3": "🟡", "SEV4": "🟢"}.get(r.get("severity", ""), "⚪")
        with st.expander(
            f"{sev_icon} **{r.get('title', 'N/A')}** — {r.get('severity', 'N/A')} | {item['timestamp'][:19]}"
        ):
            st.text_area("Input Notes", item["input"], height=120, disabled=True, key=f"hist_{item['id']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Incident ID", r.get("incident_id", "N/A"))
            col2.metric("Severity", r.get("severity", "N/A"))
            col3.metric("Total Duration", r.get("total_duration", "N/A"))
            col4.metric("Users Affected", r.get("users_affected", "N/A"))
            st.info(r.get("executive_summary", ""))
            st.error(r.get("root_cause", ""))
            if r.get("action_items"):
                st.subheader("Action Items")
                for ai in r["action_items"]:
                    st.write(f"• **{ai.get('priority', 'N/A')}** — {ai.get('action', 'N/A')} (Owner: {ai.get('owner', 'N/A')})")
            st.caption(f"Model: {item.get('model_key', 'N/A')}")

# ── Search Tab ───────────────────────────────────────────────────────────────
with tab_search:
    st.title("🔎 Search Past Reports")
    st.caption("Semantic search across all stored incident reports using ChromaDB.")

    query = st.text_input("Search query", placeholder="e.g. database connection pool exhaustion")
    n_results = st.slider("Max results", 1, 20, 5)

    if st.button("Search", type="primary") and query.strip():
        results = store.search(query, n_results)
        if not results:
            st.warning("No matching reports found.")
        for item in results:
            r = item["result"]
            similarity = f"{(1 - item.get('distance', 0)) * 100:.0f}%" if item.get("distance") is not None else "N/A"
            sev_icon = {"SEV1": "🔴", "SEV2": "🟠", "SEV3": "🟡", "SEV4": "🟢"}.get(r.get("severity", ""), "⚪")
            with st.expander(
                f"{sev_icon} **{r.get('title', 'N/A')}** — Similarity: {similarity} | {item['timestamp'][:19]}"
            ):
                st.text_area("Input Notes", item["input"], height=120, disabled=True, key=f"search_{item['id']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Incident ID", r.get("incident_id", "N/A"))
                col2.metric("Severity", r.get("severity", "N/A"))
                col3.metric("Total Duration", r.get("total_duration", "N/A"))
                col4.metric("Users Affected", r.get("users_affected", "N/A"))
                st.info(r.get("executive_summary", ""))
                st.error(r.get("root_cause", ""))
