from .config import get_llm_client, get_model
from .models import ExpenseSummary
from .prompts import SYSTEM_PROMPT, build_user_message


def summarize_expenses(expense_data: str, model_key: str = "gpt-4o", company_policy_notes: str = "") -> ExpenseSummary:
    client = get_llm_client()
    deployment = get_model(model_key)
    response = client.beta.chat.completions.parse(
        model=deployment,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(expense_data, company_policy_notes)},
        ],
        response_format=ExpenseSummary,
    )
    return response.choices[0].message.parsed
