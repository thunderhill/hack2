import os, ssl, warnings

# ── SSL bypass — MUST be before any other import ─────────────────────────────
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ── Path setup ────────────────────────────────────────────────────────────────
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

st.set_page_config(page_title="Travel Itinerary Generator", page_icon="✈️", layout="wide")
st.title("✈️ AI Travel Itinerary Generator")
st.caption("Tell us your travel preferences and get a personalized day-by-day itinerary.")

from travel_itinerary.config import MODEL_OPTIONS

with st.sidebar:
    st.header("Settings")
    model_key = st.selectbox("LLM Model", MODEL_OPTIONS)

col1, col2 = st.columns(2)
with col1:
    destination = st.text_input("Destination *", placeholder="e.g., Kyoto, Japan")
    budget = st.selectbox("Budget Level", ["budget", "mid-range", "luxury"])
    travel_month = st.text_input("Travel Month (optional)", placeholder="e.g., April")
with col2:
    duration_days = st.number_input("Duration (days)", min_value=1, max_value=30, value=5)
    interests = st.text_input("Interests *", placeholder="e.g., temples, food, hiking, art museums")

if st.button("Generate Itinerary", type="primary") and destination and interests:
    from travel_itinerary.agent import generate_itinerary
    with st.spinner(f"Creating your {duration_days}-day {destination} itinerary..."):
        try:
            itinerary = generate_itinerary(destination, duration_days, budget, interests, model_key, travel_month)

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
