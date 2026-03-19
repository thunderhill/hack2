"""Streamlit UI for Pipeline Anomaly Explainer with MCP agent + ChromaDB history."""

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

from pipeline_anomaly.agent import explain_anomaly
from pipeline_anomaly.config import MODEL_OPTIONS
from chroma_store import ChromaStore

store = ChromaStore("pipeline_anomaly")

st.set_page_config(page_title="Pipeline Anomaly Explainer (MCP)", page_icon="🔍", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    st.divider()
    st.metric("Analyses Stored", store.count())

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_analyze, tab_history, tab_search = st.tabs(["Analyze", "History", "Search"])

# ── Analyze Tab ──────────────────────────────────────────────────────────────
with tab_analyze:
    st.title("🔍 Pipeline Anomaly Explanation Agent")
    st.caption("Paste a CI/CD pipeline log snippet to get an AI-powered anomaly analysis.")

    SAMPLE_LOG = """[2024-03-15 14:23:11] Starting build #1234 for branch: main
[2024-03-15 14:23:12] Pulling Docker image: node:18-alpine
[2024-03-15 14:23:15] Running npm install...
[2024-03-15 14:23:45] npm ERR! code ERESOLVE
[2024-03-15 14:23:45] npm ERR! ERESOLVE unable to resolve dependency tree
[2024-03-15 14:23:45] npm ERR! peer dep missing: react@^17.0.0, required by react-router-dom@5.3.4
[2024-03-15 14:23:45] npm ERR! Conflicting peer dependency: react@18.2.0
[2024-03-15 14:23:45] npm ERR! Fix the upstream dependency conflict
[2024-03-15 14:23:46] Build failed with exit code 1
[2024-03-15 14:23:46] Pipeline stage 'install-dependencies' failed after 31s
[2024-03-15 14:23:47] Sending failure notification to team-channel"""

    log_input = st.text_area(
        "Pipeline Log Snippet",
        value=SAMPLE_LOG,
        height=250,
        placeholder="Paste your pipeline log here...",
    )

    if st.button("Analyze Anomaly", type="primary") and log_input.strip():
        with st.spinner("Analyzing pipeline log via MCP agent..."):
            try:
                result = explain_anomaly(log_input, model_key)
                result_dict = result.model_dump()

                # Store in ChromaDB
                store.add(log_input, result_dict, model_key)

                col1, col2, col3 = st.columns(3)
                col1.metric("Anomaly Type", result.anomaly_type)
                col2.metric("Severity", result.severity.upper())
                col3.metric("Affected Stage", result.affected_stage)

                st.subheader("Plain English Summary")
                st.info(result.plain_english_summary)

                st.subheader("Root Cause")
                st.error(result.root_cause)

                col_a, col_b = st.columns(2)
                with col_a:
                    st.subheader("Remediation Steps")
                    for i, step in enumerate(result.remediation_steps, 1):
                        st.write(f"{i}. {step}")
                with col_b:
                    st.subheader("Prevention Tips")
                    for tip in result.prevention_tips:
                        st.write(f"• {tip}")
            except Exception as e:
                st.error(f"Analysis failed: {e}")

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.title("📋 Analysis History")
    st.caption("Browse past pipeline anomaly analyses stored in ChromaDB.")

    recent = store.get_recent(20)
    if not recent:
        st.info("No analyses yet. Run an analysis from the Analyze tab to get started.")
    for item in recent:
        r = item["result"]
        with st.expander(
            f"**{r.get('anomaly_type', 'N/A')}** — {r.get('severity', 'N/A').upper()} | {item['timestamp'][:19]}"
        ):
            st.text_area("Input Log", item["input"], height=120, disabled=True, key=f"hist_{item['id']}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Anomaly Type", r.get("anomaly_type", "N/A"))
            col2.metric("Severity", r.get("severity", "N/A").upper())
            col3.metric("Affected Stage", r.get("affected_stage", "N/A"))
            st.info(r.get("plain_english_summary", ""))
            st.error(r.get("root_cause", ""))
            st.caption(f"Model: {item.get('model_key', 'N/A')}")

# ── Search Tab ───────────────────────────────────────────────────────────────
with tab_search:
    st.title("🔎 Search Past Analyses")
    st.caption("Semantic search across all stored analyses using ChromaDB.")

    query = st.text_input("Search query", placeholder="e.g. npm dependency conflict")
    n_results = st.slider("Max results", 1, 20, 5)

    if st.button("Search", type="primary") and query.strip():
        results = store.search(query, n_results)
        if not results:
            st.warning("No matching analyses found.")
        for item in results:
            r = item["result"]
            similarity = f"{(1 - item.get('distance', 0)) * 100:.0f}%" if item.get("distance") is not None else "N/A"
            with st.expander(
                f"**{r.get('anomaly_type', 'N/A')}** — Similarity: {similarity} | {item['timestamp'][:19]}"
            ):
                st.text_area("Input Log", item["input"], height=120, disabled=True, key=f"search_{item['id']}")
                col1, col2, col3 = st.columns(3)
                col1.metric("Anomaly Type", r.get("anomaly_type", "N/A"))
                col2.metric("Severity", r.get("severity", "N/A").upper())
                col3.metric("Affected Stage", r.get("affected_stage", "N/A"))
                st.info(r.get("plain_english_summary", ""))
                st.error(r.get("root_cause", ""))
