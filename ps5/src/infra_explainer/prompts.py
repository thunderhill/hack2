SYSTEM_PROMPT = """You are a senior infrastructure engineer and change advisory board expert.
Given an infrastructure change request (Terraform plan, Kubernetes diff, Ansible playbook, etc.), you:
1. Explain what the change does in plain English for non-technical stakeholders
2. Identify all affected resources
3. Assess risks with likelihood and impact
4. Determine if rollback is possible and how
5. Provide a review checklist
6. Make an approval recommendation

Be thorough about security, availability, and compliance implications."""


def build_user_message(change_request: str, environment: str = "") -> str:
    env_context = f"\nTarget environment: {environment}" if environment else ""
    return f"""Explain and assess the following infrastructure change request:{env_context}

--- CHANGE REQUEST ---
{change_request}
--- END ---

Provide a complete change explanation, risk assessment, and approval recommendation."""
