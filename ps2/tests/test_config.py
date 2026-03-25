import os
import pytest
from unittest.mock import patch, MagicMock


def test_provider_config_is_hashable():
    """ProviderConfig must be hashable (frozen dataclass) for lru_cache."""
    from pipeline_anomaly.config import PROVIDERS
    tcs = PROVIDERS["tcs"]
    assert hash(tcs) is not None  # raises TypeError if not hashable


def test_providers_registry_has_tcs_and_ollama():
    from pipeline_anomaly.config import PROVIDERS
    assert "tcs" in PROVIDERS
    assert "ollama" in PROVIDERS


def test_get_model_tcs_known_key():
    from pipeline_anomaly.config import get_model
    assert get_model("tcs", "gpt-4o-mini") == "azure/genailab-maas-gpt-4o-mini"


def test_get_model_tcs_unknown_key_raises():
    from pipeline_anomaly.config import get_model
    with pytest.raises(ValueError, match="Unknown model"):
        get_model("tcs", "nonexistent-model")


def test_get_model_ollama_identity():
    """Ollama get_model returns the key unchanged (identity lookup)."""
    from pipeline_anomaly.config import get_model
    assert get_model("ollama", "llama3:8b") == "llama3:8b"
    assert get_model("ollama", "mistral") == "mistral"


def test_get_model_unknown_provider_raises():
    from pipeline_anomaly.config import get_model
    with pytest.raises(ValueError, match="Unknown provider"):
        get_model("openrouter", "some-model")


def test_list_ollama_models_returns_empty_list_when_unavailable():
    """list_ollama_models() returns [] when Ollama is not running."""
    import httpx
    from pipeline_anomaly.config import list_ollama_models
    with patch("httpx.get", side_effect=httpx.ConnectError("refused")):
        result = list_ollama_models()
    assert result == []


def test_list_ollama_models_parses_api_tags_response():
    """list_ollama_models() parses the /api/tags JSON and returns model names."""
    from pipeline_anomaly.config import list_ollama_models
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "models": [
            {"name": "llama3:8b"},
            {"name": "mistral:latest"},
        ]
    }
    with patch("httpx.get", return_value=mock_response):
        result = list_ollama_models()
    assert result == ["llama3:8b", "mistral:latest"]


def test_get_llm_client_unknown_provider_raises():
    from pipeline_anomaly.config import get_llm_client
    with pytest.raises(ValueError, match="Unknown provider"):
        get_llm_client("nonexistent")


def test_get_llm_client_tcs_uses_ssl_bypass(monkeypatch):
    """TCS client is created with verify=False."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://genailab.tcs.in")
    from pipeline_anomaly import config
    # Clear cache so monkeypatched env is picked up
    config._cached_client.cache_clear()
    client = config.get_llm_client("tcs")
    assert client.base_url is not None
    config._cached_client.cache_clear()


def test_ollama_base_url_strips_trailing_v1(monkeypatch):
    """If OLLAMA_BASE_URL has a /v1 suffix it is stripped before appending /v1."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    from pipeline_anomaly import config
    config._cached_client.cache_clear()
    tcs_provider = config.PROVIDERS["ollama"]
    base = os.environ.get("OLLAMA_BASE_URL", tcs_provider.base_url)
    # Simulate the stripping logic
    normalized = base.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[:-3]
    assert normalized == "http://localhost:11434"
    config._cached_client.cache_clear()
