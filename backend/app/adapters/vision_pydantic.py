import hashlib

from app.adapters.model_client import bounded_call, configured_model
from app.adapters.model_runner import ModelCallRunner
from app.domain.errors import CapabilityUnavailable, DomainError, PermissionDenied, ProviderError
from app.ports.providers import VisionResult


class PydanticAIVisionAnalyzer:
    def __init__(
        self,
        model_id: str,
        api_key: str = "",
        base_url: str = "",
        *,
        provider: str | None = None,
        enabled: bool = False,
        agent=None,
    ):
        self.model_id, self.enabled = model_id, enabled
        self.runner = ModelCallRunner()
        self.agent, self.testing = agent, agent is not None
        self.api_key, self.base_url, self.provider = api_key, base_url, provider

    def analyze(
        self, content: bytes, media_type: str, source_id: str, consent: bool
    ) -> VisionResult:
        if not self.enabled or not self.model_id:
            raise CapabilityUnavailable("Vision is disabled or has no configured vision_model")
        if not consent:
            raise PermissionDenied("Explicit consent is required before image cloud egress")
        if (
            media_type not in {"image/png", "image/jpeg", "image/webp"}
            or not 0 < len(content) <= 5 * 1024 * 1024
        ):
            raise DomainError("Vision accepts only bounded PNG/JPEG/WebP images")
        # Re-encode locally to remove EXIF/GPS metadata; image content remains an explicit
        # disclosure.
        from app.adapters.vision_sanitize import clean_image

        cleaned = clean_image(content)
        if self.agent is None:
            try:
                from pydantic_ai import Agent
            except ImportError as exc:
                raise CapabilityUnavailable("Install the models extra for vision") from exc
            self.agent = Agent(
                configured_model(self.model_id, self.api_key, self.base_url, self.provider),
                output_type=VisionResult,
                instructions=(
                    "Describe visible construction context and uncertainty only. "
                    "Do not identify people, infer biometrics, decide final "
                    "safety, or propose commands. Preserve the supplied evidence "
                    "source identifier."
                ),
            )
        try:
            from pydantic_ai import BinaryContent

            image = BinaryContent(data=cleaned, media_type="image/png")
        except ImportError as exc:
            if not self.testing:
                raise CapabilityUnavailable("PydanticAI multimodal input is unavailable") from exc
            image = {"data": cleaned, "media_type": "image/png"}
        prompt = [
            f"Evidence source: {source_id}. "
            f"Source SHA-256: {hashlib.sha256(content).hexdigest()}. "
            "Return cautious observations only.",
            image,
        ]
        result = self.runner.call(
            bounded_call(
                self.agent,
                prompt,
                role="vision_model",
                model_id=self.model_id,
                testing=self.testing,
            )
        )
        output = VisionResult.model_validate(result)
        if output.evidence_source_id != source_id:
            raise ProviderError("Vision returned an unrelated source identifier")
        return output.model_copy(update={"mode": "pydantic-ai-vision"})

    def close(self) -> None:
        self.runner.close()
