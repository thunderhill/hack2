# PS7 — AI Travel Itinerary Generator: Developer Guide

## Architecture Overview

```
User (Browser)
     │
     ▼
┌──────────────────────────────────────────────┐
│  app/main.py  (Streamlit UI)                 │
│  - Destination, duration, budget, interests  │
│  - Optional travel month                     │
│  - Calls generate_itinerary()                │
│  - Renders expandable day cards              │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  src/travel_itinerary/agent.py               │
│  generate_itinerary(dest, days, budget, ...) │
│  - Builds structured prompt                  │
│  - Calls Azure OpenAI with parse()           │
│  - Returns TravelItinerary                   │
└──────┬───────────────────┬────────────────────┘
       │                   │
       ▼                   ▼
┌────────────┐    ┌──────────────────────────────┐
│ config.py  │    │ prompts.py                   │
│ AzureOpenAI│    │ SYSTEM_PROMPT                │
│ client     │    │ build_user_message()         │
└────────────┘    └──────────────────────────────┘
       │
       ▼
Azure OpenAI API (expert travel planner persona)
(structured output → TravelItinerary)
       │
       ▼
┌─────────────────────────────────────────────┐
│  src/travel_itinerary/models.py             │
│  TravelItinerary + DayPlan + Activity       │
└─────────────────────────────────────────────┘
```

---

## Project Structure

```
ps7/
├── app/
│   └── main.py                       # Streamlit app — rendering only
├── src/
│   └── travel_itinerary/
│       ├── __init__.py
│       ├── agent.py                  # Single function: generate_itinerary()
│       ├── config.py                 # Azure OpenAI client factory + model map
│       ├── models.py                 # TravelItinerary + DayPlan + Activity
│       └── prompts.py                # System prompt + message builder
└── pyproject.toml                    # Package: travel-itinerary, Python 3.11+
```

---

## Core Components

### `agent.py`

```python
def generate_itinerary(
    destination: str,
    duration_days: int,
    budget: str,
    interests: str,
    model_key: str = "gpt-4o",
    travel_month: str = ""
) -> TravelItinerary:
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
```

Unlike other PS projects, `generate_itinerary()` takes structured parameters (not a blob of text), which the message builder formats into a structured prompt. This produces more predictable and specific itineraries than free-form input.

### `models.py`

Three nested Pydantic models forming a hierarchy:

```python
class Activity(BaseModel):
    time: str             # e.g., "9:00 AM"
    name: str             # Activity or place name
    description: str      # Brief description
    duration: str         # e.g., "2 hours"
    estimated_cost: str   # e.g., "$20" or "Free"
    tips: str             # Practical tips

class DayPlan(BaseModel):
    day_number: int                  # 1, 2, 3, ...
    date_label: str                  # e.g., "Day 1 - Arrival"
    theme: str                       # e.g., "Old City Exploration"
    activities: list[Activity]       # Activities for the day
    lunch_recommendation: str        # Lunch suggestion
    dinner_recommendation: str       # Dinner suggestion
    accommodation: str               # Where to stay
    daily_budget_estimate: str       # Estimated daily spend

class TravelItinerary(BaseModel):
    destination: str
    trip_duration: str               # e.g., "5 days"
    travel_style: str                # budget | mid-range | luxury
    best_time_to_visit: str          # Recommended season
    days: list[DayPlan]              # Day-by-day plans
    total_budget_estimate: str       # Total trip budget
    packing_essentials: list[str]    # Items to pack
    cultural_tips: list[str]         # Cultural etiquette
    emergency_contacts: str          # Emergency info
    getting_around: str              # Transportation tips
```

The three-level nesting (`TravelItinerary → DayPlan → Activity`) is the deepest model hierarchy in the PS projects. The OpenAI structured output API handles this correctly with Pydantic's JSON schema generation.

### `prompts.py`

```python
def build_user_message(destination, duration_days, budget, interests, travel_month=""):
    month_context = f"\nTravel month: {travel_month}" if travel_month else ""
    return f"""Create a detailed travel itinerary with these preferences:

Destination: {destination}
Duration: {duration_days} days
Budget level: {budget}
Interests: {interests}{month_context}

Create a complete day-by-day itinerary with specific activities, dining recommendations, and practical tips."""
```

The structured key-value format of the user message (rather than free-form prose) is intentional — it maps cleanly to the model's parameters and results in more consistent LLM output.

---

## Environment Setup

```bash
cd /path/to/hack2/ps7
python -m venv .venv
source .venv/bin/activate
pip install -e .

cat > .env << 'EOF'
AZURE_GENAI_API_KEY=your_key_here
AZURE_GENAI_ENDPOINT=https://genailab-maas.services.ai.azure.com
AZURE_GENAI_API_VERSION=2024-08-01-preview
EOF

streamlit run app/main.py
```

