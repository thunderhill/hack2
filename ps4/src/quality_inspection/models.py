from pydantic import BaseModel, Field


class DefectDetail(BaseModel):
    defect_id: str = Field(description="Unique defect identifier e.g. D001")
    defect_type: str = Field(description="Type: dimensional | surface | material | functional | cosmetic")
    description: str = Field(description="Clear description of the defect")
    severity: str = Field(description="Severity: critical | major | minor")
    affected_component: str = Field(description="Component or part affected")


class QualityInspectionReport(BaseModel):
    product_id: str = Field(description="Product or batch identifier extracted from input")
    inspection_date: str = Field(description="Inspection date extracted or 'Not specified'")
    overall_quality_status: str = Field(description="PASS | FAIL | CONDITIONAL_PASS")
    defect_count: int = Field(description="Total number of defects identified")
    defects: list[DefectDetail] = Field(description="List of individual defects found")
    quality_score: float = Field(description="Quality score 0.0 to 100.0")
    root_cause_analysis: str = Field(description="Probable root causes of defects")
    corrective_actions: list[str] = Field(description="Immediate corrective actions required")
    preventive_measures: list[str] = Field(description="Long-term preventive measures")
    disposition: str = Field(description="Recommended disposition: rework | scrap | accept | quarantine")
    inspector_notes: str = Field(description="Additional observations and notes")
