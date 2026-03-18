from pydantic import BaseModel, Field


class RiskItem(BaseModel):
    risk: str = Field(description="Description of the risk")
    likelihood: str = Field(description="Likelihood: high | medium | low")
    impact: str = Field(description="Impact: high | medium | low")


class ChangeExplanation(BaseModel):
    change_type: str = Field(description="Type: terraform | kubernetes | ansible | cloudformation | firewall | network | other")
    summary: str = Field(description="One-sentence summary of what this change does")
    plain_english: str = Field(description="Detailed plain English explanation for non-infrastructure experts")
    resources_affected: list[str] = Field(description="List of infrastructure resources being changed")
    change_nature: str = Field(description="Nature: additive | destructive | modifying | scaling | security | configuration")
    risk_level: str = Field(description="Overall risk: critical | high | medium | low")
    risks: list[RiskItem] = Field(description="Specific risks identified")
    rollback_possible: bool = Field(description="Whether this change can be rolled back")
    rollback_procedure: str = Field(description="How to roll back if needed, or 'N/A'")
    review_checklist: list[str] = Field(description="Items reviewers should verify before approving")
    approval_recommendation: str = Field(description="APPROVE | APPROVE_WITH_CONDITIONS | REJECT | NEEDS_MORE_INFO")
