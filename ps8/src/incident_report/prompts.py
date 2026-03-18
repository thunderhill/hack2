SYSTEM_PROMPT = """You are a senior site reliability engineer (SRE) expert in writing post-incident reports (PIRs).
Given an incident timeline and notes, you write a professional, blameless post-incident report that:
1. Accurately reconstructs the timeline from available information
2. Identifies root cause using 5-why methodology
3. Assesses customer impact honestly
4. Highlights what went well and what needs improvement
5. Creates specific, actionable follow-up items with owners and deadlines
6. Maintains a blameless, learning-focused tone

Follow Google SRE and ITIL incident management best practices."""


def build_user_message(incident_notes: str, service_name: str = "") -> str:
    service_context = f"\nService/System: {service_name}" if service_name else ""
    return f"""Generate a post-incident report from the following incident notes:{service_context}

--- INCIDENT NOTES ---
{incident_notes}
--- END NOTES ---

Create a complete, professional post-incident report suitable for sharing with stakeholders."""
