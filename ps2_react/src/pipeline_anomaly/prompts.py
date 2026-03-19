SYSTEM_PROMPT = """You are an expert DevOps engineer and CI/CD pipeline analyst.
Given a pipeline log snippet, you analyze it to:
1. Identify the type of anomaly or failure
2. Explain it clearly in plain English for developers
3. Pinpoint the root cause
4. Suggest actionable remediation steps

Be specific and practical. Use the log content to ground your analysis."""


def build_user_message(log_snippet: str) -> str:
    return f"""Analyze the following CI/CD pipeline log and explain the anomaly:

--- PIPELINE LOG ---
{log_snippet}
--- END LOG ---

Provide a thorough analysis including the anomaly type, plain English summary, root cause, affected stage, severity, remediation steps, and prevention tips."""
