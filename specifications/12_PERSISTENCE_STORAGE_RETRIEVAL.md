# Persistence, Storage, Search, and Retrieval

## Persistence stack — Frozen

- SQLAlchemy 2.x
- Alembic migrations
- SQLite for local/desktop
- PostgreSQL for server/team
- domain/Pydantic models separate from ORM models

Use async or sync SQLAlchemy consistently where it best matches the application/runtime; do not mix styles casually. Repository/query services should be domain-specific rather than a universal generic repository.

## SQLite local/desktop — Required

SQLite is the zero-infrastructure authoritative application DB for local/demo/desktop. Enable appropriate pragmas/migrations and safe transaction boundaries. Store only metadata/structured project state in DB; large IFC/PDF/image/video objects remain in FileStore.

## PostgreSQL server/team — Required

Provide a verified PostgreSQL profile with the same domain behavior. Migrations must work for both supported databases where schemas are intended to be portable; isolate DB-specific enhancements.

## DBOS system database

DBOS local may use SQLite and server may use PostgreSQL. Do not assume the application DB and runtime DB must be physically identical; configuration may point them to appropriate databases while keeping operational setup simple.

## FileStore

### LocalFileStore — Required Default

Store files under a controlled application data directory with metadata/hash/revision in the DB. Prevent path traversal and unrestricted file access.

### S3CompatibleFileStore — Required Implemented Optional

Implement object storage against an S3-compatible API. Default test/dev service may be MinIO-compatible; do not tie the Port to one vendor. Support upload/read/delete or the minimal operations actually required by the product, content hashes, bounded sizes, and safe object keys.

## Retrieval strategy

Order of preference:

1. structured IDs/revisions/relationships;
2. relational queries;
3. metadata filters;
4. full-text search;
5. semantic/vector retrieval when it adds value.

Do not route structured construction facts through embeddings unnecessarily.

## Local search — Required

Provide lightweight metadata/FTS search appropriate for SQLite/local data and document chunks. It must work with no embedding model or external service.

## Server semantic retrieval — Required Implemented Optional

Use PostgreSQL + `pgvector` for vector similarity when embeddings are enabled. Keep embeddings as derived/rebuildable data linked to source revision/hash. Store model/version/dimension metadata. Re-index on source/model version changes as needed.

Do not add an independent vector database unless a future measured requirement justifies it.

## Embeddings

Use a configured logical `embedding_model`/provider where semantic retrieval is enabled. Normal CI uses deterministic fake embeddings or fixtures; live provider tests are opt-in with credentials.

## Current references

- pgvector: https://github.com/pgvector/pgvector
- current pgvector supports exact/approximate nearest-neighbor search while keeping vectors in PostgreSQL; verify version/API at implementation time.
- MinIO Python SDK can access MinIO and other S3-compatible services; verify current SDK/API at implementation time.
