from .config import get_llm_client, get_model
from .models import CapacityPlan
from .prompts import SYSTEM_PROMPT, build_user_message


def generate_capacity_plan(metrics_data: str, model_key: str = "gpt-4o", growth_projection: str = "", sla_requirements: str = "") -> CapacityPlan:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(metrics_data, growth_projection, sla_requirements)},
        ],
        response_format=CapacityPlan,
    )
    return response.choices[0].message.parsed
