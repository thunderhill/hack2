"""MCP Server for Infrastructure Change Explainer — exposes agent + ChromaDB as tools."""

import os, ssl, warnings

os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv

load_dotenv(override=True)

from mcp.server.fastmcp import FastMCP

from infra_explainer.agent import explain_change
from infra_explainer.config import MODEL_OPTIONS
from infra_explainer.guardrails import run_input_guardrails, run_output_guardrails
from chroma_store import ChromaStore

mcp = FastMCP("Infrastructure Change Explainer")
store = ChromaStore("infra_explainer")


@mcp.tool()
def explain_infra_change(change_request: str, model_key: str = "gpt-4o-mini", environment: str = "") -> dict:
    """Explain infrastructure changes (Terraform, K8s, Ansible) in plain English, assess risks, and provide approval recommendations.

    Args:
        change_request: The infrastructure change text (Terraform plan, K8s diff, Ansible playbook, etc.)
        model_key: LLM model to use (gpt-4o, gpt-4o-mini, gpt-35-turbo)
        environment: Target environment (e.g., Production, Staging)
    """
    guard = run_input_guardrails(change_request)
    if guard.blocked:
        return {"error": f"Input blocked by guardrails: {guard.block_reason}", "guardrails": guard.model_dump()}

    result = explain_change(guard.sanitized_input, model_key, environment)
    result_dict = result.model_dump()

    out_guard = run_output_guardrails(result)
    result_dict["_guardrails"] = {"input": guard.model_dump(), "output": out_guard.model_dump()}

    store.add(change_request, result_dict, model_key)
    return result_dict


@mcp.tool()
def search_past_analyses(query: str, n_results: int = 5) -> list:
    """Search past infrastructure change analyses by semantic similarity.

    Args:
        query: Search query text
        n_results: Number of results to return (default 5)
    """
    return store.search(query, n_results)


@mcp.tool()
def get_recent_analyses(n: int = 10) -> list:
    """Get the most recent infrastructure change analyses.

    Args:
        n: Number of recent analyses to return (default 10)
    """
    return store.get_recent(n)


@mcp.tool()
def list_models() -> list:
    """List available LLM models."""
    return MODEL_OPTIONS


if __name__ == "__main__":
    mcp.run()
