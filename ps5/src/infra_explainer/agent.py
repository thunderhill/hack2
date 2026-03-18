from .config import get_llm_client, get_model
from .models import ChangeExplanation
from .prompts import SYSTEM_PROMPT, build_user_message


def explain_change(change_request: str, model_key: str = "gpt-4o", environment: str = "") -> ChangeExplanation:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(change_request, environment)},
        ],
        response_format=ChangeExplanation,
    )
    return response.choices[0].message.parsed
