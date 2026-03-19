"""Audio-interactive Travel Itinerary Generator — speak your travel request, get a full itinerary."""

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

from travel_itinerary.agent import generate_itinerary
from travel_itinerary.config import MODEL_OPTIONS
from travel_itinerary.audio_processor import transcribe_audio, extract_travel_intent
from travel_itinerary.guardrails import run_input_guardrails
from chroma_store import ChromaStore

store = ChromaStore("travel_itinerary_audio")

st.set_page_config(
    page_title="Travel Itinerary — Audio Input",
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
    st.markdown("2. Review transcription")
    st.markdown("3. Adjust extracted details")
    st.markdown("4. Generate itinerary")
    st.divider()
    st.metric("Itineraries Stored", store.count())

# ── Header ───────────────────────────────────────────────────────────────────
st.title("🎙️ Travel Itinerary — Audio Interactive")
st.caption("Speak your travel request and get a personalized itinerary powered by Whisper + GPT.")

st.info(
    "**Example:** *"I want to visit Kyoto, Japan for 7 days in April. "
    "I'm on a mid-range budget and love temples, traditional food, and tea ceremonies."*",
    icon="💡",
)

st.divider()

# ── Step 1: Audio Input ───────────────────────────────────────────────────────
st.subheader("Step 1 — Provide Audio")

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

else:  # Record in browser
    try:
        # st.audio_input available in Streamlit >= 1.38
        recorded = st.audio_input("Click to record your travel request")
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
            except Exception as e:
                st.error(f"Transcription failed: {e}")

    if "transcript" in st.session_state:
        transcript = st.session_state["transcript"]
        edited_transcript = st.text_area(
            "Transcript (edit if needed)",
            value=transcript,
            height=100,
            key="edited_transcript",
        )
        st.session_state["transcript"] = edited_transcript

        # ── Step 3: Intent Extraction ─────────────────────────────────────────
        st.divider()
        st.subheader("Step 3 — Extracted Travel Details")

        if st.button("Extract Travel Details", type="secondary") or "intent" not in st.session_state:
            with st.spinner("Extracting travel intent..."):
                try:
                    intent = extract_travel_intent(st.session_state["transcript"], model_key)
                    st.session_state["intent"] = intent
                except Exception as e:
                    st.error(f"Intent extraction failed: {e}")

        if "intent" in st.session_state:
            intent = st.session_state["intent"]

            # Show confidence
            conf_color = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(intent["confidence"], "⚪")
            st.caption(f"Extraction confidence: {conf_color} {intent['confidence'].upper()}")
            if intent.get("notes"):
                st.warning(f"Note: {intent['notes']}")

            # Editable fields
            col1, col2 = st.columns(2)
            with col1:
                destination = st.text_input("Destination", value=intent["destination"])
                budget = st.selectbox(
                    "Budget Level",
                    ["budget", "mid-range", "luxury"],
                    index=["budget", "mid-range", "luxury"].index(intent.get("budget", "mid-range")),
                )
                travel_month = st.text_input("Travel Month", value=intent.get("travel_month", ""))
            with col2:
                duration_days = st.number_input(
                    "Duration (days)", min_value=1, max_value=30,
                    value=max(1, min(30, intent.get("duration_days", 5))),
                )
                interests = st.text_input("Interests", value=intent.get("interests", ""))

            # ── Step 4: Generate ─────────────────────────────────────────────
            st.divider()
            st.subheader("Step 4 — Generate Itinerary")

            if st.button("Generate Itinerary", type="primary") and destination and interests:
                # Guardrails
                combined = f"Destination: {destination}, Interests: {interests}"
                guard = run_input_guardrails(combined)

                with st.expander("Guardrail Checks", expanded=not guard.passed):
                    for check in guard.checks:
                        icon = "✅" if check.passed else "❌"
                        st.write(f"{icon} **{check.name}**: {check.message}")
                    if guard.pii_detected:
                        st.warning(f"PII masked: {', '.join(guard.pii_detected)}")
                    if guard.warnings:
                        for w in guard.warnings:
                            st.caption(f"⚠️ {w}")

                if guard.blocked:
                    st.error(f"Input blocked: {guard.block_reason}")
                else:
                    with st.spinner(f"Creating your {duration_days}-day {destination} itinerary..."):
                        try:
                            itinerary = generate_itinerary(
                                destination, duration_days, budget, interests,
                                model_key, travel_month,
                            )
                            result_dict = itinerary.model_dump()

                            # Store with audio transcript for richer search
                            input_text = (
                                f"[Audio] {st.session_state.get('transcript', '')}\n"
                                f"Destination: {destination}, Duration: {duration_days} days, "
                                f"Budget: {budget}, Interests: {interests}"
                            )
                            store.add(input_text, result_dict, model_key)

                            # ── Results ──────────────────────────────────────
                            st.success("Itinerary generated!")

                            col_a, col_b, col_c, col_d = st.columns(4)
                            col_a.metric("Destination", itinerary.destination)
                            col_b.metric("Duration", itinerary.trip_duration)
                            col_c.metric("Style", itinerary.travel_style.capitalize())
                            col_d.metric("Total Budget", itinerary.total_budget_estimate)

                            st.info(f"**Best time to visit:** {itinerary.best_time_to_visit}")
                            st.info(f"**Getting around:** {itinerary.getting_around}")

                            st.subheader("Day-by-Day Itinerary")
                            for day in itinerary.days:
                                with st.expander(
                                    f"📅 {day.date_label} — {day.theme} | Budget: {day.daily_budget_estimate}"
                                ):
                                    for activity in day.activities:
                                        st.markdown(
                                            f"**{activity.time} — {activity.name}** "
                                            f"({activity.duration}) | {activity.estimated_cost}"
                                        )
                                        st.write(activity.description)
                                        if activity.tips:
                                            st.caption(f"💡 {activity.tips}")
                                        st.divider()
                                    col_l, col_d_ = st.columns(2)
                                    col_l.markdown(f"🍜 **Lunch:** {day.lunch_recommendation}")
                                    col_d_.markdown(f"🍽️ **Dinner:** {day.dinner_recommendation}")
                                    st.caption(f"🏨 {day.accommodation}")

                            col_pack, col_tips = st.columns(2)
                            with col_pack:
                                st.subheader("🧳 Packing Essentials")
                                for item in itinerary.packing_essentials:
                                    st.write(f"• {item}")
                            with col_tips:
                                st.subheader("🌏 Cultural Tips")
                                for tip in itinerary.cultural_tips:
                                    st.write(f"• {tip}")

                            st.subheader("🆘 Emergency Contacts")
                            st.info(itinerary.emergency_contacts)

                        except Exception as e:
                            st.error(f"Generation failed: {e}")

# ── History Tab prompt ────────────────────────────────────────────────────────
st.divider()
with st.expander("📋 Recent Audio-Generated Itineraries"):
    recent = store.get_recent(10)
    if not recent:
        st.info("No itineraries yet.")
    for item in recent:
        r = item["result"]
        with st.container():
            st.markdown(
                f"**{r.get('destination', 'N/A')}** — {r.get('trip_duration', 'N/A')} | "
                f"{r.get('travel_style', 'N/A')} | {item['timestamp'][:19]}"
            )
            if item["input"].startswith("[Audio]"):
                transcript_line = item["input"].split("\n")[0].replace("[Audio] ", "")
                st.caption(f"🎙️ *\"{transcript_line[:120]}...\"*" if len(transcript_line) > 120 else f"🎙️ *\"{transcript_line}\"*")
            st.divider()
