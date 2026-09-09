"""Publish derived vectors in the same transaction as the durable job result."""

import hashlib

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.adapters.embeddings import validate_vectors
from app.adapters.persistence.tables import ChunkRow, DocumentRow
from app.adapters.retrieval_pgvector import embedding_table
from app.domain.errors import CapabilityUnavailable, ProviderError
from app.domain.models import utcnow
from app.domain.retrieval import PreparedEmbeddingIndex


def publish_embeddings(session: Session, prepared: PreparedEmbeddingIndex) -> dict:
    if session.get_bind().dialect.name != "postgresql":
        raise CapabilityUnavailable("Vector publication requires PostgreSQL")
    table = embedding_table()
    document = session.scalar(
        select(DocumentRow)
        .where(
            DocumentRow.id == prepared.document_id, DocumentRow.project_id == prepared.project_id
        )
        .with_for_update()
    )
    if document is None or document.content_hash != prepared.source_hash:
        raise ProviderError(
            "Source revision changed while generating embeddings; recompute required"
        )
    descriptor = prepared.descriptor
    validate_vectors(
        [c.vector for c in prepared.chunks], len(prepared.chunks), descriptor.dimensions
    )
    identities = {c.chunk_id for c in prepared.chunks}
    if len(identities) != len(prepared.chunks):
        raise ProviderError("Prepared embedding identities are not unique")
    chunks = {
        c.id: c
        for c in session.scalars(
            select(ChunkRow)
            .where(
                ChunkRow.id.in_(identities),
                ChunkRow.document_id == document.id,
                ChunkRow.project_id == prepared.project_id,
            )
            .with_for_update()
        )
    }
    if set(chunks) != identities:
        raise ProviderError("Selected chunks changed while generating embeddings")
    for chunk in prepared.chunks:
        source = chunks[chunk.chunk_id]
        if (
            source.payload.get("source_hash") != prepared.source_hash
            or hashlib.sha256(source.text.encode()).hexdigest() != chunk.text_hash
        ):
            raise ProviderError("Selected chunk content changed while generating embeddings")
        session.execute(
            delete(table).where(
                table.c.chunk_id == chunk.chunk_id,
                table.c.model == descriptor.model,
                table.c.model_version != descriptor.version,
            )
        )
        row = dict(
            chunk_id=chunk.chunk_id,
            model=descriptor.model,
            model_version=descriptor.version,
            project_id=prepared.project_id,
            document_id=prepared.document_id,
            source_hash=prepared.source_hash,
            dimensions=descriptor.dimensions,
            embedding=list(chunk.vector),
            created_at=utcnow().isoformat(),
        )
        statement = insert(table).values(**row)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=["chunk_id", "model", "model_version"],
                set_={
                    key: value
                    for key, value in row.items()
                    if key not in {"chunk_id", "model", "model_version"}
                },
            )
        )
    return prepared.result()
