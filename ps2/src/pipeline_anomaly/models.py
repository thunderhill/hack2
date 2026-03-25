from pydantic import BaseModel, Field, field_validator


class AnomalyExplanation(BaseModel):
    anomaly_type: str = Field(description="Type/category of the anomaly detected")
    plain_english_summary: str = Field(description="Clear explanation of what went wrong for a non-expert")
    root_cause: str = Field(description="Technical root cause of the anomaly")
    affected_stage: str = Field(description="Pipeline stage where the anomaly occurred")
    severity: str = Field(description="Severity level: critical | high | medium | low")
    remediation_steps: list[str] = Field(description="Ordered list of steps to fix the issue")
    prevention_tips: list[str] = Field(description="Tips to prevent this anomaly in the future")
    confidence_level: float = Field(
        default=0.0,
        description="Model confidence in this analysis, 0.0–1.0",
    )

    @field_validator("confidence_level", mode="before")
    @classmethod
    def normalise_confidence(cls, v: float) -> float:
        """Normalise: if >= 2.0, treat as percentage and divide by 100; then clamp to [0.0, 1.0]."""
        if v >= 2.0:
            v = v / 100.0
        return max(0.0, min(1.0, v))
