"""Explicit engineering-capability construction and resource ownership.

The caller supplies its startup ExitStack so partially constructed clients close
on failure, in the same reverse order as the rest of the composition root.
"""

from contextlib import ExitStack

from app.adapters.persistence.database import SQLRepositoryFactory
from app.application.capability_jobs import CapabilityJobService
from app.ports.providers import DocumentCatalog
from app.ports.services import FileStore
from app.settings import Settings


def build_capability_jobs(
    settings: Settings,
    factory: SQLRepositoryFactory,
    runtime_name: str,
    storage: FileStore,
    documents: DocumentCatalog,
    resources: ExitStack,
) -> CapabilityJobService:
    from app.adapters.bim_ifc import LocalIFCImporter
    from app.adapters.resolver_ortools import ORToolsResolver
    from app.adapters.vision_pydantic import PydanticAIVisionAnalyzer

    enabled = {"document_parse", "bim_import"}
    if settings.optimization_enabled:
        enabled.add("optimization")
    if settings.vision_enabled:
        enabled.add("vision")
    vision = PydanticAIVisionAnalyzer(
        settings.vision_model,
        settings.model_api_key,
        settings.model_base_url,
        provider=settings.model_provider,
        enabled=settings.vision_enabled,
    )
    resources.callback(vision.close)
    semantic = None
    if settings.vector_enabled:
        from app.adapters.embeddings import (
            DeterministicTestEmbeddings,
            OpenAICompatibleEmbeddings,
        )
        from app.adapters.retrieval_pgvector import PgVectorSearch

        if settings.embedding_provider == "deterministic-test":
            embeddings = DeterministicTestEmbeddings(
                settings.embedding_dimensions, settings.embedding_version
            )
        else:
            embeddings = OpenAICompatibleEmbeddings(
                settings.embedding_model,
                settings.embedding_version,
                settings.embedding_dimensions,
                settings.model_api_key,
                settings.model_base_url,
                cloud_egress_enabled=settings.cloud_embedding_egress,
            )
            resources.callback(embeddings.close)
        semantic = PgVectorSearch(factory.engine, embeddings)
        enabled.add("embedding_index")
    return CapabilityJobService(
        factory,
        runtime_name,
        storage,
        documents,
        LocalIFCImporter(),
        ORToolsResolver(),
        vision,
        frozenset(enabled),
        semantic,
    )
