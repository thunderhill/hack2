import os
from functools import lru_cache
from openai import AzureOpenAI

MODEL_OPTIONS = ["gpt-4o", "gpt-4o-mini", "gpt-35-turbo"]
MODEL_DISPLAY_MAP = {
    "gpt-4o": "genailab-maas-gpt-4o",
    "gpt-4o-mini": "genailab-maas-gpt-4o-mini",
    "gpt-35-turbo": "genailab-maas-gpt-35-turbo",
}

def get_model(model_key: str) -> str:
    return MODEL_DISPLAY_MAP.get(model_key, MODEL_DISPLAY_MAP["gpt-4o"])

@lru_cache(maxsize=1)
def _cached_client(api_key: str, endpoint: str, api_version: str) -> AzureOpenAI:
    return AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_version)

def get_llm_client() -> AzureOpenAI:
    api_key = os.environ.get("AZURE_GENAI_API_KEY", "")
    if not api_key:
        raise EnvironmentError("AZURE_GENAI_API_KEY is not set in environment.")
    endpoint = os.environ.get("AZURE_GENAI_ENDPOINT", "https://genailab-maas.services.ai.azure.com")
    api_version = os.environ.get("AZURE_GENAI_API_VERSION", "2024-08-01-preview")
    return _cached_client(api_key, endpoint, api_version)

