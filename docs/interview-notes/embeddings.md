# Embeddings

## What they are

An embedding model turns text into a fixed-length vector of numbers (768 floats for
`nomic-embed-text`) such that texts with similar meaning have vectors that point in similar
directions. Similarity is measured with cosine similarity: 1.0 means identical direction,
0 means unrelated.

"How much annual leave do I get?" and "Employees receive 27 days of paid leave" share almost
no words, but their embeddings are close. That is what makes semantic search work where
keyword search fails.

## Why we use them

Embeddings are the bridge between a natural-language question and the right passage in a
document. Both are embedded with the *same* model so they live in the same vector space and
can be compared.

## What problem they solve

Keyword search needs exact term matches and breaks on synonyms, paraphrase and typos.
Embeddings capture meaning, so retrieval tolerates all three.

## Alternatives

| Option | Trade-off |
| --- | --- |
| `nomic-embed-text` via Ollama (chosen) | Free, local, 768-d, strong on retrieval benchmarks, no PyTorch install |
| sentence-transformers (`bge-small`, `all-MiniLM`) | Runs in-process; pulls in PyTorch (~2 GB); fine-grained control |
| Hosted (OpenAI `text-embedding-3`, Azure OpenAI) | Excellent quality, zero ops; cost and data leaves the machine |
| BM25 / TF-IDF (sparse) | No model needed, exact-term precision; no semantics. Best combined with dense vectors ("hybrid") |

## How they are wired in this project

- `app/embeddings/base.py` - `EmbeddingProvider` protocol with `embed_documents()` and
  `embed_query()` kept separate: nomic models are trained with `search_document:` and
  `search_query:` prefixes, and asymmetric handling improves recall.
- `app/embeddings/ollama.py` - `LocalEmbeddingProvider` calls Ollama's `POST /api/embed`
  in batches; reuses the same `OLLAMA_BASE_URL` as the chat model.
- `app/embeddings/fake.py` - a deterministic hashed bag-of-words provider so retrieval tests
  run offline in milliseconds and still rank overlapping texts higher.
- The Qdrant collection is created lazily from the first vector's length, so changing
  models does not require code changes (but does require re-indexing; the store refuses
  mismatched dimensions with a clear error).

## How I would explain it in an interview

"An embedding is a learned coordinate for a piece of text. I embed every chunk once at
ingestion and store the vectors in Qdrant; at query time I embed the question and ask for
the nearest neighbours by cosine similarity. The model choice matters less than people
expect; what matters is using the same model on both sides, respecting any query/document
prefixes the model was trained with, and re-indexing whenever the model changes because
vectors from different models are not comparable."

## Gotchas worth mentioning

- Vectors from different models (or versions) are incompatible; a model swap means a
  full re-index.
- Embedding models have their own context limit (8k tokens for nomic); chunks must fit.
- Cosine scores are not probabilities; "0.75" is model-specific and thresholds need tuning.
- Embedding a long document as one vector averages its topics away; that is why we chunk.
