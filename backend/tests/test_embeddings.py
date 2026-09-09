import json
import math

import httpx
import pytest
from app.adapters.embeddings import (
    DeterministicTestEmbeddings,
    OpenAICompatibleEmbeddings,
    validate_vectors,
)
from app.adapters.retrieval_pgvector import PgVectorSearch
from app.domain.errors import CapabilityUnavailable, PermissionDenied, ProviderError
from app.domain.retrieval import SemanticQuery


def test_fixture_embeddings_are_reproducible_normalized_and_labeled():
    first = DeterministicTestEmbeddings(64)
    values = first.embed(["duct revision", "inspection accepted", "duct revision"])
    assert values[0] == values[2] == DeterministicTestEmbeddings(64).embed(["duct revision"])[0]
    assert values[0] != values[1]
    assert first.descriptor.test_only is True
    assert all(math.isclose(sum(x * x for x in vector), 1) for vector in values)


@pytest.mark.parametrize(
    "vectors,count,dimensions",
    [
        ([], 1, 2),
        ([[1]], 1, 2),
        ([[0, 0]], 1, 2),
        ([[float("nan"), 1]], 1, 2),
        ([[float("inf"), 1]], 1, 2),
        ([["bad", 1]], 1, 2),
    ],
)
def test_invalid_embeddings_are_rejected(vectors, count, dimensions):
    with pytest.raises(ProviderError):
        validate_vectors(vectors, count, dimensions)


def test_cloud_embedding_requires_both_configuration_and_per_request_consent():
    adapter = OpenAICompatibleEmbeddings("test-model", "v1", 2, client=object())
    with pytest.raises(PermissionDenied):
        adapter.embed(["document"], consent=True)
    adapter.cloud_egress_enabled = True
    with pytest.raises(PermissionDenied):
        adapter.embed(["document"], consent=False)


def test_actual_openai_sdk_embedding_http_contract_and_minimization():
    openai = pytest.importorskip("openai")
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": "test-model",
                "data": [{"object": "embedding", "embedding": [0.2, 0.8], "index": 0}],
                "usage": {"prompt_tokens": 2, "total_tokens": 2},
            },
        )

    client = openai.OpenAI(
        api_key="test-not-a-secret",
        base_url="http://test.invalid/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    adapter = OpenAICompatibleEmbeddings(
        "test-model", "v1", 2, cloud_egress_enabled=True, client=client
    )
    try:
        assert adapter.embed(
            ["Contact worker@example.org +1 202 555 0123 about the duct"], consent=True
        ) == [(0.2, 0.8)]
        assert captured[0]["model"] == "test-model"
        assert "worker@example.org" not in captured[0]["input"][0]
        assert "202 555 0123" not in captured[0]["input"][0]
    finally:
        adapter.close()


def test_vector_disabled_database_fails_before_any_embedding_call(services):
    class NeverCalled:
        def embed(self, *_args, **_kwargs):
            raise AssertionError("No cloud call is allowed for unsupported database")

    vector = PgVectorSearch(services.factory.engine, NeverCalled())
    assert vector.health()[0] is False
    with pytest.raises(CapabilityUnavailable):
        vector.search("harbor-east", SemanticQuery(query="duct"))
