"""PostgreSQL exact cosine retrieval with immutable source/model provenance.

An optional independent Alembic branch owns the derived table. No extension or
vector table is required by SQLite or by the ordinary PostgreSQL profile.
"""

import hashlib
import math
from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, String, Table, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.adapters.embeddings import validate_vectors
from app.adapters.persistence.tables import ChunkRow, DocumentRow
from app.domain.errors import CapabilityUnavailable, DomainError, NotFound, ProviderError
from app.domain.retrieval import EmbeddedChunk, PreparedEmbeddingIndex, SemanticMatch, SemanticQuery
from app.ports.providers import EmbeddingProvider


def embedding_table():
    try:
        from pgvector.sqlalchemy import VECTOR
    except ImportError as exc:
        raise CapabilityUnavailable("Install the server extra for pgvector") from exc
    return Table(
        "document_embeddings",
        MetaData(),
        Column("chunk_id", String(100), primary_key=True),
        Column("model", String(250), primary_key=True),
        Column("model_version", String(250), primary_key=True),
        Column("project_id", String(100), nullable=False),
        Column("document_id", String(100), nullable=False),
        Column("source_hash", String(64), nullable=False),
        Column("dimensions", Integer, nullable=False),
        Column("embedding", VECTOR(), nullable=False),
        Column("created_at", String(40), nullable=False),
    )


def migrate_vectors(engine) -> None:
    if engine.dialect.name != "postgresql":
        raise CapabilityUnavailable("The vector profile requires PostgreSQL")
    from alembic import command
    from alembic.config import Config

    config = Config()
    source = Path(__file__).resolve().parents[2] / "vector_migrations"
    bundled = Path(__file__).resolve().parents[1] / "vector_migrations"
    config.set_main_option("script_location", str(source if source.is_dir() else bundled))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


class PgVectorSearch:
    def __init__(self, engine, embeddings: EmbeddingProvider):
        self.engine, self.embeddings = engine, embeddings

    def health(self) -> tuple[bool, str]:
        if self.engine.dialect.name != "postgresql":
            return False, "PostgreSQL is required for pgvector"
        try:
            embedding_table()
            with self.engine.connect() as connection:
                connection.execute(text("SET LOCAL statement_timeout = '2000ms'"))
                version = connection.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector' ")
                ).scalar()
                table = connection.execute(
                    text("SELECT to_regclass('public.document_embeddings')")
                ).scalar()
                return bool(version and table), (
                    f"pgvector {version}; derived table available"
                    if version and table
                    else "Run cca init-vector to apply the optional vector migration"
                )
        except (SQLAlchemyError, CapabilityUnavailable):
            return (
                False,
                "Vector dependency/schema/service unavailable; relational retrieval remains usable",
            )

    def _ready(self):
        if self.engine.dialect.name != "postgresql":
            raise CapabilityUnavailable(
                "Vector retrieval requires PostgreSQL; local FTS remains available"
            )
        healthy, reason = self.health()
        if not healthy:
            raise CapabilityUnavailable(reason)
        return embedding_table()

    def index_document(
        self,
        project_id: str,
        document_id: str,
        chunk_ids: tuple[str, ...] = (),
        consent: bool = False,
    ) -> dict:
        # Standalone administrative rebuilds still use the same publication path.
        # Durable jobs call prepare_index and publish in their completion transaction.
        from app.adapters.persistence.embedding_records import publish_embeddings

        prepared = self.prepare_index(project_id, document_id, chunk_ids, consent)
        with Session(self.engine) as session, session.begin():
            return publish_embeddings(session, prepared)

    def prepare_index(
        self,
        project_id: str,
        document_id: str,
        chunk_ids: tuple[str, ...] = (),
        consent: bool = False,
    ) -> PreparedEmbeddingIndex:
        self._ready()
        with Session(self.engine) as session:
            document = session.get(DocumentRow, document_id)
            if document is None or document.project_id != project_id:
                raise NotFound("Document is outside the requested project")
            query = select(ChunkRow).where(
                ChunkRow.document_id == document_id, ChunkRow.project_id == project_id
            )
            if chunk_ids:
                query = query.where(ChunkRow.id.in_(chunk_ids))
            chunks = list(session.scalars(query.order_by(ChunkRow.id).limit(129)))
            if not chunks or len(chunks) > 128:
                raise DomainError("Select 1 to 128 document chunks for this bounded indexing job")
            if chunk_ids and {c.id for c in chunks} != set(chunk_ids):
                raise DomainError("Requested chunks are not all in the selected document")
            source_hash = document.content_hash
        descriptor = self.embeddings.descriptor
        vectors = []
        # No database write transaction remains open across paid/network calls.
        for start in range(0, len(chunks), 64):
            batch = chunks[start : start + 64]
            values = self.embeddings.embed([c.text for c in batch], consent=consent)
            vectors.extend(validate_vectors(values, len(batch), descriptor.dimensions))
        return PreparedEmbeddingIndex(
            project_id=project_id,
            document_id=document_id,
            source_hash=source_hash,
            descriptor=descriptor,
            chunks=tuple(
                EmbeddedChunk(
                    chunk_id=chunk.id,
                    text_hash=hashlib.sha256(chunk.text.encode()).hexdigest(),
                    vector=vector,
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ),
        )

    def search(self, project_id: str, query: SemanticQuery) -> list[SemanticMatch]:
        table = self._ready()
        descriptor = self.embeddings.descriptor
        vector = validate_vectors(
            self.embeddings.embed([query.query], consent=query.consent), 1, descriptor.dimensions
        )[0]
        distance = table.c.embedding.cosine_distance(list(vector)).label("distance")
        statement = (
            select(ChunkRow.payload, DocumentRow.id, distance)
            .select_from(table)
            .join(ChunkRow, ChunkRow.id == table.c.chunk_id)
            .join(DocumentRow, DocumentRow.id == table.c.document_id)
            .where(
                table.c.project_id == project_id,
                DocumentRow.project_id == project_id,
                table.c.model == descriptor.model,
                table.c.model_version == descriptor.version,
                table.c.dimensions == descriptor.dimensions,
                table.c.source_hash == DocumentRow.content_hash,
            )
        )
        if query.document_id:
            statement = statement.where(table.c.document_id == query.document_id)
        if query.source_hash:
            statement = statement.where(table.c.source_hash == query.source_hash)
        with Session(self.engine) as session:
            rows = session.execute(statement.order_by(distance).limit(query.limit))
            result = []
            for chunk, document_id, value in rows:
                if value is None or not math.isfinite(float(value)):
                    raise ProviderError("Vector index returned an invalid cosine distance")
                result.append(
                    SemanticMatch(
                        document_id=document_id,
                        chunk_id=chunk["id"],
                        text=chunk["text"],
                        page=chunk.get("page"),
                        source_hash=chunk["source_hash"],
                        score=1 - float(value),
                        model=descriptor.model,
                        model_version=descriptor.version,
                        dimensions=descriptor.dimensions,
                        test_only=descriptor.test_only,
                    )
                )
            return result
