# Vector databases and Qdrant

## What they are

A vector database stores embeddings alongside a payload (metadata) and answers "which
stored vectors are closest to this query vector?" quickly, even with millions of entries.
It does this with approximate nearest-neighbour (ANN) indexes such as HNSW, which trade a
tiny amount of recall for orders-of-magnitude faster search than a brute-force scan.

Qdrant is an open-source vector database written in Rust. It runs as a single Docker
container, exposes REST and gRPC APIs, supports payload filtering alongside vector search,
and has an in-process "local mode" that is ideal for tests.

## Why we use one

- Semantic search over chunks is the core retrieval operation in RAG.
- Metadata filtering lets us scope a search to one document or delete every chunk belonging
  to a document in one call.
- Persistence: vectors survive restarts via a mounted volume.

## What problem it solves

Brute-force cosine similarity over a few thousand vectors is fine in NumPy; over hundreds of
thousands it is not, and you still need persistence, filtering, updates and deletes. A vector
DB packages all of that.

## Alternatives

| Option | Trade-off |
| --- | --- |
| Qdrant (chosen) | Free, single container, filtering, local mode for tests, good Python client |
| Chroma | Simplest to start; weaker filtering and scaling story |
| pgvector (Postgres) | Keeps vectors next to relational data; ANN performance lags dedicated engines |
| FAISS | Library not a database: blazing fast, but you build persistence and metadata yourself |
| Azure AI Search / Pinecone / Weaviate Cloud | Managed, hybrid search built in; cost, data leaves the machine |

## How it is wired in this project

- `docker-compose.yml` runs `qdrant/qdrant` with `./data/qdrant` mounted for persistence.
  Dashboard at http://localhost:6333/dashboard.
- `app/retrieval/base.py` - `VectorStore` protocol: `upsert`, `search`, `delete_document`,
  `count`, `health`. The RAG pipeline depends only on this.
- `app/retrieval/qdrant_store.py` - `QdrantVectorStore`:
  - point ID = chunk UUID; vector = embedding; payload = `document_id`, `document_name`,
    `page`, `chunk_index`, `text`, extra metadata;
  - collection created lazily with cosine distance and a keyword index on `document_id`;
  - `location=":memory:"` runs the real client code in-process for tests.
- `app/retrieval/retriever.py` - `Retriever` pairs the store with an `EmbeddingProvider`
  and records embedding vs search latency separately.

## How I would explain it in an interview

"Qdrant is where chunk embeddings live. Each point carries the vector plus a payload with
the document ID, filename, page and the chunk text itself, so a search result is directly
usable as a citation. I hid it behind a five-method `VectorStore` interface: the pipeline
never imports the Qdrant client, tests run against Qdrant's in-memory mode, and swapping to
pgvector or Azure AI Search would be one new class. The design decision I'd highlight is
storing text in the payload rather than a separate database: one round-trip per query, and
deletes are a single filtered call."

## Gotchas worth mentioning

- Point IDs must be UUIDs or integers; we derive UUID5s from `document_id:index` so re-indexing
  the same document overwrites rather than duplicates.
- ANN search is approximate; `exact=True` exists for counts and debugging but is slow.
- A collection is bound to one vector dimension; changing embedding model means a new
  collection or a full re-index.
- Payload indexes are a no-op in local mode; the server mode needs them for fast filters.
