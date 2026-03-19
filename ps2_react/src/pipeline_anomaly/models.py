from pydantic import BaseModel, Field


class AnomalyExplanation(BaseModel):
    anomaly_type: str = Field(description="Type/category of the anomaly detected")
    plain_english_summary: str = Field(description="Clear explanation of what went wrong for a non-expert")
    root_cause: str = Field(description="Technical root cause of the anomaly")
    affected_stage: str = Field(description="Pipeline stage where the anomaly occurred")
    severity: str = Field(description="Severity level: critical | high | medium | low")
    remediation_steps: list[str] = Field(description="Ordered list of steps to fix the issue")
    prevention_tips: list[str] = Field(description="Tips to prevent this anomaly in the future")
