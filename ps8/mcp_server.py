"""MCP Server for DevOps Incident Report Generator — exposes agent + ChromaDB as tools."""

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

from incident_report.agent import generate_incident_report
from incident_report.config import MODEL_OPTIONS
from chroma_store import ChromaStore

mcp = FastMCP("DevOps Incident Report Generator")
store = ChromaStore("incident_report")


@mcp.tool()
def generate_devops_incident_report(incident_notes: str, model_key: str = "gpt-4o-mini", service_name: str = "") -> dict:
    """Generate professional, blameless post-incident reports with timeline, root cause analysis, impact assessment, and action items.

    Args:
        incident_notes: The incident timeline and notes to analyze
        model_key: LLM model to use (gpt-4o, gpt-4o-mini, gpt-35-turbo)
        service_name: Optional service or system name
    """
    result = generate_incident_report(incident_notes, model_key, service_name)
    result_dict = result.model_dump()
    store.add(incident_notes, result_dict, model_key)
    return result_dict


@mcp.tool()
def search_past_analyses(query: str, n_results: int = 5) -> list:
    """Search past incident report analyses by semantic similarity.

    Args:
        query: Search query text
        n_results: Number of results to return (default 5)
    """
    return store.search(query, n_results)


@mcp.tool()
def get_recent_analyses(n: int = 10) -> list:
    """Get the most recent incident report analyses.

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
