from pydantic import BaseModel, Field


class ResourceRecommendation(BaseModel):
    resource_type: str = Field(description="Resource type: compute | memory | storage | network | database")
    current_state: str = Field(description="Current resource state/capacity")
    recommended_state: str = Field(description="Recommended resource state/capacity")
    urgency: str = Field(description="Urgency: immediate | within_month | within_quarter | planned")
    estimated_cost_impact: str = Field(description="Estimated monthly cost impact e.g. +$500/month")


class CapacityPlan(BaseModel):
    assessment_period: str = Field(description="Assessment period or timeframe")
    capacity_risk_level: str = Field(description="Overall capacity risk: critical | high | medium | low")
    bottlenecks: list[str] = Field(description="Current or near-term capacity bottlenecks identified")
    recommendations: list[ResourceRecommendation] = Field(description="Specific resource recommendations")
    scaling_strategy: str = Field(description="Recommended scaling strategy: vertical | horizontal | hybrid | serverless")
    timeline: str = Field(description="Recommended implementation timeline")
    total_cost_estimate: str = Field(description="Total estimated monthly cost for recommended changes")
    risk_if_not_acted: str = Field(description="Consequences if capacity planning is not done")
    optimization_opportunities: list[str] = Field(description="Cost optimization opportunities identified")
    executive_summary: str = Field(description="2-3 sentence executive summary of the capacity situation")
