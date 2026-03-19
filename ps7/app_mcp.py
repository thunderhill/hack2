"""Streamlit UI for Travel Itinerary Generator with MCP agent + ChromaDB history."""

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
from travel_itinerary.guardrails import run_input_guardrails, run_output_guardrails
from chroma_store import ChromaStore

store = ChromaStore("travel_itinerary")

st.set_page_config(page_title="Travel Itinerary Generator (MCP)", page_icon="✈️", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)
    st.divider()
    st.metric("Itineraries Stored", store.count())

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_generate, tab_history, tab_search = st.tabs(["Generate", "History", "Search"])

# ── Generate Tab ─────────────────────────────────────────────────────────────
with tab_generate:
    st.title("✈️ AI Travel Itinerary Generator")
    st.caption("Tell us your travel preferences and get a personalized day-by-day itinerary.")

    col1, col2 = st.columns(2)
    with col1:
        destination = st.text_input("Destination *", placeholder="e.g., Kyoto, Japan")
        budget = st.selectbox("Budget Level", ["budget", "mid-range", "luxury"])
        travel_month = st.text_input("Travel Month (optional)", placeholder="e.g., April")
    with col2:
        duration_days = st.number_input("Duration (days)", min_value=1, max_value=30, value=5)
        interests = st.text_input("Interests *", placeholder="e.g., temples, food, hiking, art museums")

    if st.button("Generate Itinerary", type="primary") and destination and interests:
        # ── Input Guardrails ─────────────────────────────────────────
        combined_input = f"Destination: {destination}, Interests: {interests}"
        guard = run_input_guardrails(combined_input)
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
          with st.spinner(f"Creating your {duration_days}-day {destination} itinerary..."):
            try:
                itinerary = generate_itinerary(destination, duration_days, budget, interests, model_key, travel_month)
                result_dict = itinerary.model_dump()

                # ── Output Guardrails ────────────────────────────────
                out_guard = run_output_guardrails(itinerary)
                if out_guard.warnings:
                    with st.expander("Output Guardrail Warnings"):
                        for w in out_guard.warnings:
                            st.warning(w)

                # Store in ChromaDB
                input_text = f"Destination: {destination}, Duration: {duration_days} days, Budget: {budget}, Interests: {interests}"
                store.add(input_text, result_dict, model_key)

                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Destination", itinerary.destination)
                col_b.metric("Duration", itinerary.trip_duration)
                col_c.metric("Style", itinerary.travel_style.capitalize())
                col_d.metric("Total Budget", itinerary.total_budget_estimate)

                st.info(f"**Best time to visit:** {itinerary.best_time_to_visit}")
                st.info(f"**Getting around:** {itinerary.getting_around}")

                st.subheader("Day-by-Day Itinerary")
                for day in itinerary.days:
                    with st.expander(f"📅 {day.date_label} — {day.theme} | Budget: {day.daily_budget_estimate}"):
                        for activity in day.activities:
                            st.markdown(f"**{activity.time} — {activity.name}** ({activity.duration}) | {activity.estimated_cost}")
                            st.write(activity.description)
                            if activity.tips:
                                st.caption(f"💡 {activity.tips}")
                            st.divider()
                        col_l, col_d2 = st.columns(2)
                        col_l.write(f"🍽️ **Lunch:** {day.lunch_recommendation}")
                        col_d2.write(f"🌙 **Dinner:** {day.dinner_recommendation}")
                        st.write(f"🏨 **Stay:** {day.accommodation}")

                col_e, col_f = st.columns(2)
                with col_e:
                    st.subheader("Packing Essentials")
                    for item in itinerary.packing_essentials:
                        st.write(f"• {item}")
                with col_f:
                    st.subheader("Cultural Tips")
                    for tip in itinerary.cultural_tips:
                        st.write(f"• {tip}")

                st.info(f"**Emergency Contacts:** {itinerary.emergency_contacts}")
            except Exception as e:
                st.error(f"Itinerary generation failed: {e}")

# ── History Tab ──────────────────────────────────────────────────────────────
with tab_history:
    st.title("📋 Itinerary History")
    st.caption("Browse past travel itineraries stored in ChromaDB.")

    recent = store.get_recent(20)
    if not recent:
        st.info("No itineraries yet. Generate one from the Generate tab to get started.")
    for item in recent:
        r = item["result"]
        with st.expander(
            f"**{r.get('destination', 'N/A')}** — {r.get('trip_duration', 'N/A')} | {item['timestamp'][:19]}"
        ):
            st.text_area("Input", item["input"], height=80, disabled=True, key=f"hist_{item['id']}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Destination", r.get("destination", "N/A"))
            col2.metric("Duration", r.get("trip_duration", "N/A"))
            col3.metric("Style", r.get("travel_style", "N/A").capitalize())
            col4.metric("Total Budget", r.get("total_budget_estimate", "N/A"))
            st.info(f"**Best time to visit:** {r.get('best_time_to_visit', 'N/A')}")
            st.info(f"**Getting around:** {r.get('getting_around', 'N/A')}")
            if r.get("days"):
                st.subheader("Days")
                for day in r["days"]:
                    st.write(f"📅 **{day.get('date_label', '')}** — {day.get('theme', '')}")
            col_e, col_f = st.columns(2)
            with col_e:
                if r.get("packing_essentials"):
                    st.subheader("Packing Essentials")
                    for pk in r["packing_essentials"]:
                        st.write(f"• {pk}")
            with col_f:
                if r.get("cultural_tips"):
                    st.subheader("Cultural Tips")
                    for tip in r["cultural_tips"]:
                        st.write(f"• {tip}")
            st.caption(f"Model: {item.get('model_key', 'N/A')}")

# ── Search Tab ───────────────────────────────────────────────────────────────
with tab_search:
    st.title("🔎 Search Past Itineraries")
    st.caption("Semantic search across all stored itineraries using ChromaDB.")

    query = st.text_input("Search query", placeholder="e.g. beach vacation budget friendly")
    n_results = st.slider("Max results", 1, 20, 5)

    if st.button("Search", type="primary") and query.strip():
        results = store.search(query, n_results)
        if not results:
            st.warning("No matching itineraries found.")
        for item in results:
            r = item["result"]
            similarity = f"{(1 - item.get('distance', 0)) * 100:.0f}%" if item.get("distance") is not None else "N/A"
            with st.expander(
                f"**{r.get('destination', 'N/A')}** — Similarity: {similarity} | {item['timestamp'][:19]}"
            ):
                st.text_area("Input", item["input"], height=80, disabled=True, key=f"search_{item['id']}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Destination", r.get("destination", "N/A"))
                col2.metric("Duration", r.get("trip_duration", "N/A"))
                col3.metric("Style", r.get("travel_style", "N/A").capitalize())
                col4.metric("Total Budget", r.get("total_budget_estimate", "N/A"))
                st.info(f"**Best time to visit:** {r.get('best_time_to_visit', 'N/A')}")
                st.info(f"**Getting around:** {r.get('getting_around', 'N/A')}")
