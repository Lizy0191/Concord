"""Real PydanticAI Agent, tools, output validation and multimodal types.

The SDK's FunctionModel is the deliberate model-response boundary. These are
credential-free SDK integration tests, not live cloud/model-quality verification.
"""

import io

import pytest
from app.adapters.demo import demo_state
from app.domain.errors import PermissionDenied, ProviderError
from app.domain.models import Evidence, ProjectSnapshot, utcnow
from app.domain.runs import ReasoningProposal
from app.ports.providers import VisionResult
from PIL import Image

pytestmark = pytest.mark.integration


def sdk(monkeypatch):
    pytest.importorskip("pydantic_ai")
    from pydantic_ai import models

    # An accidental real provider request is a test failure, never a paid call.
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)


def context():
    state = demo_state()
    snapshot = ProjectSnapshot(
        project_id=state.project.id, version=state.version, sources=state.sources
    )
    evidence = Evidence(
        snapshot_id=snapshot.id,
        provider="original-sdk-fixture",
        source_id="drawing",
        source_revision="V17",
        observed_at=utcnow(),
        work_package_id="WP-200",
        fact="Drawing V17 differs from the current V16 work package. Contact person@example.com.",
    )
    return state, snapshot, evidence


def test_real_pydantic_ai_reasoning_executes_only_bound_read_tools(monkeypatch):
    sdk(monkeypatch)
    from app.adapters import reasoning_pydantic as module
    from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
    from pydantic_ai.models.function import FunctionModel

    state, snapshot, evidence = context()
    calls = []

    async def respond(messages, info):
        calls.append(messages)
        assert {tool.name for tool in info.function_tools} == {
            "query_evidence",
            "query_dependencies",
        }
        assert info.model_settings["timeout"] == 25
        returned = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart) and part.tool_name == "query_evidence"
        ]
        if not returned:
            return ModelResponse(
                parts=[ToolCallPart("query_evidence", {"evidence_id": evidence.id})]
            )
        assert returned[-1].content["id"] == evidence.id
        assert "person@example.com" not in str(returned[-1].content)
        output = ReasoningProposal(
            summary="Drawing change requires coordination",
            evidence_ids=(evidence.id,),
            limitations=("Synthetic SDK fixture; not a safety conclusion.",),
        )
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, output.model_dump(mode="json"))]
        )

    monkeypatch.setattr(module, "configured_model", lambda *args: FunctionModel(respond))
    engine = module.PydanticAIReasoningEngine("fixture:sdk")
    try:
        output = engine.interpret(state, snapshot, (evidence,))
        assert output.evidence_ids == (evidence.id,) and output.mode == "pydantic-ai"
        assert len(calls) == 2 and not engine.testing
    finally:
        engine.close()


def test_real_pydantic_ai_usage_limit_stops_endless_tool_requests(monkeypatch):
    sdk(monkeypatch)
    from app.adapters import reasoning_pydantic as module
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    state, snapshot, evidence = context()
    calls = []

    async def repeat(messages, info):
        calls.append(1)
        return ModelResponse(
            parts=[ToolCallPart("query_dependencies", {"work_package_id": "WP-200"})]
        )

    monkeypatch.setattr(module, "configured_model", lambda *args: FunctionModel(repeat))
    engine = module.PydanticAIReasoningEngine("fixture:sdk")
    try:
        with pytest.raises(ProviderError, match="no fallback"):
            engine.interpret(state, snapshot, (evidence,))
        assert len(calls) == 4  # The real SDK enforces UsageLimits(request_limit=4).
    finally:
        engine.close()


def test_real_pydantic_ai_vision_receives_sanitized_binary_content(monkeypatch):
    sdk(monkeypatch)
    from app.adapters import vision_pydantic as module
    from pydantic_ai import BinaryContent
    from pydantic_ai.messages import ModelResponse, ToolCallPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    content = io.BytesIO()
    exif = Image.Exif()
    exif[270] = "private metadata"
    Image.new("RGB", (32, 24), "white").save(content, "JPEG", exif=exif)
    calls = []

    async def respond(messages, info):
        calls.append(1)
        prompts = [
            part.content
            for message in messages
            for part in message.parts
            if isinstance(part, UserPromptPart)
        ]
        images = [
            item
            for prompt in prompts
            if not isinstance(prompt, str)
            for item in prompt
            if isinstance(item, BinaryContent)
        ]
        assert len(images) == 1 and images[0].media_type == "image/png"
        with Image.open(io.BytesIO(images[0].data)) as image:
            assert image.format == "PNG" and not image.getexif()
            assert "private metadata" not in str(image.info)
        assert not info.function_tools
        result = VisionResult(
            observations=("An original white fixture image.",),
            evidence_source_id="synthetic-photo",
            limitations=("Not a safety judgment.",),
            mode="fixture",
        )
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, result.model_dump(mode="json"))]
        )

    monkeypatch.setattr(module, "configured_model", lambda *args: FunctionModel(respond))
    engine = module.PydanticAIVisionAnalyzer("fixture:sdk", enabled=True)
    try:
        with pytest.raises(PermissionDenied):
            engine.analyze(content.getvalue(), "image/jpeg", "synthetic-photo", False)
        assert not calls
        result = engine.analyze(content.getvalue(), "image/jpeg", "synthetic-photo", True)
        assert (
            result.mode == "pydantic-ai-vision" and result.evidence_source_id == "synthetic-photo"
        )
        assert len(calls) == 1 and not engine.testing
    finally:
        engine.close()
