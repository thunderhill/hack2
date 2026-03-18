import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Quality Inspection Assistant", page_icon="🔬", layout="wide")
st.title("🔬 Manufacturing Quality Inspection Assistant")
st.caption("Enter inspection data to generate an AI-powered quality report.")

from quality_inspection.config import MODEL_OPTIONS

with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    product_type = st.text_input("Product Type (optional)", placeholder="e.g., Automotive brake pad")

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
    from quality_inspection.agent import generate_inspection_report
    with st.spinner("Generating quality inspection report..."):
        try:
            report = generate_inspection_report(inspection_data, model_key, product_type)

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
