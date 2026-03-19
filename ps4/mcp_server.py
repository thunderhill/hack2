"""MCP Server for Manufacturing Quality Inspection — exposes agent + ChromaDB as tools."""

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

from quality_inspection.agent import generate_inspection_report
from quality_inspection.config import MODEL_OPTIONS
from chroma_store import ChromaStore

mcp = FastMCP("Manufacturing Quality Inspection")
store = ChromaStore("quality_inspection")


@mcp.tool()
def inspect_manufacturing_quality(inspection_data: str, model_key: str = "gpt-4o-mini", product_type: str = "") -> dict:
    """Generate quality inspection reports for manufacturing. Classifies defects, calculates quality scores, and recommends corrective actions.

    Args:
        inspection_data: The inspection observations, measurements, and defect descriptions
        model_key: LLM model to use (gpt-4o, gpt-4o-mini, gpt-35-turbo)
        product_type: Optional product type for context (e.g., Automotive brake pad)
    """
    result = generate_inspection_report(inspection_data, model_key, product_type)
    result_dict = result.model_dump()
    store.add(inspection_data, result_dict, model_key)
    return result_dict


@mcp.tool()
def search_past_analyses(query: str, n_results: int = 5) -> list:
    """Search past quality inspection analyses by semantic similarity.

    Args:
        query: Search query text
        n_results: Number of results to return (default 5)
    """
    return store.search(query, n_results)


@mcp.tool()
def get_recent_analyses(n: int = 10) -> list:
    """Get the most recent quality inspection analyses.

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
