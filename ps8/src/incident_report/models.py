from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    timestamp: str = Field(description="Event timestamp")
    event: str = Field(description="What happened at this time")
    actor: str = Field(description="Who or what triggered this: system | engineer | automated")


class ActionItem(BaseModel):
    action: str = Field(description="Specific action to take")
    owner: str = Field(description="Team or role responsible")
    priority: str = Field(description="Priority: P1 | P2 | P3")
    due_date: str = Field(description="Target completion date or timeframe")


class IncidentReport(BaseModel):
    incident_id: str = Field(description="Incident ID extracted or generated")
    title: str = Field(description="Concise incident title")
    severity: str = Field(description="Severity: SEV1 | SEV2 | SEV3 | SEV4")
    status: str = Field(description="Status: resolved | monitoring | ongoing")
    incident_start: str = Field(description="When the incident started")
    incident_end: str = Field(description="When the incident was resolved")
    total_duration: str = Field(description="Total incident duration")
    time_to_detect: str = Field(description="Time from incident start to detection")
    time_to_resolve: str = Field(description="Time from detection to resolution")
    affected_services: list[str] = Field(description="List of affected services/systems")
    customer_impact: str = Field(description="Description of customer/user impact")
    users_affected: str = Field(description="Estimated number of users affected")
    executive_summary: str = Field(description="2-3 sentence executive summary")
    timeline: list[TimelineEvent] = Field(description="Chronological timeline of events")
    root_cause: str = Field(description="Root cause of the incident")
    contributing_factors: list[str] = Field(description="Contributing factors")
    what_went_well: list[str] = Field(description="Things that worked well during incident response")
    what_went_wrong: list[str] = Field(description="Things that need improvement")
    action_items: list[ActionItem] = Field(description="Follow-up action items")
    lessons_learned: str = Field(description="Key lessons learned from this incident")
