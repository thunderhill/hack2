import os
import httpx
from dataclasses import dataclass
from functools import lru_cache
from openai import OpenAI


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key_env: str          # env var to read key from
    ssl_verify: bool
    model_map: tuple[tuple[str, str], ...]  # (display_name, deployment_id); empty for Ollama
    default_model: str

    @property
    def model_map_dict(self) -> dict[str, str]:
        return dict(self.model_map)


_DEFAULT_TCS_URL = "https://genailab.tcs.in"
_DEFAULT_OLLAMA_URL = "http://localhost:11434"

PROVIDERS: dict[str, ProviderConfig] = {
    "tcs": ProviderConfig(
        base_url=_DEFAULT_TCS_URL,
        api_key_env="OPENAI_API_KEY",
        ssl_verify=False,
        model_map=(
            ("gpt-4o", "azure/genailab-maas-gpt-4o"),
            ("gpt-4o-mini", "azure/genailab-maas-gpt-4o-mini"),
            ("gpt-35-turbo", "genailab-maas-gpt-35-turbo"),
        ),
        default_model="gpt-4o-mini",
    ),
    "ollama": ProviderConfig(
        base_url=_DEFAULT_OLLAMA_URL,
        api_key_env="OLLAMA_API_KEY",
        ssl_verify=True,
        model_map=(),          # populated dynamically via list_ollama_models()
        default_model="",
    ),
}

# Convenience alias — backward compat for code that imports MODEL_OPTIONS
MODEL_OPTIONS: list[str] = list(PROVIDERS["tcs"].model_map_dict.keys())


def get_model(provider: str, model_key: str) -> str:
    """Return the deployment ID for a given provider + display name.

    For Ollama, the model_key IS the deployment ID (identity lookup).
    For TCS, looks up the static model_map and raises ValueError for unknown keys.
    """
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. Options: {list(PROVIDERS)}")
    if provider == "ollama":
        return model_key
    model_map = PROVIDERS[provider].model_map_dict
    if model_key not in model_map:
        raise ValueError(
            f"Unknown model {model_key!r} for provider {provider!r}. "
            f"Options: {list(model_map)}"
        )
    return model_map[model_key]


def list_ollama_models() -> list[str]:
    """Return model names available in the local Ollama instance.

    Calls GET {OLLAMA_BASE_URL}/api/tags. Returns [] on any error (Ollama not
    running, network issue, etc.) — never raises.
    """
    base_url = os.environ.get("OLLAMA_BASE_URL", _DEFAULT_OLLAMA_URL).rstrip("/")
    try:
        response = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        data = response.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


@lru_cache(maxsize=None)
def _cached_client(provider: str, api_key: str, base_url: str) -> OpenAI:
    config = PROVIDERS[provider]
    return OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/") + "/v1",
        http_client=httpx.Client(verify=config.ssl_verify),
    )


def get_llm_client(provider: str = "tcs") -> OpenAI:
    """Return a cached OpenAI-compatible client for the given provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider {provider!r}. Options: {list(PROVIDERS)}")
    config = PROVIDERS[provider]

    if provider == "tcs":
        api_key = os.environ.get(config.api_key_env, "")
        if not api_key:
            raise EnvironmentError(f"{config.api_key_env} is not set in .env")
    else:
        api_key = os.environ.get(config.api_key_env) or "ollama"

    # Resolve base URL from env (allows override) and strip accidental /v1 suffix
    if provider == "tcs":
        raw_url = os.environ.get("OPENAI_BASE_URL", config.base_url)
    else:
        raw_url = os.environ.get("OLLAMA_BASE_URL", config.base_url)

    base_url = raw_url.rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]

    return _cached_client(provider, api_key, base_url)
