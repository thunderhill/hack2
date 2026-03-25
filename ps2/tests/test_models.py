import pytest
from pipeline_anomaly.models import AnomalyExplanation

BASE = dict(
    anomaly_type="build_failure",
    plain_english_summary="Build failed",
    root_cause="dependency conflict",
    affected_stage="install",
    severity="high",
    remediation_steps=["fix deps"],
    prevention_tips=["pin versions"],
)


def test_confidence_level_default_when_missing():
    """confidence_level defaults to 0.0 when not provided."""
    result = AnomalyExplanation(**BASE)
    assert result.confidence_level == 0.0


def test_confidence_level_stored_as_fraction():
    """A valid fraction 0.0-1.0 is stored unchanged."""
    result = AnomalyExplanation(**BASE, confidence_level=0.87)
    assert result.confidence_level == pytest.approx(0.87)


def test_confidence_level_normalises_percentage():
    """LLM returning 87 (percentage) is divided by 100 → 0.87."""
    result = AnomalyExplanation(**BASE, confidence_level=87)
    assert result.confidence_level == pytest.approx(0.87)


def test_confidence_level_clamped_above_one():
    """A value like 1.5 is clamped to 1.0."""
    result = AnomalyExplanation(**BASE, confidence_level=1.5)
    assert result.confidence_level == pytest.approx(1.0)


def test_confidence_level_clamped_below_zero():
    """A negative value is clamped to 0.0."""
    result = AnomalyExplanation(**BASE, confidence_level=-0.1)
    assert result.confidence_level == pytest.approx(0.0)
