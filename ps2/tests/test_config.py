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
    import httpx
    from pipeline_anomaly import config
    config._cached_client.cache_clear()
    captured: list[tuple] = []
    real_cached = config._cached_client.__wrapped__

    def spy_cached(provider, api_key, base_url):
        cfg = config.PROVIDERS[provider]
        captured.append((provider, cfg.ssl_verify))
        return real_cached(provider, api_key, base_url)

    with patch.object(config, "_cached_client", side_effect=spy_cached):
        config.get_llm_client("tcs")
    assert captured == [("tcs", False)]
    config._cached_client.cache_clear()


def test_ollama_base_url_strips_trailing_v1(monkeypatch):
    """If OLLAMA_BASE_URL has a /v1 suffix it is stripped before appending /v1."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    from pipeline_anomaly import config
    config._cached_client.cache_clear()
    captured_base_urls: list[str] = []

    def spy_cached(provider, api_key, base_url):
        captured_base_urls.append(base_url)
        return MagicMock()

    with patch.object(config, "_cached_client", side_effect=spy_cached):
        config.get_llm_client("ollama")
    assert len(captured_base_urls) == 1
    # /v1 suffix must be stripped before _cached_client appends its own /v1
    assert captured_base_urls[0] == "http://localhost:11434"
    assert captured_base_urls[0].endswith("/v1/v1") is False
    config._cached_client.cache_clear()
