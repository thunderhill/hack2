import json
from .config import get_llm_client, get_model
from .models import AnomalyExplanation
from .prompts import SYSTEM_PROMPT, build_user_message


def explain_anomaly(log_snippet: str, model_key: str = "gpt-4o") -> AnomalyExplanation:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(log_snippet)},
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
    return AnomalyExplanation(**data)
