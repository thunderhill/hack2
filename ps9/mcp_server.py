"""MCP Server for Travel Expense Report Summarizer — exposes agent + ChromaDB as tools."""

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

from expense_report.agent import summarize_expenses
from expense_report.config import MODEL_OPTIONS
from expense_report.guardrails import run_input_guardrails, run_output_guardrails
from chroma_store import ChromaStore

mcp = FastMCP("Travel Expense Report Summarizer")
store = ChromaStore("expense_report")


@mcp.tool()
def summarize_travel_expenses(expense_data: str, model_key: str = "gpt-4o-mini", company_policy_notes: str = "") -> dict:
    """Review and categorize travel expenses, check compliance against corporate policies, flag violations, and provide approval recommendations.

    Args:
        expense_data: The expense report text to analyze
        model_key: LLM model to use (gpt-4o, gpt-4o-mini, gpt-35-turbo)
        company_policy_notes: Optional additional company policy notes
    """
    guard = run_input_guardrails(expense_data)
    if guard.blocked:
        return {"error": f"Input blocked by guardrails: {guard.block_reason}", "guardrails": guard.model_dump()}

    result = summarize_expenses(guard.sanitized_input, model_key, company_policy_notes)
    result_dict = result.model_dump()

    out_guard = run_output_guardrails(result)
    result_dict["_guardrails"] = {"input": guard.model_dump(), "output": out_guard.model_dump()}

    store.add(expense_data, result_dict, model_key)
    return result_dict


@mcp.tool()
def search_past_analyses(query: str, n_results: int = 5) -> list:
    """Search past expense report analyses by semantic similarity.

    Args:
        query: Search query text
        n_results: Number of results to return (default 5)
    """
    return store.search(query, n_results)


@mcp.tool()
def get_recent_analyses(n: int = 10) -> list:
    """Get the most recent expense report analyses.

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
