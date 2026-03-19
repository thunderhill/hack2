"""MCP Server for Capacity Planning Advisor — exposes agent + ChromaDB as tools."""

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

from capacity_planning.agent import generate_capacity_plan
from capacity_planning.config import MODEL_OPTIONS
from chroma_store import ChromaStore

mcp = FastMCP("Capacity Planning Advisor")
store = ChromaStore("capacity_planning")


@mcp.tool()
def plan_infrastructure_capacity(metrics_data: str, model_key: str = "gpt-4o-mini", growth_projection: str = "", sla_requirements: str = "") -> dict:
    """Analyze infrastructure metrics and utilization trends to recommend resource scaling, estimate costs, and identify optimization opportunities.

    Args:
        metrics_data: Current infrastructure metrics and utilization data
        model_key: LLM model to use (gpt-4o, gpt-4o-mini, gpt-35-turbo)
        growth_projection: Expected growth projection (e.g., 40% user growth in 6 months)
        sla_requirements: SLA requirements (e.g., 99.9% uptime, <200ms response)
    """
    result = generate_capacity_plan(metrics_data, model_key, growth_projection, sla_requirements)
    result_dict = result.model_dump()
    store.add(metrics_data, result_dict, model_key)
    return result_dict


@mcp.tool()
def search_past_analyses(query: str, n_results: int = 5) -> list:
    """Search past capacity planning analyses by semantic similarity.

    Args:
        query: Search query text
        n_results: Number of results to return (default 5)
    """
    return store.search(query, n_results)


@mcp.tool()
def get_recent_analyses(n: int = 10) -> list:
    """Get the most recent capacity planning analyses.

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
