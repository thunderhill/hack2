import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Pipeline Anomaly Explainer", page_icon="🔍", layout="wide")
st.title("🔍 Pipeline Anomaly Explanation Agent")
st.caption("Paste a CI/CD pipeline log snippet to get an AI-powered anomaly analysis.")

from pipeline_anomaly.config import MODEL_OPTIONS

with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)

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
    from pipeline_anomaly.agent import explain_anomaly
    with st.spinner("Analyzing pipeline log..."):
        try:
            result = explain_anomaly(log_input, model_key)

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
