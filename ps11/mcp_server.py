import os, ssl, warnings
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
load_dotenv(override=True)

import io
import pandas as pd
from mcp.server.fastmcp import FastMCP

from eda_report.config import get_llm_client, get_model, MODEL_OPTIONS
from eda_report.infer import infer_columns
from eda_report.preprocess import impute_nulls, parse_datetimes
from eda_report.profile import build_profile
from eda_report.insights import get_section_narrative, get_executive_summary
from chroma_store import ChromaStore

mcp = FastMCP("EDA Report Generator")
_store = ChromaStore()
_DEFAULT_MODEL_KEY = "gpt-4o-mini"

@mcp.tool()
def profile_dataset(csv_content: str, dataset_name: str) -> str:
    """Parse CSV content and return a DatasetProfile as JSON."""
    df = pd.read_csv(io.StringIO(csv_content))
    metas = infer_columns(df)
    df = impute_nulls(df.copy(), metas)
    df = parse_datetimes(df, metas)
    profile = build_profile(df, metas, dataset_name=dataset_name)
    return profile.model_dump_json()

@mcp.tool()
def get_insights(profile_json: str, section: str) -> str:
    """Generate a narrative for the given report section using the LLM."""
    from eda_report.models import DatasetProfile
    profile = DatasetProfile.model_validate_json(profile_json)
    client = get_llm_client()
    model = get_model(_DEFAULT_MODEL_KEY)
    return get_section_narrative(client, model, profile, section)

@mcp.tool()
def search_past_reports(query: str) -> str:
    """Search ChromaDB for past EDA reports similar to the query."""
    results = _store.search_similar(query, n=3)
    return json.dumps(results)

if __name__ == "__main__":
    mcp.run()
