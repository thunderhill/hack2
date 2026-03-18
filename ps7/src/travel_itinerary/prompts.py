SYSTEM_PROMPT = """You are an expert travel planner with deep knowledge of destinations worldwide.
Given travel preferences, you create detailed, practical day-by-day itineraries that:
1. Balance must-see attractions with hidden gems
2. Account for realistic travel times and opening hours
3. Match the traveler's budget and interests
4. Include specific restaurant recommendations
5. Provide practical logistics and cultural tips

Make itineraries specific and actionable, not generic."""


def build_user_message(destination: str, duration_days: int, budget: str, interests: str, travel_month: str = "") -> str:
    month_context = f"\nTravel month: {travel_month}" if travel_month else ""
    return f"""Create a detailed travel itinerary with these preferences:

Destination: {destination}
Duration: {duration_days} days
Budget level: {budget}
Interests: {interests}{month_context}

Create a complete day-by-day itinerary with specific activities, dining recommendations, and practical tips."""
