"""FastAPI dependency seams.

Routes depend on these functions rather than on concrete classes. Tests replace the *leaf*
dependencies (LLM, embeddings, vector store, registry) via ``app.dependency_overrides``;
the composed ones (retriever, RAG pipeline, ingestion service) are built from whatever the
leaves resolve to, so overrides propagate automatically.

Leaf singletons are cached per unique configuration so HTTP clients are reused.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from langgraph.checkpoint.memory import InMemorySaver

from app.config import Settings, get_settings
from app.embeddings import EmbeddingProvider, LocalEmbeddingProvider
from app.ingestion import DocumentRegistry, IngestionService
from app.llm import LLMProvider, OllamaProvider
from app.rag import RAGPipeline
from app.retrieval import QdrantVectorStore, Retriever, VectorStore

SettingsDep = Annotated[Settings, Depends(get_settings)]


# --- leaves -------------------------------------------------------------------------------


@lru_cache
def _build_ollama_provider(
    base_url: str, model: str, timeout_seconds: float, temperature: float
) -> OllamaProvider:
    return OllamaProvider(
        base_url=base_url, model=model, timeout_seconds=timeout_seconds, temperature=temperature
    )


def get_llm_provider(settings: SettingsDep) -> LLMProvider:
    return _build_ollama_provider(
        settings.ollama_base_url_str,
        settings.ollama_model,
        settings.ollama_timeout_seconds,
        settings.ollama_temperature,
    )


@lru_cache
def _build_embedding_provider(
    base_url: str, model: str, batch_size: int, timeout_seconds: float
) -> LocalEmbeddingProvider:
    return LocalEmbeddingProvider(
        base_url=base_url, model=model, batch_size=batch_size, timeout_seconds=timeout_seconds
    )


def get_embedding_provider(settings: SettingsDep) -> EmbeddingProvider:
    return _build_embedding_provider(
        settings.ollama_base_url_str,
        settings.embedding_model,
        settings.embedding_batch_size,
        settings.ollama_timeout_seconds,
    )


@lru_cache
def _build_vector_store(location: str, collection: str, api_key: str | None) -> QdrantVectorStore:
    return QdrantVectorStore(location=location, collection=collection, api_key=api_key)


def get_vector_store(settings: SettingsDep) -> VectorStore:
    api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    return _build_vector_store(settings.qdrant_url, settings.qdrant_collection, api_key)


@lru_cache
def _build_registry(db_path: str) -> DocumentRegistry:
    return DocumentRegistry(db_path)


def get_document_registry(settings: SettingsDep) -> DocumentRegistry:
    return _build_registry(str(settings.registry_db_path))


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]
DocumentRegistryDep = Annotated[DocumentRegistry, Depends(get_document_registry)]


# --- composed -----------------------------------------------------------------------------


def get_retriever(
    settings: SettingsDep, embeddings: EmbeddingProviderDep, store: VectorStoreDep
) -> Retriever:
    return Retriever(
        embeddings=embeddings,
        store=store,
        default_top_k=settings.retrieval_top_k,
        score_threshold=settings.retrieval_score_threshold or None,
    )


RetrieverDep = Annotated[Retriever, Depends(get_retriever)]


def get_rag_pipeline(retriever: RetrieverDep, llm: LLMProviderDep) -> RAGPipeline:
    return RAGPipeline(retriever=retriever, llm=llm)


RAGPipelineDep = Annotated[RAGPipeline, Depends(get_rag_pipeline)]


def get_checkpointer(request: Request) -> InMemorySaver:
    return request.app.state.checkpointer


CheckpointerDep = Annotated[InMemorySaver, Depends(get_checkpointer)]


async def get_agent(
    settings: SettingsDep,
    retriever: RetrieverDep,
    llm: LLMProviderDep,
    checkpointer: CheckpointerDep,
):
    # Imported here so retrieval/RAG finish loading before the graph (avoids a cycle).
    # Async so FastAPI does not run this in a threadpool — the first MCP import must
    # happen on the event-loop thread (Windows pywin32).
    from app.agent.graph import Agent
    from app.mcp.client import InProcessMCPClient
    from app.mcp.server import get_mcp_server

    return Agent(
        llm=llm,
        retriever=retriever,
        tools=InProcessMCPClient(get_mcp_server(str(settings.notes_path))),
        checkpointer=checkpointer,
        max_steps=settings.agent_max_steps,
    )


AgentDep = Annotated[object, Depends(get_agent)]


def get_ingestion_service(
    settings: SettingsDep,
    registry: DocumentRegistryDep,
    store: VectorStoreDep,
    embeddings: EmbeddingProviderDep,
) -> IngestionService:
    return IngestionService(
        registry=registry,
        store=store,
        embeddings=embeddings,
        upload_dir=settings.upload_dir,
        max_upload_bytes=settings.max_upload_bytes,
        chunk_size=settings.chunk_size_tokens,
        chunk_overlap=settings.chunk_overlap_tokens,
    )


IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]
