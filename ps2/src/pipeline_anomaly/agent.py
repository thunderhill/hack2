from .config import get_llm_client, get_model
from .models import AnomalyExplanation
from .prompts import SYSTEM_PROMPT, build_user_message


def explain_anomaly(log_snippet: str, model_key: str = "gpt-4o") -> AnomalyExplanation:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(log_snippet)},
        ],
        response_format=AnomalyExplanation,
    )
    return response.choices[0].message.parsed
