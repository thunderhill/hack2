import os, ssl, warnings

# ── SSL bypass — MUST be before any other import ──────────────────────────────
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(override=True)

import io
import json
import pandas as pd
import streamlit as st

from eda_report.config import MODEL_OPTIONS, get_llm_client, get_model
from eda_report.guardrails import validate_dataframe
from eda_report.infer import infer_columns
from eda_report.preprocess import impute_nulls, parse_datetimes
from eda_report.profile import build_profile
from eda_report import charts
from eda_report.insights import get_section_narrative, get_executive_summary
from chroma_store import ChromaStore

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EDA Report Generator — PS11",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0e0e1a; }
[data-testid="stSidebar"] { background: #13132a; border-right: 1px solid #2a2a4a; }

.section-header {
    padding: 16px 24px; border-radius: 10px; margin-bottom: 20px;
    font-size: 1.4rem; font-weight: 700; color: #fff; letter-spacing: 0.5px;
}
.hdr-overview      { background: linear-gradient(90deg, #00695c, #0e0e1a); }
.hdr-quality       { background: linear-gradient(90deg, #b37a00, #0e0e1a); }
.hdr-distributions { background: linear-gradient(90deg, #4a3a9a, #0e0e1a); }
.hdr-correlations  { background: linear-gradient(90deg, #006064, #0e0e1a); }
.hdr-outliers      { background: linear-gradient(90deg, #8b1a1a, #0e0e1a); }
.hdr-insights      { background: linear-gradient(90deg, #4a148c, #0e0e1a); }
.hdr-export        { background: linear-gradient(90deg, #1a237e, #0e0e1a); }

.metric-card {
    background: linear-gradient(135deg, #1a1a2e, #252540);
    border-radius: 12px; padding: 18px; border: 1px solid #2a2a4a;
    text-align: center; margin-bottom: 10px;
}
.metric-value { font-size: 2.2rem; font-weight: 700; margin: 4px 0; }
.metric-label { font-size: 0.8rem; color: #aaa; text-transform: uppercase; letter-spacing: 1px; }
.teal   { color: #00d4aa; }
.purple { color: #7c6bf2; }
.amber  { color: #ffc300; }
.coral  { color: #ff6b6b; }

.ai-card {
    background: #1a1a2e; border-left: 4px solid #7c6bf2;
    border-radius: 8px; padding: 16px; margin-top: 12px;
    color: #e0e0ff; font-size: 0.95rem; line-height: 1.6;
}
.ai-card .ai-label { font-size: 0.75rem; color: #7c6bf2; font-weight: 600;
                     text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }

.finding-card { background:#1a1a2e; border-left:4px solid #00d4aa;
                border-radius:8px; padding:12px 16px; margin-bottom:8px; color:#e0e0ff; }
.anomaly-card { background:#1a1a2e; border-left:4px solid #ff6b6b;
                border-radius:8px; padding:12px 16px; margin-bottom:8px; color:#e0e0ff; }
.rec-card     { background:#1a1a2e; border-left:4px solid #7c6bf2;
                border-radius:8px; padding:12px 16px; margin-bottom:8px; color:#e0e0ff; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("profile", None), ("df", None), ("metas", None),
    ("narratives", {}), ("exec_summary", None),
    ("active_section", "Overview"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

try:
    _store = ChromaStore()
except Exception as _chroma_err:
    _store = None
    st.warning(f"ChromaDB unavailable: {_chroma_err}. Past reports panel disabled.")

DATA_DIR = Path(__file__).parent / "data"
DEMO_DATASETS = {
    "Retail Sales":    DATA_DIR / "retail_sales.csv",
    "IT Service Desk": DATA_DIR / "it_service_desk.csv",
}
SECTIONS = ["Overview", "Data Quality", "Distributions",
            "Correlations", "Outliers & Anomalies", "AI Insights", "Export"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 EDA Report Generator")
    st.caption("AI Friday Season 2 — PS11")
    st.divider()

    model_key = st.selectbox("Model", MODEL_OPTIONS, index=0)
    deployment = get_model(model_key)

    st.markdown("### Dataset")
    source = st.radio("Source", ["Use demo dataset", "Upload file"],
                      label_visibility="collapsed")

    df_raw = None
    dataset_name = ""
    file_size_mb = 0.0

    if source == "Use demo dataset":
        chosen = st.selectbox("Demo dataset", list(DEMO_DATASETS.keys()))
        dataset_name = chosen
        _trigger = st.button("Generate Report", type="primary", use_container_width=True)
        if _trigger:
            df_raw = pd.read_csv(DEMO_DATASETS[chosen])
            file_size_mb = DEMO_DATASETS[chosen].stat().st_size / 1_048_576
    else:
        uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"])
        _trigger = False
        if uploaded:
            dataset_name = uploaded.name.rsplit(".", 1)[0]
            raw_bytes = uploaded.read()
            file_size_mb = len(raw_bytes) / 1_048_576
            if uploaded.name.endswith(".xlsx"):
                df_raw = pd.read_excel(io.BytesIO(raw_bytes))
            else:
                df_raw = pd.read_csv(io.BytesIO(raw_bytes))
            _trigger = st.button("Generate Report", type="primary", use_container_width=True)

    # ── Pipeline trigger ──────────────────────────────────────────────────────
    if df_raw is not None and _trigger:
        with st.spinner("Running analysis pipeline…"):
            guard = validate_dataframe(df_raw, file_size_mb=file_size_mb)
            if not guard.ok:
                for e in guard.errors:
                    st.error(e)
            else:
                for w in guard.warnings:
                    st.warning(w)
                df = guard.df
                metas = infer_columns(df)
                df = impute_nulls(df.copy(), metas)
                df = parse_datetimes(df, metas)
                profile = build_profile(df, metas, dataset_name=dataset_name)
                st.session_state["df"]       = df
                st.session_state["metas"]    = metas
                st.session_state["profile"]  = profile
                st.session_state["narratives"] = {}
                st.session_state["exec_summary"] = None
                st.session_state["active_section"] = "Overview"
                st.rerun()

    # ── Navigation ────────────────────────────────────────────────────────────
    if st.session_state["profile"] is not None:
        st.divider()
        st.markdown("### Navigation")
        section_icons = {
            "Overview": "🏠", "Data Quality": "🔍", "Distributions": "📈",
            "Correlations": "🔗", "Outliers & Anomalies": "⚠️",
            "AI Insights": "✨", "Export": "📥",
        }
        for sec in SECTIONS:
            label = f"{section_icons[sec]} {sec}"
            active = st.session_state["active_section"] == sec
            if st.button(label, key=f"nav_{sec}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state["active_section"] = sec
                st.rerun()

# ── Helper: AI narrative card ─────────────────────────────────────────────────
def _ai_card(text: str) -> None:
    st.markdown(
        f'<div class="ai-card"><div class="ai-label">✨ AI Analysis</div>{text}</div>',
        unsafe_allow_html=True,
    )

def _get_narrative(section: str) -> str:
    if section not in st.session_state["narratives"]:
        client = get_llm_client()
        narrative = get_section_narrative(
            client, deployment, st.session_state["profile"], section)
        st.session_state["narratives"][section] = narrative
    return st.session_state["narratives"][section]

def _metric_card(value: str, label: str, color_class: str) -> str:
    return (f'<div class="metric-card">'
            f'<div class="metric-value {color_class}">{value}</div>'
            f'<div class="metric-label">{label}</div></div>')

# ── Main content area ─────────────────────────────────────────────────────────
profile = st.session_state["profile"]
df      = st.session_state["df"]

if profile is None:
    st.markdown("## 📊 EDA Report Generator")
    st.markdown("### Auto-generate comprehensive EDA reports with AI-powered insights")
    col1, col2, col3 = st.columns(3)
    col1.markdown(_metric_card("📊", "Charts & Stats", "teal"), unsafe_allow_html=True)
    col2.markdown(_metric_card("✨", "AI Narratives", "purple"), unsafe_allow_html=True)
    col3.markdown(_metric_card("📥", "Export Ready", "amber"), unsafe_allow_html=True)
    st.info("Select a dataset and click **Generate Report** in the sidebar to begin.")
    st.stop()

section = st.session_state["active_section"]
numeric_cols = [c.meta.name for c in profile.columns if c.meta.dtype == "numeric"]
cat_cols     = [c.meta.name for c in profile.columns if c.meta.dtype == "categorical"]
dt_cols      = [c.meta.name for c in profile.columns if c.meta.is_datetime]

# ── OVERVIEW ──────────────────────────────────────────────────────────────────
if section == "Overview":
    st.markdown('<div class="section-header hdr-overview">🏠 Overview</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_metric_card(f"{profile.row_count:,}", "Total Rows", "teal"), unsafe_allow_html=True)
    c2.markdown(_metric_card(str(profile.col_count), "Columns", "purple"), unsafe_allow_html=True)
    c3.markdown(_metric_card(f"{profile.duplicate_row_count:,}", "Duplicates", "amber"), unsafe_allow_html=True)
    c4.markdown(_metric_card(f"{profile.memory_mb:.2f} MB", "Memory", "teal"), unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(charts.null_bar(profile), use_container_width=True)
    with col2:
        st.plotly_chart(charts.column_type_pie(profile), use_container_width=True)
    _ai_card(_get_narrative("Overview"))

# ── DATA QUALITY ──────────────────────────────────────────────────────────────
elif section == "Data Quality":
    st.markdown('<div class="section-header hdr-quality">🔍 Data Quality</div>',
                unsafe_allow_html=True)
    null_cols = [(c.meta.name, c.meta.null_pct) for c in profile.columns if c.meta.null_pct > 0]
    if null_cols:
        rows_data = [{"Column": n, "Null %": f"{p*100:.1f}%",
                 "Status": "⚠️ Warning" if p > 0.1 else "✅ Low"} for n, p in null_cols]
        st.dataframe(pd.DataFrame(rows_data), use_container_width=True, hide_index=True)
    else:
        st.success("No missing values detected.")
    st.markdown(f"**Duplicate rows:** `{profile.duplicate_row_count:,}`")
    pii_cols = [c.meta.name for c in profile.columns
                if any(p in c.meta.name.lower() for p in
                       ["email", "phone", "ssn", "dob", "address"])]
    if pii_cols:
        st.warning(f"Possible PII columns: {', '.join(pii_cols)}")
    _ai_card(_get_narrative("Data Quality"))

# ── DISTRIBUTIONS ─────────────────────────────────────────────────────────────
elif section == "Distributions":
    st.markdown('<div class="section-header hdr-distributions">📈 Distributions</div>',
                unsafe_allow_html=True)
    if numeric_cols:
        st.markdown("#### Numeric Distributions")
        for i in range(0, len(numeric_cols), 2):
            row_cols = st.columns(2)
            for j, col_name in enumerate(numeric_cols[i:i+2]):
                with row_cols[j]:
                    st.plotly_chart(charts.histogram(df, col_name), use_container_width=True)
    if cat_cols:
        st.markdown("#### Categorical Distributions")
        cat_profiles = [c for c in profile.columns if c.meta.dtype == "categorical"]
        for i in range(0, len(cat_profiles), 2):
            row_cols = st.columns(2)
            for j, cp in enumerate(cat_profiles[i:i+2]):
                with row_cols[j]:
                    st.plotly_chart(charts.value_counts_bar(cp), use_container_width=True)
    _ai_card(_get_narrative("Distributions"))

# ── CORRELATIONS ──────────────────────────────────────────────────────────────
elif section == "Correlations":
    st.markdown('<div class="section-header hdr-correlations">🔗 Correlations</div>',
                unsafe_allow_html=True)
    if len(numeric_cols) >= 2:
        st.plotly_chart(charts.correlation_heatmap(df, numeric_cols), use_container_width=True)
        corr_matrix = df[numeric_cols].corr().abs()
        pairs = []
        for i in range(len(numeric_cols)):
            for j in range(i+1, len(numeric_cols)):
                pairs.append((corr_matrix.iloc[i, j], numeric_cols[i], numeric_cols[j]))
        pairs.sort(reverse=True)
        top_pairs = pairs[:4]
        if top_pairs:
            st.markdown("#### Top Correlated Pairs")
            for i in range(0, len(top_pairs), 2):
                row_cols = st.columns(2)
                for k, (_, cx, cy) in enumerate(top_pairs[i:i+2]):
                    with row_cols[k]:
                        st.plotly_chart(charts.scatter_pair(df, cx, cy), use_container_width=True)
    else:
        st.info("Need at least 2 numeric columns for correlation analysis.")
    _ai_card(_get_narrative("Correlations"))

# ── OUTLIERS ──────────────────────────────────────────────────────────────────
elif section == "Outliers & Anomalies":
    st.markdown('<div class="section-header hdr-outliers">⚠️ Outliers & Anomalies</div>',
                unsafe_allow_html=True)
    st.plotly_chart(charts.outlier_pct_bar(profile), use_container_width=True)
    if numeric_cols:
        st.markdown("#### Box Plots")
        for i in range(0, len(numeric_cols), 2):
            row_cols = st.columns(2)
            for j, col_name in enumerate(numeric_cols[i:i+2]):
                with row_cols[j]:
                    st.plotly_chart(charts.box_plot(df, col_name), use_container_width=True)
    if dt_cols and numeric_cols:
        st.markdown("#### Time Series")
        st.plotly_chart(
            charts.time_series_line(df, dt_cols[0], numeric_cols[0]),
            use_container_width=True)
    _ai_card(_get_narrative("Outliers & Anomalies"))

# ── AI INSIGHTS ───────────────────────────────────────────────────────────────
elif section == "AI Insights":
    st.markdown('<div class="section-header hdr-insights">✨ AI Insights</div>',
                unsafe_allow_html=True)
    if st.session_state["exec_summary"] is None:
        with st.spinner("Generating executive summary…"):
            client = get_llm_client()
            es = get_executive_summary(client, deployment, profile)
            st.session_state["exec_summary"] = es
            if _store is not None:
                try:
                    _store.store_report(
                        dataset_name=profile.dataset_name,
                        row_count=profile.row_count,
                        col_count=profile.col_count,
                        summary_json=es.model_dump_json(),
                    )
                except Exception:
                    pass  # ChromaDB failure should not crash the app

    es = st.session_state["exec_summary"]
    score = es.data_quality_score
    color = "teal" if score >= 80 else ("amber" if score >= 60 else "coral")
    st.markdown(_metric_card(f"{score:.0f}/100", "Data Quality Score", color),
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Key Findings")
        for f in es.key_findings:
            st.markdown(f'<div class="finding-card">• {f}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown("#### Anomalies Detected")
        for a in es.anomalies:
            st.markdown(f'<div class="anomaly-card">⚠️ {a}</div>', unsafe_allow_html=True)

    st.markdown("#### Recommendations")
    for r in es.recommendations:
        st.markdown(f'<div class="rec-card">→ {r}</div>', unsafe_allow_html=True)

    st.markdown("#### ML Readiness")
    st.markdown(
        f'<div class="ai-card"><div class="ai-label">🤖 Assessment</div>{es.ml_readiness}</div>',
        unsafe_allow_html=True)

    st.markdown("#### Similar Past Reports")
    query = f"{profile.dataset_name} {profile.row_count} rows {profile.col_count} columns"
    past = _store.search_similar(query, n=3) if _store is not None else []
    if past:
        for item in past:
            meta = item["meta"]
            with st.expander(
                    f"📄 {meta.get('dataset_name','Unknown')} — {meta.get('timestamp','')[:10]}"):
                try:
                    st.json(json.loads(item["summary"]))
                except Exception:
                    st.text(item["summary"])
    else:
        st.info("No past reports yet. Generate reports from multiple datasets to see similarities.")

# ── EXPORT ────────────────────────────────────────────────────────────────────
elif section == "Export":
    st.markdown('<div class="section-header hdr-export">📥 Export</div>',
                unsafe_allow_html=True)

    stat_rows = []
    for cp in profile.columns:
        row = {"column": cp.meta.name, "dtype": cp.meta.dtype,
               "null_pct": cp.meta.null_pct, "role": cp.meta.role}
        if cp.mean is not None:    row["mean"] = cp.mean
        if cp.median is not None:  row["median"] = cp.median
        if cp.std is not None:     row["std"] = cp.std
        if cp.min is not None:     row["min"] = cp.min
        if cp.max is not None:     row["max"] = cp.max
        if cp.unique_count is not None: row["unique_count"] = cp.unique_count
        if cp.outlier:             row["outlier_count"] = cp.outlier.count
        stat_rows.append(row)

    csv_df = pd.DataFrame(stat_rows)
    st.download_button(
        "⬇️ Download CSV Summary",
        data=csv_df.to_csv(index=False).encode(),
        file_name=f"{profile.dataset_name}_eda_summary.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.markdown("---")
    st.markdown("**HTML Report** — includes charts and AI findings in a self-contained file")
    if st.button("⬇️ Build & Download HTML Report", use_container_width=True):
        html_parts = [
            "<!DOCTYPE html><html><head><style>",
            "body{background:#0e0e1a;color:#e0e0ff;font-family:Inter,sans-serif;padding:24px}",
            "h1{color:#00d4aa}h2{color:#7c6bf2}p,li{color:#e0e0ff}",
            "</style></head><body>",
            f"<h1>EDA Report: {profile.dataset_name}</h1>",
            f"<p>Rows: {profile.row_count:,} | Columns: {profile.col_count} | Memory: {profile.memory_mb:.2f} MB | Duplicates: {profile.duplicate_row_count}</p>",
        ]
        for col_name in numeric_cols[:4]:
            html_parts.append(f"<h2>{col_name} Distribution</h2>")
            html_parts.append(
                charts.histogram(df, col_name).to_html(include_plotlyjs="cdn", full_html=False))
        if len(numeric_cols) >= 2:
            html_parts.append("<h2>Correlation Matrix</h2>")
            html_parts.append(
                charts.correlation_heatmap(df, numeric_cols).to_html(
                    include_plotlyjs=False, full_html=False))
        if st.session_state["exec_summary"]:
            es = st.session_state["exec_summary"]
            html_parts.append(f"<h2>Key Findings (Data Quality: {es.data_quality_score:.0f}/100)</h2><ul>")
            for f in es.key_findings:
                html_parts.append(f"<li>{f}</li>")
            html_parts.append("</ul>")
            if es.recommendations:
                html_parts.append("<h2>Recommendations</h2><ul>")
                for r in es.recommendations:
                    html_parts.append(f"<li>{r}</li>")
                html_parts.append("</ul>")
        html_parts.append("</body></html>")
        st.download_button(
            "Click to save HTML",
            data="\n".join(html_parts).encode(),
            file_name=f"{profile.dataset_name}_eda_report.html",
            mime="text/html",
        )
