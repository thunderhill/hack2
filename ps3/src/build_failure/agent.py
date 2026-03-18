from .config import get_llm_client, get_model
from .models import BuildDiagnosis
from .prompts import SYSTEM_PROMPT, build_user_message


def diagnose_build(build_output: str, model_key: str = "gpt-4o", language_hint: str = "") -> BuildDiagnosis:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(build_output, language_hint)},
        ],
        response_format=BuildDiagnosis,
    )
    return response.choices[0].message.parsed
