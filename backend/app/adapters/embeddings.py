"""Explicit test embeddings and configured cloud embeddings behind one narrow Port."""

import hashlib
import math
import re
from typing import Any, cast
from urllib.parse import urlsplit

from app.adapters.model_egress import sanitize
from app.domain.errors import CapabilityUnavailable, DomainError, PermissionDenied, ProviderError
from app.domain.retrieval import EmbeddingDescriptor


def validate_vectors(values: list, count: int, dimensions: int) -> list[tuple[float, ...]]:
    if len(values) != count:
        raise ProviderError("Embedding provider returned the wrong vector count")
    output = []
    for value in values:
        if len(value) != dimensions:
            raise ProviderError("Embedding dimensions do not match configured model metadata")
        try:
            vector = tuple(float(item) for item in value)
        except (TypeError, ValueError) as exc:
            raise ProviderError("Embedding contains a nonnumeric value") from exc
        if not all(math.isfinite(item) for item in vector) or sum(x * x for x in vector) == 0:
            raise ProviderError("Embedding is non-finite or zero; cosine similarity is undefined")
        output.append(vector)
    return output


class DeterministicTestEmbeddings:
    """Hashing fixture for reproducible database tests; NOT a semantic language model."""

    def __init__(self, dimensions: int = 64, version: str = "fixture-v1"):
        self.descriptor = EmbeddingDescriptor(
            provider="deterministic-test",
            model="token-hash",
            version=version,
            dimensions=dimensions,
            test_only=True,
        )

    def embed(self, texts: list[str], consent: bool = False) -> list[tuple[float, ...]]:
        if not 1 <= len(texts) <= 64:
            raise DomainError("Embedding batch must contain 1 to 64 selected chunks")
        vectors = []
        for text in texts:
            vector = [0.0] * self.descriptor.dimensions
            for token in re.findall(r"\w+", text.casefold())[:1000] or ["empty"]:
                digest = hashlib.sha256(token.encode()).digest()
                vector[int.from_bytes(digest[:4], "big") % len(vector)] += 1.0
            norm = math.sqrt(sum(x * x for x in vector))
            vectors.append(tuple(x / norm for x in vector))
        return vectors


class OpenAICompatibleEmbeddings:
    def __init__(
        self,
        model: str,
        version: str,
        dimensions: int,
        api_key: str = "",
        base_url: str = "",
        *,
        cloud_egress_enabled: bool = False,
        client=None,
    ):
        self.descriptor = EmbeddingDescriptor(
            provider="openai-compatible",
            model=model,
            version=version,
            dimensions=dimensions,
            test_only=False,
        )
        self.api_key, self.base_url = api_key, base_url
        self.cloud_egress_enabled, self.client = cloud_egress_enabled, client

    def _client(self):
        if self.client is None:
            if not self.api_key or not self.descriptor.model or not self.descriptor.version:
                raise CapabilityUnavailable("Embedding model, version and credential are required")
            if self.base_url:
                url = urlsplit(self.base_url)
                if url.scheme != "https" and not (
                    url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
                ):
                    raise CapabilityUnavailable(
                        "Embedding endpoint requires HTTPS or explicit loopback"
                    )
            try:
                from httpx import Timeout
                from openai import OpenAI
            except ImportError as exc:
                raise CapabilityUnavailable(
                    "Install the models extra for cloud embeddings"
                ) from exc
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=cast(Any, Timeout(20, connect=5)),
                max_retries=1,
                base_url=self.base_url or None,
            )
        return self.client

    def embed(self, texts: list[str], consent: bool = False) -> list[tuple[float, ...]]:
        if not self.cloud_egress_enabled or not consent:
            raise PermissionDenied(
                "Selected text cloud egress requires configuration and explicit consent"
            )
        if not 1 <= len(texts) <= 64:
            raise DomainError("Embedding batch must contain 1 to 64 selected chunks")
        selected = [sanitize(text, 2400) for text in texts]
        if any(not text.strip() for text in selected):
            raise DomainError("Empty text cannot be embedded")
        try:
            result = self._client().embeddings.create(
                model=self.descriptor.model, input=selected, encoding_format="float"
            )
        except (DomainError, CapabilityUnavailable):
            raise
        except Exception as exc:
            raise ProviderError(
                "Configured embedding provider failed; no derived rows were committed"
            ) from exc
        data = sorted(result.data, key=lambda item: item.index)
        if [item.index for item in data] != list(range(len(selected))):
            raise ProviderError("Embedding result indices do not match the input batch")
        return validate_vectors(
            [item.embedding for item in data], len(selected), self.descriptor.dimensions
        )

    def close(self):
        if self.client is not None:
            close = getattr(self.client, "close", None)
            if close:
                close()
