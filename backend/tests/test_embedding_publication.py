"""Preparation contracts run on SQLite; actual pgvector writes belong to service tests."""

import hashlib
from types import SimpleNamespace

import pytest
from app.adapters.embeddings import DeterministicTestEmbeddings
from app.adapters.persistence.repository import SQLCoordinationRepository
from app.adapters.retrieval_pgvector import PgVectorSearch
from app.domain.errors import ProviderError
from app.domain.jobs import EmbeddingIndexRequest
from sqlalchemy import text


def prepared_index(services, monkeypatch):
    doc = services.documents.import_file("harbor-east", "embedding.md", b"V17 duct coordination")
    search = PgVectorSearch(services.factory.engine, DeterministicTestEmbeddings())
    # Only the availability preflight is bypassed: ORM reads and deterministic
    # provider preparation are real. This never asserts pgvector ran on SQLite.
    monkeypatch.setattr(search, "_ready", lambda: None)
    return search.prepare_index("harbor-east", doc["id"])


def test_preparation_reads_real_source_without_publishing_vectors(services, monkeypatch):
    prepared = prepared_index(services, monkeypatch)
    assert prepared.project_id == "harbor-east"
    assert prepared.source_hash == hashlib.sha256(b"V17 duct coordination").hexdigest()
    assert len(prepared.chunks) == prepared.result()["indexed_chunks"] == 1
    assert prepared.chunks[0].text_hash == prepared.source_hash
    assert prepared.descriptor.test_only
    assert len(prepared.chunks[0].vector) == prepared.descriptor.dimensions


def test_cancelled_embedding_job_never_calls_publication(services, admin, monkeypatch):
    prepared = prepared_index(services, monkeypatch)
    services.jobs.enabled = services.jobs.enabled | {"embedding_index"}
    run = services.jobs.enqueue(
        "harbor-east", EmbeddingIndexRequest(document_id=prepared.document_id), admin
    )
    called = []

    def prepare(*args):
        services.coordination.cancel(run.id, admin)
        return prepared

    services.jobs.semantic = SimpleNamespace(prepare_index=prepare)
    monkeypatch.setattr(
        SQLCoordinationRepository, "publish_embeddings", lambda *args: called.append("published")
    )
    assert services.workflow.begin(run.id) == "CANCELLED"
    assert called == []
    with services.factory.open() as repo:
        assert repo.job(run.id).result is None


def test_embedding_publication_uses_the_job_transaction_and_rolls_back(
    services, admin, monkeypatch
):
    prepared = prepared_index(services, monkeypatch)
    services.jobs.enabled = services.jobs.enabled | {"embedding_index"}
    services.jobs.semantic = SimpleNamespace(prepare_index=lambda *args: prepared)
    run = services.jobs.enqueue(
        "harbor-east", EmbeddingIndexRequest(document_id=prepared.document_id), admin
    )
    with services.factory.engine.begin() as connection:
        connection.execute(text("CREATE TABLE test_vector_publication (chunk_id TEXT PRIMARY KEY)"))

    def publish(repo, value):
        for chunk in value.chunks:
            repo.session.execute(
                text("INSERT INTO test_vector_publication VALUES (:id)"), {"id": chunk.chunk_id}
            )
        return value.result()

    save_job = SQLCoordinationRepository.save_job

    def fail_completion(repo, job):
        if job.id == run.id and job.result is not None:
            raise ProviderError("Completion transaction interrupted")
        return save_job(repo, job)

    monkeypatch.setattr(SQLCoordinationRepository, "publish_embeddings", publish)
    monkeypatch.setattr(SQLCoordinationRepository, "save_job", fail_completion)
    with pytest.raises(ProviderError, match="interrupted"):
        services.workflow.begin(run.id)
    with services.factory.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM test_vector_publication")).scalar() == 0
        )
    with services.factory.open() as repo:
        assert repo.job(run.id).result is None
    monkeypatch.setattr(SQLCoordinationRepository, "save_job", save_job)
    assert services.workflow.begin(run.id) == "COMPLETED"
    with services.factory.engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM test_vector_publication")).scalar() == 1
        )
