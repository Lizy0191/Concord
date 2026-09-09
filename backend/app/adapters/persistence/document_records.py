"""Publish prepared document facts in the caller's existing database transaction."""

from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.adapters.persistence.tables import ChunkRow, DocumentRow
from app.domain.errors import Conflict
from app.ports.providers import DocumentChunk, DocumentMetadata, PreparedDocument


def prepared_record(session: Session, document_id: str) -> PreparedDocument | None:
    row = session.get(DocumentRow, document_id)
    if row is None:
        return None
    metadata = DocumentMetadata(
        id=row.id,
        project_id=row.project_id,
        filename=row.filename,
        content_hash=row.content_hash,
        parser=row.parser,
        created_at=datetime.fromisoformat(row.created_at),
    )
    chunks = tuple(
        DocumentChunk.model_validate(chunk.payload)
        for chunk in session.scalars(select(ChunkRow).where(ChunkRow.document_id == document_id))
    )
    return PreparedDocument(metadata=metadata, object_key=row.object_key, chunks=chunks)


def publish_document(session: Session, prepared: PreparedDocument) -> PreparedDocument:
    metadata = prepared.metadata
    existing = prepared_record(session, metadata.id)
    if existing is not None:
        if (
            existing.metadata.content_hash != metadata.content_hash
            or existing.metadata.project_id != metadata.project_id
        ):
            raise Conflict("Document import identifier belongs to different content")
        return existing
    session.add(
        DocumentRow(
            id=metadata.id,
            project_id=metadata.project_id,
            filename=metadata.filename,
            object_key=prepared.object_key,
            content_hash=metadata.content_hash,
            parser=metadata.parser,
            created_at=metadata.created_at.isoformat(),
        )
    )
    session.flush()
    for chunk in prepared.chunks:
        session.add(
            ChunkRow(
                id=chunk.id,
                project_id=metadata.project_id,
                document_id=metadata.id,
                text=chunk.text,
                payload=chunk.model_dump(mode="json"),
            )
        )
        if session.get_bind().dialect.name == "sqlite":
            session.execute(
                text(
                    "INSERT INTO document_fts(chunk_id, project_id, text) VALUES "
                    "(:id, :project, :text)"
                ),
                {"id": chunk.id, "project": metadata.project_id, "text": chunk.text},
            )
    session.flush()
    return prepared
