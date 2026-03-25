import json
import pytest
from unittest.mock import patch, MagicMock


MOCK_RESPONSE = {
    "anomaly_type": "dependency_conflict",
    "plain_english_summary": "npm cannot resolve peer deps",
    "root_cause": "react@18 conflicts with react-router-dom@5",
    "affected_stage": "install-dependencies",
    "severity": "high",
    "remediation_steps": ["upgrade react-router-dom"],
    "prevention_tips": ["pin peer deps"],
    "confidence_level": 0.9,
}


def _mock_openai_response(content: str):
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


def test_explain_anomaly_accepts_provider_param():
    """explain_anomaly accepts a provider kwarg without raising."""
    from pipeline_anomaly.agent import explain_anomaly
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps(MOCK_RESPONSE)
    )
    with patch("pipeline_anomaly.agent.get_llm_client", return_value=mock_client):
        result = explain_anomaly("some log", model_key="gpt-4o-mini", provider="tcs")
    assert result.anomaly_type == "dependency_conflict"
    assert result.confidence_level == pytest.approx(0.9)


def test_explain_anomaly_passes_provider_to_client():
    """get_llm_client is called with the correct provider."""
    from pipeline_anomaly.agent import explain_anomaly
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps(MOCK_RESPONSE)
    )
    with patch("pipeline_anomaly.agent.get_llm_client", return_value=mock_client) as mock_get:
        explain_anomaly("log", model_key="llama3:8b", provider="ollama")
    mock_get.assert_called_once_with("ollama")


def test_explain_anomaly_default_provider_is_tcs():
    """When provider is omitted, defaults to 'tcs'."""
    from pipeline_anomaly.agent import explain_anomaly
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _mock_openai_response(
        json.dumps(MOCK_RESPONSE)
    )
    with patch("pipeline_anomaly.agent.get_llm_client", return_value=mock_client) as mock_get:
        explain_anomaly("log", model_key="gpt-4o-mini")
    mock_get.assert_called_once_with("tcs")
