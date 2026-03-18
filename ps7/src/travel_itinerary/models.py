from pydantic import BaseModel, Field


class Activity(BaseModel):
    time: str = Field(description="Time of activity e.g. '9:00 AM'")
    name: str = Field(description="Activity or place name")
    description: str = Field(description="Brief description of the activity")
    duration: str = Field(description="Estimated duration e.g. '2 hours'")
    estimated_cost: str = Field(description="Estimated cost e.g. '$20' or 'Free'")
    tips: str = Field(description="Practical tips for this activity")


class DayPlan(BaseModel):
    day_number: int = Field(description="Day number starting from 1")
    date_label: str = Field(description="Date label e.g. 'Day 1 - Arrival'")
    theme: str = Field(description="Theme for the day e.g. 'Old City Exploration'")
    activities: list[Activity] = Field(description="List of activities for the day")
    lunch_recommendation: str = Field(description="Lunch restaurant or food recommendation")
    dinner_recommendation: str = Field(description="Dinner restaurant or food recommendation")
    accommodation: str = Field(description="Where to stay or neighborhood to stay in")
    daily_budget_estimate: str = Field(description="Estimated total spending for the day")


class TravelItinerary(BaseModel):
    destination: str = Field(description="Travel destination")
    trip_duration: str = Field(description="Trip duration e.g. '5 days'")
    travel_style: str = Field(description="Travel style: budget | mid-range | luxury")
    best_time_to_visit: str = Field(description="Best time to visit the destination")
    days: list[DayPlan] = Field(description="Day-by-day itinerary")
    total_budget_estimate: str = Field(description="Total trip budget estimate")
    packing_essentials: list[str] = Field(description="Essential items to pack")
    cultural_tips: list[str] = Field(description="Cultural etiquette and tips")
    emergency_contacts: str = Field(description="Emergency contact numbers and information")
    getting_around: str = Field(description="Transportation tips within the destination")
