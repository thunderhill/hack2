"""MCP Server for Travel Itinerary Generator — exposes agent + ChromaDB as tools."""

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

from travel_itinerary.agent import generate_itinerary
from travel_itinerary.config import MODEL_OPTIONS
from travel_itinerary.guardrails import run_input_guardrails, run_output_guardrails
from chroma_store import ChromaStore

mcp = FastMCP("Travel Itinerary Generator")
store = ChromaStore("travel_itinerary")


@mcp.tool()
def generate_travel_itinerary(destination: str, duration_days: int, budget: str, interests: str, model_key: str = "gpt-4o-mini", travel_month: str = "") -> dict:
    """Create detailed, personalized day-by-day travel itineraries with activities, dining, logistics, and cultural tips.

    Args:
        destination: Travel destination (e.g., "Kyoto, Japan")
        duration_days: Number of days for the trip
        budget: Budget level (budget, mid-range, luxury)
        interests: Comma-separated interests (e.g., "temples, food, hiking")
        model_key: LLM model to use (gpt-4o, gpt-4o-mini, gpt-35-turbo)
        travel_month: Optional travel month (e.g., "April")
    """
    combined_input = f"Destination: {destination}, Interests: {interests}"
    guard = run_input_guardrails(combined_input)
    if guard.blocked:
        return {"error": f"Input blocked by guardrails: {guard.block_reason}", "guardrails": guard.model_dump()}

    result = generate_itinerary(destination, duration_days, budget, interests, model_key, travel_month)
    result_dict = result.model_dump()

    out_guard = run_output_guardrails(result)
    result_dict["_guardrails"] = {"input": guard.model_dump(), "output": out_guard.model_dump()}

    input_text = f"Destination: {destination}, Duration: {duration_days} days, Budget: {budget}, Interests: {interests}"
    store.add(input_text, result_dict, model_key)
    return result_dict


@mcp.tool()
def search_past_analyses(query: str, n_results: int = 5) -> list:
    """Search past travel itinerary analyses by semantic similarity.

    Args:
        query: Search query text
        n_results: Number of results to return (default 5)
    """
    return store.search(query, n_results)


@mcp.tool()
def get_recent_analyses(n: int = 10) -> list:
    """Get the most recent travel itinerary analyses.

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
