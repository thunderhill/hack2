"""Streamlit UI for Infrastructure Change Explainer with MCP agent + ChromaDB history."""

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

from infra_explainer.agent import explain_change
from infra_explainer.config import MODEL_OPTIONS
from chroma_store import ChromaStore

store = ChromaStore("infra_explainer")

st.set_page_config(page_title="Infrastructure Change Explainer (MCP)", page_icon="🏗️", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    environment = st.text_input("Target Environment", placeholder="e.g., Production, Staging")
    st.divider()
    st.metric("Analyses Stored", store.count())

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_analyze, tab_history, tab_search = st.tabs(["Analyze", "History", "Search"])

# ── Analyze Tab ──────────────────────────────────────────────────────────────
with tab_analyze:
    st.title("🏗️ Infrastructure Change Request Explainer")
    st.caption("Paste an infrastructure change to get a plain-English explanation and risk assessment.")

    SAMPLE_CHANGE = """# Terraform Plan Output

Resource actions are indicated with the following symbols:
  + create
  ~ update in-place
  - destroy

Terraform will perform the following actions:

  # aws_security_group.web_sg will be updated in-place
  ~ resource "aws_security_group" "web_sg" {
      id   = "sg-0abc123def456789"
      name = "web-server-sg"

      ~ ingress {
          ~ cidr_blocks = [
              - "10.0.0.0/8",
              + "0.0.0.0/0",
            ]
            from_port   = 443
            protocol    = "tcp"
            to_port     = 443
        }
    }

  # aws_autoscaling_group.web will be updated in-place
  ~ resource "aws_autoscaling_group" "web" {
      ~ max_size = 3 -> 10
      ~ min_size = 1 -> 3
      ~ desired_capacity = 2 -> 6
    }

Plan: 0 to add, 2 to change, 0 to destroy."""

    change_input = st.text_area(
        "Infrastructure Change Request",
        value=SAMPLE_CHANGE,
        height=280,
        placeholder="Paste your Terraform plan, Kubernetes diff, Ansible playbook, etc...",
    )

    if st.button("Explain & Assess Change", type="primary") and change_input.strip():
        with st.spinner("Analyzing infrastructure change..."):
            try:
                result = explain_change(change_input, model_key, environment)
                result_dict = result.model_dump()

                # Store in ChromaDB
                store.add(change_input, result_dict, model_key)

                risk_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(result.risk_level, "⚪")
                approval_icon = {"APPROVE": "✅", "APPROVE_WITH_CONDITIONS": "⚠️", "REJECT": "❌", "NEEDS_MORE_INFO": "❓"}.get(result.approval_recommendation, "❓")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Change Type", result.change_type.upper())
                col2.metric("Risk Level", f"{risk_icon} {result.risk_level.upper()}")
                col3.metric("Nature", result.change_nature)
                col4.metric("Recommendation", f"{approval_icon} {result.approval_recommendation}")

                st.subheader("Summary")
                st.info(result.summary)

                st.subheader("Plain English Explanation")
                st.write(result.plain_english)

                st.subheader("Resources Affected")
                for resource in result.resources_affected:
                    st.write(f"• `{resource}`")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.subheader("Risk Assessment")
                    for risk in result.risks:
                        with st.expander(f"Risk: {risk.risk[:60]}"):
                            st.write(f"**Likelihood:** {risk.likelihood} | **Impact:** {risk.impact}")
                            st.write(risk.risk)

                    st.subheader("Rollback")
                    rollback_status = "✅ Possible" if result.rollback_possible else "❌ Not possible"
                    st.write(f"**Status:** {rollback_status}")
                    if result.rollback_procedure != "N/A":
                        st.write(result.rollback_procedure)

                with col_b:
                    st.subheader("Review Checklist")
                    for item in result.review_checklist:
                        st.checkbox(item, key=item)
            except Exception as e:
                st.error(f"Analysis failed: {e}")

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.title("📋 Analysis History")
    st.caption("Browse past infrastructure change analyses stored in ChromaDB.")

    recent = store.get_recent(20)
    if not recent:
        st.info("No analyses yet. Run an analysis from the Analyze tab to get started.")
    for item in recent:
        r = item["result"]
        risk_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(r.get("risk_level", ""), "⚪")
        with st.expander(
            f"**{r.get('change_type', 'N/A').upper()}** — {risk_icon} {r.get('risk_level', 'N/A').upper()} | {item['timestamp'][:19]}"
        ):
            st.text_area("Change Request", item["input"], height=120, disabled=True, key=f"hist_{item['id']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Change Type", r.get("change_type", "N/A").upper())
            col2.metric("Risk Level", r.get("risk_level", "N/A").upper())
            col3.metric("Nature", r.get("change_nature", "N/A"))
            col4.metric("Recommendation", r.get("approval_recommendation", "N/A"))
            st.info(r.get("summary", ""))
            st.write(r.get("plain_english", ""))
            if r.get("resources_affected"):
                st.write("**Resources:** " + ", ".join(f"`{res}`" for res in r["resources_affected"]))
            st.caption(f"Model: {item.get('model_key', 'N/A')}")

# ── Search Tab ───────────────────────────────────────────────────────────────
with tab_search:
    st.title("🔎 Search Past Analyses")
    st.caption("Semantic search across all stored analyses using ChromaDB.")

    query = st.text_input("Search query", placeholder="e.g. security group CIDR change")
    n_results = st.slider("Max results", 1, 20, 5)

    if st.button("Search", type="primary") and query.strip():
        results = store.search(query, n_results)
        if not results:
            st.warning("No matching analyses found.")
        for item in results:
            r = item["result"]
            similarity = f"{(1 - item.get('distance', 0)) * 100:.0f}%" if item.get("distance") is not None else "N/A"
            risk_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(r.get("risk_level", ""), "⚪")
            with st.expander(
                f"**{r.get('change_type', 'N/A').upper()}** — Similarity: {similarity} | {risk_icon} {r.get('risk_level', 'N/A').upper()} | {item['timestamp'][:19]}"
            ):
                st.text_area("Change Request", item["input"], height=120, disabled=True, key=f"search_{item['id']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Change Type", r.get("change_type", "N/A").upper())
                col2.metric("Risk Level", r.get("risk_level", "N/A").upper())
                col3.metric("Nature", r.get("change_nature", "N/A"))
                col4.metric("Recommendation", r.get("approval_recommendation", "N/A"))
                st.info(r.get("summary", ""))
                st.write(r.get("plain_english", ""))
