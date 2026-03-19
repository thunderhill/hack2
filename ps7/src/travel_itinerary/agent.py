import json
from .config import get_llm_client, get_model
from .models import TravelItinerary
from .prompts import SYSTEM_PROMPT, build_user_message
from .guardrails import run_input_guardrails, run_output_guardrails


def generate_itinerary(destination: str, duration_days: int, budget: str, interests: str, model_key: str = "gpt-4o", travel_month: str = "") -> TravelItinerary:
    # ── Input guardrails ─────────────────────────────────────────────────
    combined_input = f"Destination: {destination}, Interests: {interests}"
    guard = run_input_guardrails(combined_input)
    if guard.blocked:
        raise ValueError(f"Input blocked by guardrails: {guard.block_reason}")
    # Sanitize destination and interests individually
    sanitized_dest = guard.sanitized_input.split(", Interests: ")[0].replace("Destination: ", "") if ", Interests: " in guard.sanitized_input else destination
    sanitized_interests = guard.sanitized_input.split(", Interests: ")[1] if ", Interests: " in guard.sanitized_input else interests

    # ── LLM call ─────────────────────────────────────────────────────────
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(sanitized_dest, duration_days, budget, sanitized_interests, travel_month)},
        ],
        max_tokens=4096,
        temperature=0.3,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    if raw.endswith("```"):
        raw = raw[:-3]
    data = json.loads(raw)
    result = TravelItinerary(**data)

    # ── Output guardrails ────────────────────────────────────────────────
    out_guard = run_output_guardrails(result)
    if out_guard.warnings:
        result._guardrail_warnings = out_guard.warnings

    return result
