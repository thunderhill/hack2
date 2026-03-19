"""Streamlit UI for Manufacturing Quality Inspection with MCP agent + ChromaDB history."""

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

from quality_inspection.agent import generate_inspection_report
from quality_inspection.config import MODEL_OPTIONS
from chroma_store import ChromaStore

store = ChromaStore("quality_inspection")

st.set_page_config(page_title="Quality Inspection Assistant (MCP)", page_icon="🔬", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    product_type = st.text_input("Product Type (optional)", placeholder="e.g., Automotive brake pad")
    st.divider()
    st.metric("Analyses Stored", store.count())

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_analyze, tab_history, tab_search = st.tabs(["Analyze", "History", "Search"])

# ── Analyze Tab ──────────────────────────────────────────────────────────────
with tab_analyze:
    st.title("🔬 Manufacturing Quality Inspection Assistant")
    st.caption("Enter inspection data to generate an AI-powered quality report.")

    SAMPLE_DATA = """Product ID: BP-2024-0315-LOT42
Inspection Date: 2024-03-15
Inspector: QC-Team-A
Batch Size: 500 units

Observations:
- 23 units show surface cracks on the friction material (length 2-5mm)
- 8 units have dimensional deviation: thickness 9.2mm vs required 10.0mm +-0.2mm
- 3 units show delamination at friction-backing plate interface
- 12 units have cosmetic surface blemishes (does not affect function)
- Temperature sensor readings during cure process: Max 185C (limit: 180C) on 2024-03-14
- Hardness measurements: 45-52 HRB (spec: 48-55 HRB)
- 2 units failed shear strength test: 850N vs minimum 1000N required"""

    inspection_data = st.text_area(
        "Inspection Data",
        value=SAMPLE_DATA,
        height=280,
        placeholder="Enter inspection observations, measurements, and defect descriptions...",
    )

    if st.button("Generate Report", type="primary") and inspection_data.strip():
        with st.spinner("Generating quality inspection report..."):
            try:
                report = generate_inspection_report(inspection_data, model_key, product_type)
                result_dict = report.model_dump()

                # Store in ChromaDB
                store.add(inspection_data, result_dict, model_key)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Status", report.overall_quality_status)
                col2.metric("Quality Score", f"{report.quality_score:.1f}/100")
                col3.metric("Defects Found", report.defect_count)
                col4.metric("Disposition", report.disposition.upper())

                st.subheader("Defect Catalog")
                for d in report.defects:
                    severity_icon = {"critical": "🔴", "major": "🟠", "minor": "🟡"}.get(d.severity, "⚪")
                    with st.expander(f"{severity_icon} {d.defect_id} — {d.defect_type.upper()} | {d.affected_component}"):
                        st.write(d.description)
                        st.write(f"**Severity:** {d.severity}")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.subheader("Root Cause Analysis")
                    st.warning(report.root_cause_analysis)
                    st.subheader("Corrective Actions")
                    for i, action in enumerate(report.corrective_actions, 1):
                        st.write(f"{i}. {action}")
                with col_b:
                    st.subheader("Preventive Measures")
                    for measure in report.preventive_measures:
                        st.write(f"• {measure}")
                    st.subheader("Inspector Notes")
                    st.info(report.inspector_notes)
            except Exception as e:
                st.error(f"Report generation failed: {e}")

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.title("📋 Inspection History")
    st.caption("Browse past quality inspection reports stored in ChromaDB.")

    recent = store.get_recent(20)
    if not recent:
        st.info("No inspections yet. Run an analysis from the Analyze tab to get started.")
    for item in recent:
        r = item["result"]
        with st.expander(
            f"**{r.get('overall_quality_status', 'N/A')}** — Score: {r.get('quality_score', 'N/A')} | Defects: {r.get('defect_count', 'N/A')} | {item['timestamp'][:19]}"
        ):
            st.text_area("Input Data", item["input"], height=120, disabled=True, key=f"hist_{item['id']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Status", r.get("overall_quality_status", "N/A"))
            col2.metric("Quality Score", f"{r.get('quality_score', 0):.1f}/100")
            col3.metric("Defects Found", r.get("defect_count", "N/A"))
            col4.metric("Disposition", r.get("disposition", "N/A").upper())
            st.warning(r.get("root_cause_analysis", ""))
            if r.get("corrective_actions"):
                st.subheader("Corrective Actions")
                for i, action in enumerate(r["corrective_actions"], 1):
                    st.write(f"{i}. {action}")
            if r.get("preventive_measures"):
                st.subheader("Preventive Measures")
                for measure in r["preventive_measures"]:
                    st.write(f"• {measure}")
            st.info(r.get("inspector_notes", ""))
            st.caption(f"Model: {item.get('model_key', 'N/A')}")

# ── Search Tab ───────────────────────────────────────────────────────────────
with tab_search:
    st.title("🔎 Search Past Inspections")
    st.caption("Semantic search across all stored inspection reports using ChromaDB.")

    query = st.text_input("Search query", placeholder="e.g. surface cracks brake pad")
    n_results = st.slider("Max results", 1, 20, 5)

    if st.button("Search", type="primary") and query.strip():
        results = store.search(query, n_results)
        if not results:
            st.warning("No matching inspections found.")
        for item in results:
            r = item["result"]
            similarity = f"{(1 - item.get('distance', 0)) * 100:.0f}%" if item.get("distance") is not None else "N/A"
            with st.expander(
                f"**{r.get('overall_quality_status', 'N/A')}** — Similarity: {similarity} | Score: {r.get('quality_score', 'N/A')} | {item['timestamp'][:19]}"
            ):
                st.text_area("Input Data", item["input"], height=120, disabled=True, key=f"search_{item['id']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Status", r.get("overall_quality_status", "N/A"))
                col2.metric("Quality Score", f"{r.get('quality_score', 0):.1f}/100")
                col3.metric("Defects Found", r.get("defect_count", "N/A"))
                col4.metric("Disposition", r.get("disposition", "N/A").upper())
                st.warning(r.get("root_cause_analysis", ""))
                if r.get("corrective_actions"):
                    st.subheader("Corrective Actions")
                    for i, action in enumerate(r["corrective_actions"], 1):
                        st.write(f"{i}. {action}")
                st.info(r.get("inspector_notes", ""))
