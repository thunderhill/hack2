import json
from openai import OpenAI
from eda_report.models import DatasetProfile, ExecutiveSummary
from eda_report.config import sanitize_for_proxy

_SECTION_SYSTEM = (
    "You are a senior data analyst writing a business-friendly EDA report. "
    "Given dataset statistics in JSON, write 2-4 sentences explaining key patterns "
    "for the {section} section. Use plain English. No technical jargon. No markdown. "
    "Plain text only."
)

_EXEC_SYSTEM = (
    "You are a senior data analyst. Given a full dataset profile in JSON, produce an "
    "executive summary. Respond ONLY with valid JSON matching this schema exactly — "
    "no markdown fences, no explanation:\n"
    '{{"key_findings": ["...", "..."], '
    '"data_quality_score": 85.0, '
    '"anomalies": ["..."], '
    '"recommendations": ["..."], '
    '"ml_readiness": "..."}}'
)

def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return raw.strip()

def get_section_narrative(
    client: OpenAI, model: str, profile: DatasetProfile, section: str
) -> str:
    section_data = {
        "dataset": profile.dataset_name,
        "rows": profile.row_count,
        "section": section,
        "columns": [c.model_dump(exclude_none=True) for c in profile.columns][:20],  # cap at 20 cols to stay within token budget
    }
    user_content = sanitize_for_proxy(json.dumps(section_data))
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SECTION_SYSTEM.format(section=section)},
                {"role": "user", "content": user_content},
            ],
            max_tokens=256,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"AI analysis unavailable: {e}"

def get_executive_summary(
    client: OpenAI, model: str, profile: DatasetProfile
) -> ExecutiveSummary:
    profile_data = {
        "dataset": profile.dataset_name,
        "rows": profile.row_count,
        "cols": profile.col_count,
        "duplicates": profile.duplicate_row_count,
        "memory_mb": profile.memory_mb,
        "columns": [c.model_dump(exclude_none=True) for c in profile.columns],
    }
    user_content = sanitize_for_proxy(json.dumps(profile_data))
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _EXEC_SYSTEM},
                {"role": "user", "content": user_content},
            ],
            max_tokens=1024,
            temperature=0.2,
        )
        raw = _strip_fences(resp.choices[0].message.content)
        data = json.loads(raw)
        return ExecutiveSummary(**data)
    except Exception as e:
        return ExecutiveSummary(
            key_findings=[f"Summary generation failed: {e}"],
            data_quality_score=0.0,
            anomalies=[],
            recommendations=["Retry with a different model or check VPN connection."],
            ml_readiness="Unable to assess — AI service unavailable.",
        )
