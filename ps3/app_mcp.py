"""Streamlit UI for Build Failure Diagnosis with MCP agent + ChromaDB history."""

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

from build_failure.agent import diagnose_build
from build_failure.config import MODEL_OPTIONS
from build_failure.guardrails import run_input_guardrails, run_output_guardrails
from chroma_store import ChromaStore

store = ChromaStore("build_failure")

st.set_page_config(page_title="Build Failure Diagnosis (MCP)", page_icon="🔨", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    language_hint = st.text_input("Language/Framework (optional)", placeholder="e.g., Java Spring Boot")
    st.divider()
    st.metric("Analyses Stored", store.count())

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_analyze, tab_history, tab_search = st.tabs(["Analyze", "History", "Search"])

# ── Analyze Tab ──────────────────────────────────────────────────────────────
with tab_analyze:
    st.title("🔨 Software Build Failure Diagnosis")
    st.caption("Paste your build output to get an AI-powered diagnosis and fix.")

    SAMPLE_BUILD_OUTPUT = """[INFO] Scanning for projects...
[INFO] Building my-spring-app 1.0.0
[INFO] --- maven-compiler-plugin:3.11.0:compile ---
[ERROR] COMPILATION ERROR :
[ERROR] /src/main/java/com/example/UserService.java:[45,32] error: cannot find symbol
[ERROR]   symbol:   method getUserById(long)
[ERROR]   location: class com.example.repository.UserRepository
[ERROR] /src/main/java/com/example/UserService.java:[67,18] error: incompatible types
[ERROR]   required: java.lang.String
[ERROR]   found:    java.util.Optional<java.lang.String>
[ERROR] 2 errors
[INFO] BUILD FAILURE
[INFO] Total time: 3.421 s
[ERROR] Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin:3.11.0:compile"""

    build_output = st.text_area(
        "Build Output",
        value=SAMPLE_BUILD_OUTPUT,
        height=250,
        placeholder="Paste your build/compiler output here...",
    )

    if st.button("Diagnose Build Failure", type="primary") and build_output.strip():
        # ── Input Guardrails ─────────────────────────────────────────
        guard = run_input_guardrails(build_output)
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
          with st.spinner("Diagnosing build failure..."):
            try:
                result = diagnose_build(build_output, model_key, language_hint)
                result_dict = result.model_dump()

                # ── Output Guardrails ────────────────────────────────
                out_guard = run_output_guardrails(result)
                if out_guard.warnings:
                    with st.expander("Output Guardrail Warnings"):
                        for w in out_guard.warnings:
                            st.warning(w)

                # Store in ChromaDB
                store.add(build_output, result_dict, model_key)

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Build Tool", result.build_tool.upper())
                col2.metric("Language", result.language.capitalize())
                col3.metric("Error Type", result.error_type)
                col4.metric("Est. Fix Time", result.estimated_fix_time)

                st.subheader("Error Location")
                loc = result.error_location
                st.code(f"File: {loc.file_path}  |  Line: {loc.line_number}  |  Column: {loc.column}")

                st.subheader("Core Error")
                st.error(result.error_message)

                st.subheader("Diagnosis")
                st.warning(result.diagnosis)

                st.subheader("How to Fix")
                st.info(result.fix_explanation)

                if result.code_fix and result.code_fix != "N/A":
                    st.subheader("Code Fix")
                    st.code(result.code_fix)
            except Exception as e:
                st.error(f"Diagnosis failed: {e}")

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.title("📋 Analysis History")
    st.caption("Browse past build failure analyses stored in ChromaDB.")

    recent = store.get_recent(20)
    if not recent:
        st.info("No analyses yet. Run an analysis from the Analyze tab to get started.")
    for item in recent:
        r = item["result"]
        error_loc = r.get("error_location", {})
        with st.expander(
            f"**{r.get('error_type', 'N/A')}** — {r.get('build_tool', 'N/A').upper()} / {r.get('language', 'N/A')} | {item['timestamp'][:19]}"
        ):
            st.text_area("Build Output", item["input"], height=120, disabled=True, key=f"hist_{item['id']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Build Tool", r.get("build_tool", "N/A").upper())
            col2.metric("Language", r.get("language", "N/A").capitalize())
            col3.metric("Error Type", r.get("error_type", "N/A"))
            col4.metric("Est. Fix Time", r.get("estimated_fix_time", "N/A"))

            st.subheader("Error Location")
            st.code(
                f"File: {error_loc.get('file_path', 'N/A')}  |  "
                f"Line: {error_loc.get('line_number', 'N/A')}  |  "
                f"Column: {error_loc.get('column', 'N/A')}"
            )

            st.error(r.get("error_message", ""))
            st.warning(r.get("diagnosis", ""))
            st.info(r.get("fix_explanation", ""))

            code_fix = r.get("code_fix", "")
            if code_fix and code_fix != "N/A":
                st.subheader("Code Fix")
                st.code(code_fix)

            st.caption(f"Model: {item.get('model_key', 'N/A')}")

# ── Search Tab ───────────────────────────────────────────────────────────────
with tab_search:
    st.title("🔎 Search Past Analyses")
    st.caption("Semantic search across all stored build failure analyses using ChromaDB.")

    query = st.text_input("Search query", placeholder="e.g. maven compilation error")
    n_results = st.slider("Max results", 1, 20, 5)

    if st.button("Search", type="primary") and query.strip():
        results = store.search(query, n_results)
        if not results:
            st.warning("No matching analyses found.")
        for item in results:
            r = item["result"]
            error_loc = r.get("error_location", {})
            similarity = f"{(1 - item.get('distance', 0)) * 100:.0f}%" if item.get("distance") is not None else "N/A"
            with st.expander(
                f"**{r.get('error_type', 'N/A')}** — Similarity: {similarity} | {item['timestamp'][:19]}"
            ):
                st.text_area("Build Output", item["input"], height=120, disabled=True, key=f"search_{item['id']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Build Tool", r.get("build_tool", "N/A").upper())
                col2.metric("Language", r.get("language", "N/A").capitalize())
                col3.metric("Error Type", r.get("error_type", "N/A"))
                col4.metric("Est. Fix Time", r.get("estimated_fix_time", "N/A"))

                st.subheader("Error Location")
                st.code(
                    f"File: {error_loc.get('file_path', 'N/A')}  |  "
                    f"Line: {error_loc.get('line_number', 'N/A')}  |  "
                    f"Column: {error_loc.get('column', 'N/A')}"
                )

                st.error(r.get("error_message", ""))
                st.warning(r.get("diagnosis", ""))
                st.info(r.get("fix_explanation", ""))

                code_fix = r.get("code_fix", "")
                if code_fix and code_fix != "N/A":
                    st.subheader("Code Fix")
                    st.code(code_fix)
