from .config import get_llm_client, get_model
from .models import TravelItinerary
from .prompts import SYSTEM_PROMPT, build_user_message


def generate_itinerary(destination: str, duration_days: int, budget: str, interests: str, model_key: str = "gpt-4o", travel_month: str = "") -> TravelItinerary:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(destination, duration_days, budget, interests, travel_month)},
        ],
        response_format=TravelItinerary,
    )
    return response.choices[0].message.parsed
