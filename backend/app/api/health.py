import asyncio

from fastapi import APIRouter

from app.dependencies import (
    DocumentRegistryDep,
    EmbeddingProviderDep,
    LLMProviderDep,
    SettingsDep,
    VectorStoreDep,
)
from app.retrieval import VectorStoreUnavailableError
from app.schemas.health import (
    EmbeddingStatus,
    HealthResponse,
    OllamaStatus,
    QdrantStatus,
)

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service and dependency status")
async def health(
    settings: SettingsDep,
    llm: LLMProviderDep,
    embeddings: EmbeddingProviderDep,
    store: VectorStoreDep,
    registry: DocumentRegistryDep,
) -> HealthResponse:
    llm_ok, embed_ok, store_ok = await asyncio.gather(
        llm.health(), embeddings.health(), store.health()
    )
    chunks: int | None = None
    if store_ok:
        try:
            chunks = await store.count()
        except VectorStoreUnavailableError:
            store_ok = False

    return HealthResponse(
        status="ok" if (llm_ok and embed_ok and store_ok) else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        ollama=OllamaStatus(
            reachable=llm_ok, model=llm.model_name, base_url=settings.ollama_base_url_str
        ),
        embeddings=EmbeddingStatus(reachable=embed_ok, model=embeddings.model_name),
        qdrant=QdrantStatus(
            reachable=store_ok,
            url=settings.qdrant_url,
            collection=settings.qdrant_collection,
            chunks=chunks,
        ),
        documents_ready=registry.count_ready(),
    )
