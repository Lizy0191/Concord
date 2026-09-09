"""Credential-free provider configuration and deterministic reasoning contracts."""

import pytest
from app.adapters.demo import demo_state
from app.adapters.model_client import configured_model
from app.adapters.reasoning_offline import OfflineReasoningEngine
from app.domain.errors import CapabilityUnavailable
from app.domain.models import Evidence, ProjectSnapshot, utcnow
from app.settings import Settings
from pydantic import ValidationError


def test_offline_settings_and_reasoning_need_no_model_credentials():
    settings = Settings(reasoning="offline", model_provider=None, model_api_key="")
    state = demo_state()
    snapshot = ProjectSnapshot(
        project_id=state.project.id, version=state.version, sources=state.sources
    )
    evidence = (
        Evidence(
            snapshot_id=snapshot.id,
            provider="fixture",
            source_id="drawing",
            source_revision="V17",
            observed_at=utcnow(),
            work_package_id="WP-200",
            fact="Synthetic drawing revision.",
        ),
    )

    proposal = OfflineReasoningEngine().interpret(state, snapshot, evidence)

    assert settings.reasoning == "offline"
    assert proposal.mode == "offline" and proposal.evidence_ids == (evidence[0].id,)


def test_legacy_native_identifier_can_still_use_sdk_environment_credentials():
    settings = Settings(
        reasoning="pydantic-ai", reasoning_model="anthropic:claude-3-5-haiku-latest"
    )

    assert settings.model_provider is None
    assert configured_model(settings.reasoning_model, "") == settings.reasoning_model


@pytest.mark.parametrize(
    "provider, model",
    [
        ("openai", "gpt-4o-mini"),
        ("anthropic", "claude-3-5-haiku-latest"),
        ("google", "gemini-2.0-flash"),
    ],
)
def test_native_provider_configuration_uses_no_live_request(monkeypatch, provider, model):
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import models

    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)

    configured = configured_model(model, "test-key", provider=provider)

    assert configured.model_name == model


def test_openai_compatible_endpoint_is_explicit_and_credentialed(monkeypatch):
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import models

    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)

    configured = configured_model(
        "private-chat", "test-key", "http://localhost:11434/v1", provider="openai-compatible"
    )

    assert configured.model_name == "private-chat"
    assert str(configured.provider.base_url) == "http://localhost:11434/v1/"


def test_model_configuration_rejects_missing_or_invalid_provider_settings():
    with pytest.raises(ValidationError, match="CCA_MODEL_API_KEY"):
        Settings(reasoning="pydantic-ai", model_provider="openai", reasoning_model="gpt-4o-mini")
    with pytest.raises(ValidationError):
        Settings.model_validate({"model_provider": "unsupported"})
    with pytest.raises(ValidationError, match="CCA_MODEL_BASE_URL"):
        Settings(
            reasoning="pydantic-ai",
            model_provider="anthropic",
            reasoning_model="claude-test",
            model_api_key="test-key",
            model_base_url="https://gateway.example",
        )
    with pytest.raises(CapabilityUnavailable, match="API_KEY"):
        configured_model("private-chat", "", provider="openai-compatible")
