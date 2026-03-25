"""Audio-interactive Pipeline Anomaly Explainer — describe your error verbally, get a full analysis."""

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
from pipeline_anomaly.audio_processor import transcribe_audio, reconstruct_log_from_description
from pipeline_anomaly.guardrails import run_input_guardrails, run_output_guardrails
from chroma_store import ChromaStore

store = ChromaStore("pipeline_anomaly_audio")

st.set_page_config(
    page_title="Pipeline Anomaly — Audio Input",
    page_icon="🎙️",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    st.divider()
    st.markdown("**How to use:**")
    st.markdown("1. Record or upload audio")
    st.markdown("2. Transcribe with Whisper")
    st.markdown("3. Review reconstructed log")
    st.markdown("4. Analyze anomaly")
    st.divider()
    st.metric("Analyses Stored", store.count())

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🎙️ Pipeline Anomaly — Audio Interactive")
st.caption("Describe your CI/CD pipeline error verbally. Whisper transcribes it, GPT reconstructs the log, then analyzes the anomaly.")

st.info(
    "**Example:** *"My pipeline is failing during the install stage — "
    "npm can't resolve a peer dependency, react-router-dom needs React 17 but I have React 18."*",
    icon="💡",
)

st.divider()

# ── Step 1: Audio Input ───────────────────────────────────────────────────────
st.subheader("Step 1 — Describe Your Error")

input_mode = st.radio(
    "Input method",
    ["Upload audio file", "Record in browser"],
    horizontal=True,
)

audio_bytes = None
filename = "audio.wav"

if input_mode == "Upload audio file":
    uploaded = st.file_uploader(
        "Upload audio file (WAV, MP3, M4A, OGG, WebM)",
        type=["wav", "mp3", "m4a", "ogg", "webm", "flac"],
    )
    if uploaded:
        audio_bytes = uploaded.read()
        filename = uploaded.name
        st.audio(audio_bytes, format=f"audio/{filename.rsplit('.', 1)[-1]}")
        st.success(f"Audio loaded: {filename} ({len(audio_bytes):,} bytes)")
else:
    try:
        recorded = st.audio_input("Click to record your error description")
        if recorded:
            audio_bytes = recorded.read()
            filename = "recording.wav"
            st.success(f"Recorded {len(audio_bytes):,} bytes")
    except AttributeError:
        st.warning(
            "Browser recording requires Streamlit 1.38+. "
            "Please use the **Upload audio file** option instead."
        )

# ── Step 2: Transcription ────────────────────────────────────────────────────
if audio_bytes:
    st.divider()
    st.subheader("Step 2 — Transcription")

    if st.button("Transcribe Audio", type="primary"):
        with st.spinner("Transcribing with Whisper..."):
            try:
                transcript = transcribe_audio(audio_bytes, filename)
                st.session_state["transcript"] = transcript
                # Clear downstream state on new transcription
                st.session_state.pop("reconstruction", None)
            except Exception as e:
                st.error(f"Transcription failed: {e}")

    if "transcript" in st.session_state:
        edited = st.text_area(
            "Transcript (edit if needed)",
            value=st.session_state["transcript"],
            height=100,
            key="edited_transcript",
        )
        st.session_state["transcript"] = edited

        # ── Step 3: Log Reconstruction ────────────────────────────────────────
        st.divider()
        st.subheader("Step 3 — Log Reconstruction")
        st.caption("GPT converts your verbal description into a realistic pipeline log.")

        col_btn, col_skip = st.columns([1, 3])
        reconstruct = col_btn.button("Reconstruct Log", type="secondary")
        use_raw = col_skip.checkbox("Skip reconstruction — use transcript as-is")

        if use_raw:
            st.session_state["log_to_analyze"] = st.session_state["transcript"]
            st.info("Using raw transcript as log input.")
        elif reconstruct or "reconstruction" in st.session_state:
            if reconstruct:
                with st.spinner("Reconstructing log from description..."):
                    try:
                        recon = reconstruct_log_from_description(
                            st.session_state["transcript"], model_key
                        )
                        st.session_state["reconstruction"] = recon
                    except Exception as e:
                        st.error(f"Reconstruction failed: {e}")

            if "reconstruction" in st.session_state:
                recon = st.session_state["reconstruction"]

                conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(recon["confidence"], "⚪")
                col_a, col_b = st.columns(2)
                col_a.metric("Pipeline Stage", recon["pipeline_stage"])
                col_b.metric("Error Category", recon["error_category"])
                st.caption(f"Reconstruction confidence: {conf_icon} {recon['confidence'].upper()}")
                if recon.get("notes"):
                    st.caption(f"Assumptions: {recon['notes']}")

                edited_log = st.text_area(
                    "Reconstructed Log (edit if needed)",
                    value=recon["log_snippet"],
                    height=250,
                    key="edited_log",
                )
                st.session_state["log_to_analyze"] = edited_log

        # ── Step 4: Analysis ──────────────────────────────────────────────────
        if "log_to_analyze" in st.session_state:
            st.divider()
            st.subheader("Step 4 — Analyze Anomaly")

            if st.button("Analyze Anomaly", type="primary"):
                log_input = st.session_state["log_to_analyze"]

                # Guardrails
                guard = run_input_guardrails(log_input)
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
                    with st.spinner("Analyzing pipeline log..."):
                        try:
                            result = explain_anomaly(log_input, model_key)
                            result_dict = result.model_dump()

                            # Output guardrails
                            out_guard = run_output_guardrails(result)
                            if out_guard.warnings:
                                with st.expander("Output Guardrail Warnings"):
                                    for w in out_guard.warnings:
                                        st.warning(w)

                            # Store with transcript for richer search
                            input_doc = (
                                f"[Audio] {st.session_state.get('transcript', '')}\n"
                                f"{log_input}"
                            )
                            store.add(input_doc, result_dict, model_key)

                            # Results
                            st.success("Analysis complete!")
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

# ── Recent Analyses ───────────────────────────────────────────────────────────
st.divider()
with st.expander("📋 Recent Audio-Described Analyses"):
    recent = store.get_recent(10)
    if not recent:
        st.info("No analyses yet.")
    for item in recent:
        r = item["result"]
        transcript_line = ""
        if item["input"].startswith("[Audio]"):
            transcript_line = item["input"].split("\n")[0].replace("[Audio] ", "")
        st.markdown(
            f"**{r.get('anomaly_type', 'N/A')}** — {r.get('severity', 'N/A').upper()} | {item['timestamp'][:19]}"
        )
        if transcript_line:
            st.caption(f"🎙️ *\"{transcript_line[:120]}\"*")
        st.divider()
