import json
from .config import get_llm_client, get_model
from .models import ExpenseSummary
from .prompts import SYSTEM_PROMPT, build_user_message
from .guardrails import run_input_guardrails, run_output_guardrails


def summarize_expenses(expense_data: str, model_key: str = "gpt-4o", company_policy_notes: str = "") -> ExpenseSummary:
    # ── Input guardrails ─────────────────────────────────────────────────
    guard = run_input_guardrails(expense_data)
    if guard.blocked:
        raise ValueError(f"Input blocked by guardrails: {guard.block_reason}")
    sanitized_input = guard.sanitized_input

    # ── LLM call ─────────────────────────────────────────────────────────
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT + "\nRespond ONLY with valid JSON. No markdown, no explanation."},
            {"role": "user", "content": build_user_message(sanitized_input, company_policy_notes)},
        ],
        max_tokens=4096,
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
    result = ExpenseSummary(**data)

    # ── Output guardrails ────────────────────────────────────────────────
    out_guard = run_output_guardrails(result)
    if out_guard.warnings:
        result._guardrail_warnings = out_guard.warnings

    return result
