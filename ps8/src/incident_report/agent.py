from .config import get_llm_client, get_model
from .models import IncidentReport
from .prompts import SYSTEM_PROMPT, build_user_message


def generate_incident_report(incident_notes: str, model_key: str = "gpt-4o", service_name: str = "") -> IncidentReport:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(incident_notes, service_name)},
        ],
        response_format=IncidentReport,
    )
    return response.choices[0].message.parsed
