# PS7 — AI Travel Itinerary Generator: User Guide

## Overview

The AI Travel Itinerary Generator creates personalized day-by-day travel itineraries with specific activities, dining recommendations, accommodation suggestions, and practical tips. Enter your destination, duration, budget, and interests to get a complete trip plan.

**When to use it:**
- Planning a personal or business trip and want a structured starting itinerary
- Exploring what a destination has to offer before committing to a trip
- Generating trip ideas for a specific budget level or interest set

---

## Prerequisites

- Python 3.11 or higher
- Access to an Azure OpenAI deployment with one of: `gpt-4o`, `gpt-4o-mini`, or `gpt-35-turbo`
- Azure GenAI API credentials (key + endpoint)

---

## Installation & Setup

**1. Install the package:**

```bash
cd ps7
pip install -e .
```

**2. Create a `.env` file in the `ps7/` directory:**

```env
AZURE_GENAI_API_KEY=your_api_key_here
AZURE_GENAI_ENDPOINT=https://genailab-maas.services.ai.azure.com
AZURE_GENAI_API_VERSION=2024-08-01-preview
```

| Variable | Required | Default |
|---|---|---|
| `AZURE_GENAI_API_KEY` | Yes | — |
| `AZURE_GENAI_ENDPOINT` | No | `https://genailab-maas.services.ai.azure.com` |
| `AZURE_GENAI_API_VERSION` | No | `2024-08-01-preview` |

---

## Running the App

```bash
cd ps7
streamlit run app/main.py
```

The app opens at `http://localhost:8501`.

---

## Using the Interface

**Sidebar — Settings:**
- **LLM Model** — Select the model. `gpt-4o` generates the most detailed and accurate itineraries.

**Main Panel — Inputs (two columns):**

| Field | Required | Description |
|---|---|---|
| **Destination** | Yes | City and country (e.g., `Kyoto, Japan`) |
| **Duration (days)** | Yes | Number of days, 1–30 |
| **Budget Level** | Yes | `budget` / `mid-range` / `luxury` |
| **Interests** | Yes | Comma-separated interests (e.g., `temples, food, hiking, art museums`) |
| **Travel Month** | No | Month of travel (e.g., `April`) — affects seasonal recommendations |

**Generate Itinerary** — Click after filling in the required fields.

**Results:**

- Four metrics: Destination, Duration, Style, Total Budget
- **Best time to visit** and **Getting around** tips
- **Day-by-Day Itinerary** — Expandable cards per day showing:
  - Day theme (e.g., "Old City Exploration")
  - Activities with time, duration, estimated cost, and tips
  - Lunch and dinner recommendations
  - Accommodation suggestion
  - Daily budget estimate
- **Packing Essentials** and **Cultural Tips** (two columns)
- **Emergency Contacts** for the destination

---

## Input/Output Reference

### Input fields

- **Destination** — Be specific: `Kyoto, Japan` gives better results than `Japan`
- **Interests** — The more specific, the better: `street food, rooftop bars, contemporary art` vs. just `food`
- **Travel Month** — Enables seasonal activity and weather recommendations
- **Budget Level:**
  - `budget` — Hostels, street food, free attractions
  - `mid-range` — 3-star hotels, mid-range restaurants, some paid tours
  - `luxury` — 5-star hotels, fine dining, private experiences

### Output structure

| Field | Description |
|---|---|
| `destination` | Travel destination |
| `trip_duration` | Duration string (e.g., `5 days`) |
| `travel_style` | budget / mid-range / luxury |
| `best_time_to_visit` | Recommended travel season |
| `getting_around` | Transportation tips in the destination |
| `days[].date_label` | Day label (e.g., `Day 1 - Arrival`) |
| `days[].theme` | Theme for the day |
| `days[].activities[].time` | Time of activity |
| `days[].activities[].name` | Activity or place name |
| `days[].activities[].duration` | Estimated duration |
| `days[].activities[].estimated_cost` | Estimated cost |
| `days[].activities[].tips` | Practical tips |
| `days[].lunch_recommendation` | Lunch suggestion |
| `days[].dinner_recommendation` | Dinner suggestion |
| `days[].accommodation` | Where to stay |
| `days[].daily_budget_estimate` | Estimated daily spend |
| `total_budget_estimate` | Total trip budget estimate |
| `packing_essentials` | Items to pack |
| `cultural_tips` | Etiquette and cultural advice |
| `emergency_contacts` | Emergency numbers and info |

---

## Troubleshooting

**`AZURE_GENAI_API_KEY is not set in environment`**
→ Ensure `.env` exists in the `ps7/` directory with the correct key.

**`Itinerary generation failed: ...`**
→ Check Azure credentials and endpoint. Verify the deployment is active.

**Itinerary is too generic**
→ Add more specific interests and a travel month. The more context you provide, the more tailored the result.

**App shows no output after clicking Generate**
→ Both Destination and Interests fields are required. The button is disabled if either is empty.
