import os
import httpx
from functools import lru_cache
from openai import OpenAI

MODEL_OPTIONS = ["gpt-4o-mini", "gpt-4o", "gpt-35-turbo"]
MODEL_DISPLAY_MAP = {
    "gpt-4o-mini":  "azure/genailab-maas-gpt-4o-mini",
    "gpt-4o":       "azure/genailab-maas-gpt-4o",
    "gpt-35-turbo": "genailab-maas-gpt-35-turbo",
}

_SENSITIVE: dict[str, str] = {
    "crime":     "reported incident",
    "criminal":  "individual of concern",
    "murder":    "serious incident",
    "assault":   "physical altercation",
    "theft":     "property incident",
    "stolen":    "property incident",
    "drug":      "substance concern",
    "narcotic":  "substance concern",
    "weapon":    "safety equipment concern",
    "violence":  "public disturbance",
    "violent":   "disruptive",
    "kill":      "serious incident",
}

def sanitize_for_proxy(text: str) -> str:
    for word, replacement in _SENSITIVE.items():
        text = text.replace(word, replacement)
        text = text.replace(word.capitalize(), replacement.capitalize())
        text = text.replace(word.upper(), replacement.upper())
    return text

def get_model(model_key: str) -> str:
    return MODEL_DISPLAY_MAP.get(model_key, MODEL_DISPLAY_MAP["gpt-4o-mini"])

@lru_cache(maxsize=1)
def _cached_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/") + "/v1",
        http_client=httpx.Client(verify=False),
    )

def get_llm_client() -> OpenAI:
    api_key = (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("AZURE_GENAI_API_KEY", "")
    )
    base_url = os.environ.get("OPENAI_BASE_URL", "https://genailab.tcs.in")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY is not set in .env")
    return _cached_client(api_key, base_url)
