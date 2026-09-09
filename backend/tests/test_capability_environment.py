"""Environment inspection must not turn availability into a live health claim."""

import importlib.metadata

import pytest
from app.adapters import capability_environment


@pytest.mark.parametrize(
    ("available", "enabled", "credential", "status"),
    [
        (False, True, True, "unavailable_dependency"),
        (True, True, False, "unavailable_credential"),
        (True, False, False, "available_disabled"),
        (True, True, None, "enabled"),
        (True, True, True, "enabled"),
    ],
)
def test_optional_capability_keeps_availability_distinct_from_health(
    monkeypatch, available, enabled, credential, status
):
    monkeypatch.setattr(capability_environment, "dependency", lambda module: available)
    monkeypatch.setattr(importlib.metadata, "version", lambda distribution: "test-version")
    report = capability_environment.optional(
        "test capability", "test implementation", "test_module", enabled, credential
    )
    assert report.status == status
    assert report.dependency_available is available
    assert report.enabled is enabled
    assert report.credential_present is credential
    assert report.service_reachable is None
    assert report.version == "test-version"


def test_unknown_model_credential_remains_unknown(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert capability_environment.model_credential("", "") is False
    assert capability_environment.model_credential("openai:test", "key") is True
    assert capability_environment.model_credential("anthropic:test", "") is False
    assert capability_environment.model_credential("workload-identity:test", "") is None
