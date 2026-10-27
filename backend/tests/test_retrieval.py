"""Qdrant store (in-memory) and Retriever, driven by the deterministic fake embeddings."""

import pytest

from app.embeddings import FakeEmbeddingProvider
from app.ingestion.chunking import Chunk
from app.retrieval import QdrantVectorStore, Retriever, VectorStoreUnavailableError


def _chunk(doc: str, index: int, text: str, page: int | None = None) -> Chunk:
    import uuid

    return Chunk(
        chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc}:{index}")),
        document_id=doc,
        document_name=f"{doc}.pdf",
        chunk_index=index,
        text=text,
        page=page,
        metadata={"content_type": "application/pdf"},
    )


CHUNKS = [
    _chunk("finance", 0, "Quarterly revenue grew twelve percent driven by subscriptions.", 1),
    _chunk("finance", 1, "Operating margin improved as cloud costs fell.", 2),
    _chunk("recipes", 0, "Whisk eggs with sugar, then fold in flour for the sponge cake.", 1),
    _chunk("recipes", 1, "Bake the sponge at 180 degrees for twenty five minutes.", 1),
]


@pytest.fixture
async def store(fake_embeddings: FakeEmbeddingProvider) -> QdrantVectorStore:
    s = QdrantVectorStore(location=":memory:", collection="t")
    vectors = await fake_embeddings.embed_documents([c.text for c in CHUNKS])
    await s.upsert(CHUNKS, vectors)
    return s


async def test_empty_store_is_safe(fake_embeddings: FakeEmbeddingProvider) -> None:
    s = QdrantVectorStore(location=":memory:", collection="empty")
    assert await s.count() == 0
    assert await s.search(await fake_embeddings.embed_query("anything"), top_k=3) == []
    await s.delete_document("nope")  # no error


async def test_upsert_and_count(store: QdrantVectorStore) -> None:
    assert await store.count() == 4
    assert await store.health() is True


async def test_search_returns_semantically_closest_with_payload(
    store: QdrantVectorStore, fake_embeddings: FakeEmbeddingProvider
) -> None:
    vector = await fake_embeddings.embed_query("how much did revenue grow")
    results = await store.search(vector, top_k=2)

    assert len(results) == 2
    top = results[0]
    assert top.document_id == "finance"
    assert "revenue" in top.text
    assert top.document_name == "finance.pdf"
    assert top.page == 1
    assert top.chunk_index == 0
    assert results[0].score >= results[1].score


async def test_search_respects_top_k_and_threshold(
    store: QdrantVectorStore, fake_embeddings: FakeEmbeddingProvider
) -> None:
    vector = await fake_embeddings.embed_query("sponge cake bake")
    assert len(await store.search(vector, top_k=1)) == 1
    # A very high threshold filters everything that is not nearly identical.
    assert await store.search(vector, top_k=4, score_threshold=0.99) == []


async def test_upsert_is_idempotent_on_chunk_id(
    store: QdrantVectorStore, fake_embeddings: FakeEmbeddingProvider
) -> None:
    vectors = await fake_embeddings.embed_documents([c.text for c in CHUNKS[:2]])
    await store.upsert(CHUNKS[:2], vectors)
    assert await store.count() == 4


async def test_delete_document_removes_only_that_document(store: QdrantVectorStore) -> None:
    await store.delete_document("finance")
    assert await store.count() == 2


async def test_dimension_mismatch_is_reported(store: QdrantVectorStore) -> None:
    with pytest.raises(VectorStoreUnavailableError, match="64-d"):
        await store.upsert([CHUNKS[0]], [[0.1] * 8])


async def test_upsert_length_mismatch_rejected(store: QdrantVectorStore) -> None:
    with pytest.raises(ValueError):
        await store.upsert([CHUNKS[0]], [])


async def test_retriever_embeds_query_and_reports_timings(
    store: QdrantVectorStore, fake_embeddings: FakeEmbeddingProvider
) -> None:
    retriever = Retriever(embeddings=fake_embeddings, store=store, default_top_k=3)
    result = await retriever.retrieve("fold in flour for the cake")

    assert fake_embeddings.query_calls == ["fold in flour for the cake"]
    assert len(result.chunks) == 3
    assert result.chunks[0].document_id == "recipes"
    assert result.embedding_ms >= 0 and result.search_ms >= 0
    assert result.total_ms == result.embedding_ms + result.search_ms


async def test_retriever_top_k_override(
    store: QdrantVectorStore, fake_embeddings: FakeEmbeddingProvider
) -> None:
    retriever = Retriever(embeddings=fake_embeddings, store=store, default_top_k=4)
    assert len((await retriever.retrieve("revenue", top_k=1)).chunks) == 1
