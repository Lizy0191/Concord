"""Derived retrieval data is revision/model-bound and never authoritative project state."""

from pydantic import Field

from app.domain.models import Model


class EmbeddingDescriptor(Model):
    provider: str
    model: str
    version: str
    dimensions: int = Field(ge=1, le=4096)
    test_only: bool = False


class SemanticQuery(Model):
    query: str = Field(min_length=1, max_length=2000)
    document_id: str | None = None
    source_hash: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    consent: bool = False


class SemanticMatch(Model):
    document_id: str
    chunk_id: str
    text: str
    page: int | None
    source_hash: str
    score: float
    model: str
    model_version: str
    dimensions: int
    test_only: bool


class EmbeddedChunk(Model):
    chunk_id: str
    text_hash: str
    vector: tuple[float, ...] = Field(min_length=1, max_length=4096)


class PreparedEmbeddingIndex(Model):
    """Validated model output; private until the job's completion transaction commits."""

    project_id: str
    document_id: str
    source_hash: str
    descriptor: EmbeddingDescriptor
    chunks: tuple[EmbeddedChunk, ...] = Field(min_length=1, max_length=128)

    def result(self) -> dict:
        return {
            "document_id": self.document_id,
            "source_hash": self.source_hash,
            "indexed_chunks": len(self.chunks),
            "embedding": self.descriptor.model_dump(mode="json"),
            "derived_only": True,
        }
