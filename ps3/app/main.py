import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Build Failure Diagnosis", page_icon="🔨", layout="wide")
st.title("🔨 Software Build Failure Diagnosis")
st.caption("Paste your build output to get an AI-powered diagnosis and fix.")

from build_failure.config import MODEL_OPTIONS

with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    language_hint = st.text_input("Language/Framework (optional)", placeholder="e.g., Java Spring Boot")

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
    from build_failure.agent import diagnose_build
    with st.spinner("Diagnosing build failure..."):
        try:
            result = diagnose_build(build_output, model_key, language_hint)

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