---

## Extending the App

### Add a new travel style

```python
class TravelItinerary(BaseModel):
    travel_style: str = Field(
        description="Travel style: budget | mid-range | luxury | backpacker | business | family"
    )
```

Update `SYSTEM_PROMPT` to define what each style means in terms of accommodation and activity selection.

### Add a transportation plan per day

```python
class DayPlan(BaseModel):
    ...
    transportation: list[str] = Field(
        description="Transportation options for the day, e.g., ['Take metro Line 1 to Shinjuku', 'Walk 10 minutes to temple']"
    )
```

Render it in `app/main.py` within the day expander card.

### Add hotel booking links

After the itinerary is generated, add a post-processing step that generates search links:

```python
def add_booking_links(itinerary: TravelItinerary) -> dict[str, str]:
    links = {}
    for day in itinerary.days:
        hotel = day.accommodation
        search_url = f"https://www.booking.com/search.html?ss={hotel.replace(' ', '+')}"
        links[f"Day {day.day_number}"] = search_url
    return links
```

### Add a map visualization

Use `streamlit-folium` to render activity locations on a map:

```bash
pip install streamlit-folium folium
```

```python
import folium
from streamlit_folium import st_folium

def render_day_map(day: DayPlan, geocoded_activities: list[tuple[float, float]]):
    m = folium.Map(location=geocoded_activities[0], zoom_start=14)
    for coords, activity in zip(geocoded_activities, day.activities):
        folium.Marker(coords, popup=activity.name).add_to(m)
    st_folium(m, width=700)
```

---

## Testing

### Test the agent in isolation

```python
import os
os.environ["AZURE_GENAI_API_KEY"] = "your_key"

from travel_itinerary.agent import generate_itinerary

itinerary = generate_itinerary(
    destination="Kyoto, Japan",
    duration_days=3,
    budget="mid-range",
    interests="temples, food, traditional arts",
    model_key="gpt-4o-mini",
    travel_month="April",
)
print(itinerary.total_budget_estimate)
print(f"Days planned: {len(itinerary.days)}")
for day in itinerary.days:
    print(f"{day.date_label}: {day.theme} ({len(day.activities)} activities)")
```

### Unit test with mocks

```python
from unittest.mock import MagicMock, patch
from travel_itinerary.models import TravelItinerary, DayPlan, Activity

mock_itinerary = TravelItinerary(
    destination="Kyoto, Japan",
    trip_duration="3 days",
    travel_style="mid-range",
    best_time_to_visit="March-May (cherry blossoms) or October-November (autumn leaves)",
    days=[
        DayPlan(
            day_number=1,
            date_label="Day 1 - Arrival & Gion",
            theme="Historic Gion District",
            activities=[
                Activity(time="2:00 PM", name="Fushimi Inari Shrine",
                         description="Famous for thousands of torii gates",
                         duration="2 hours", estimated_cost="Free", tips="Go early to avoid crowds"),
            ],
            lunch_recommendation="Nishiki Market food stalls",
            dinner_recommendation="Gion Kappa restaurant",
            accommodation="Kyoto Station area hotel",
            daily_budget_estimate="$120",
        )
    ],
    total_budget_estimate="$450-550",
    packing_essentials=["Comfortable walking shoes", "IC card for transit"],
    cultural_tips=["Remove shoes before entering temples", "Bow when greeting"],
    emergency_contacts="Police: 110, Ambulance: 119",
    getting_around="IC card (Suica/ICOCA) for buses and subway",
)

with patch("travel_itinerary.agent.get_llm_client") as mock_client:
    mock_response = MagicMock()
    mock_response.choices[0].message.parsed = mock_itinerary
    mock_client.return_value.beta.chat.completions.parse.return_value = mock_response

    from travel_itinerary.agent import generate_itinerary
    result = generate_itinerary("Kyoto, Japan", 3, "mid-range", "temples")
    assert result.destination == "Kyoto, Japan"
    assert len(result.days) == 1
```

---

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8501
CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0"]
```

```bash
docker build -t ps7-travel-itinerary .
docker run -p 8501:8501 \
  -e AZURE_GENAI_API_KEY=your_key \
  -e AZURE_GENAI_ENDPOINT=https://genailab-maas.services.ai.azure.com \
  ps7-travel-itinerary
```

### Production environment variables

| Variable | Description |
|---|---|
| `AZURE_GENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_GENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_GENAI_API_VERSION` | API version (default: `2024-08-01-preview`) |
