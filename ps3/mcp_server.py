"""MCP Server for Build Failure Diagnosis — exposes agent + ChromaDB as tools."""

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

from build_failure.agent import diagnose_build
from build_failure.config import MODEL_OPTIONS
from chroma_store import ChromaStore

mcp = FastMCP("Build Failure Diagnosis")
store = ChromaStore("build_failure")


@mcp.tool()
def diagnose_build_failure(build_output: str, model_key: str = "gpt-4o-mini", language_hint: str = "") -> dict:
    """Diagnose build failures from compiler/build tool output. Provides error classification, location, diagnosis, and code fixes.

    Args:
        build_output: The build/compiler output text to diagnose
        model_key: LLM model to use (gpt-4o, gpt-4o-mini, gpt-35-turbo)
        language_hint: Optional language/framework hint (e.g. "Java Spring Boot")
    """
    result = diagnose_build(build_output, model_key, language_hint)
    result_dict = result.model_dump()
    store.add(build_output, result_dict, model_key)
    return result_dict


@mcp.tool()
def search_past_analyses(query: str, n_results: int = 5) -> list:
    """Search past build failure analyses by semantic similarity.

    Args:
        query: Search query text
        n_results: Number of results to return (default 5)
    """
    return store.search(query, n_results)


@mcp.tool()
def get_recent_analyses(n: int = 10) -> list:
    """Get the most recent build failure analyses.

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
