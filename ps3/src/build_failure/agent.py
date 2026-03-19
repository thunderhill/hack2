import json
from .config import get_llm_client, get_model
from .models import BuildDiagnosis
from .prompts import SYSTEM_PROMPT, build_user_message


def diagnose_build(build_output: str, model_key: str = "gpt-4o", language_hint: str = "") -> BuildDiagnosis:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(build_output, language_hint)},
        ],
        max_tokens=1024,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    if raw.endswith("```"):
        raw = raw[:-3]
    data = json.loads(raw)
    return BuildDiagnosis(**data)
