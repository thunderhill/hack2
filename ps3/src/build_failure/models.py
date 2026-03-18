from pydantic import BaseModel, Field


class ErrorLocation(BaseModel):
    file_path: str = Field(description="File path where error occurred, or 'unknown'")
    line_number: str = Field(description="Line number of error, or 'unknown'")
    column: str = Field(description="Column number, or 'unknown'")


class BuildDiagnosis(BaseModel):
    build_tool: str = Field(description="Build tool detected: maven | gradle | npm | pip | cargo | make | other")
    language: str = Field(description="Programming language: java | python | javascript | rust | c++ | other")
    error_type: str = Field(description="Type of error: compilation | dependency | configuration | linking | syntax | runtime")
    error_message: str = Field(description="The core error message extracted from the output")
    error_location: ErrorLocation = Field(description="Where the error occurred")
    diagnosis: str = Field(description="Clear diagnosis of why the build failed")
    fix_explanation: str = Field(description="Step-by-step explanation of how to fix it")
    code_fix: str = Field(description="Concrete code or config change to fix the issue, or 'N/A'")
    estimated_fix_time: str = Field(description="Estimated time to fix: minutes | hours | days")
