# Architecture

This document captures the target design and is updated as phases land. Sections marked
*(planned)* describe components not yet implemented.

## Component map

```mermaid
flowchart TD
    UI[React + TypeScript + Vite UI] -->|HTTP JSON| API[FastAPI]
    API --> Graph[LangGraph agent]
    Graph --> Retriever[Retriever abstraction]
    Graph --> Tools[Tool layer: local tools + MCP client]
    Graph --> LLM[LLMProvider]
    Retriever --> Ingest[LlamaIndex readers + SentenceSplitter]
    Retriever --> Qdrant[(Qdrant in Docker)]
    Retriever --> Embed[EmbeddingProvider -> Ollama nomic-embed-text]
    Tools --> MCP[Local MCP server: allowlisted tools]
    LLM --> Ollama[Ollama qwen2.5:14b]
    API --> Obs[Structured logs + metrics + trace store]
```

## Responsibilities

| Component | Responsibility | Status |
| --- | --- | --- |
| FastAPI | HTTP boundary, validation, error handling, request IDs | Phase 1 |
| `LLMProvider` / `OllamaProvider` | Vendor-neutral chat completion and health check | Phase 1 |
| Prompt registry | Versioned system prompts, version logged per request | Phase 1 |
| Observability | JSON logs with request correlation; metrics and traces later | Phase 1 (base) |
| Upload security | Allowlist + content sniffing, safe filenames, streaming size cap | Phase 2 |
| LlamaIndex | `PDFReader` per-page loading, `SentenceSplitter` overlapping chunks | Phase 2 |
| `EmbeddingProvider` / `LocalEmbeddingProvider` | Local embeddings via Ollama `nomic-embed-text` | Phase 2 |
| `VectorStore` / `QdrantVectorStore` | Points: chunk UUID, vector, payload (document, page, text, metadata) | Phase 2 |
| `DocumentRegistry` | SQLite table of documents with status and counts | Phase 2 |
| `Retriever` + `RAGPipeline` | Embed question, search, build cited context, answer with sources | Phase 2 |
| React UI | Sidebar (upload/status/delete), chat, source citations, activity placeholder | Phase 3 |
| CORS | Allowlisted Vite origin; `X-Request-ID` exposed to the browser | Phase 3 |
| LangGraph | Stateful plan / act / evaluate loop with conditional routing | Phase 4 *(planned)* |
| MCP server + client | Allowlisted local tools over a standard protocol | Phase 5 *(planned)* |
| Human-in-the-loop | `interrupt()` on state-changing tools, approve/reject endpoint | Phase 6 *(planned)* |
| Evaluation | Local dataset, retrieval and groundedness metrics | Phase 7 *(planned)* |
| Docker Compose + CI | `frontend`, `backend`, `qdrant`; GitHub Actions lint/test/build | Phase 8 *(planned)* |

## Ingestion flow (Phase 2)

```mermaid
sequenceDiagram
    participant C as Client
    participant A as POST /documents/upload
    participant S as IngestionService
    participant V as validate_upload
    participant L as LlamaIndex PDFReader / read_text
    participant K as SentenceSplitter
    participant E as LocalEmbeddingProvider
    participant Q as QdrantVectorStore
    participant R as DocumentRegistry

    C->>A: multipart file
    A->>S: ingest(filename, stream)
    S->>S: spool to data/uploads/<uuid>/upload.part (size cap enforced)
    S->>V: name, size, first 4 KB
    V-->>S: safe_name, content_type (or FileValidationError)
    S->>R: create(status=processing)
    S->>L: load_pages(path)
    L-->>S: [LoadedPage(text, page)]
    S->>K: chunk_pages(400 tokens, 60 overlap)
    K-->>S: [Chunk(uuid5, document_id, page, text)]
    S->>E: embed_documents(texts)  (search_document: prefix, batched)
    E-->>S: vectors
    S->>Q: upsert(chunks, vectors)
    S->>R: mark_ready(chunk_count, page_count)
    A-->>C: 201 DocumentResponse
```

## Question flow (Phase 2, `use_documents=true`)

```mermaid
sequenceDiagram
    participant C as Client
    participant A as POST /chat
    participant P as RAGPipeline
    participant T as Retriever
    participant E as LocalEmbeddingProvider
    participant Q as QdrantVectorStore
    participant X as build_context
    participant L as OllamaProvider

    C->>A: {message, history, top_k}
    A->>P: answer(question, history)
    P->>T: retrieve(question)
    T->>E: embed_query (search_query: prefix)
    T->>Q: search(vector, top_k, cosine)
    Q-->>T: [RetrievedChunk(score, document, page, text)]
    T-->>P: RetrievalResult(chunks, embedding_ms, search_ms)
    P->>X: build_context(chunks)
    X-->>P: "[Source N] file, page P <<< text >>>" + sources[]
    P->>L: chat([rag-system-v1(context), ...history, question])
    L-->>P: answer with [Source N] citations
    P->>P: extract_citations -> cited labels
    A-->>C: ChatResponse(answer, sources[cited flag], retrieval stats, prompt_version)
```

With `use_documents=false` the route skips retrieval and uses `chat-system-v1` (Phase 1
behaviour).

## Target agent graph (Phase 4, planned)

```mermaid
flowchart TD
    Start([question]) --> plan[plan: structured output -> action]
    plan -->|retrieve| retrieve[retrieve_documents]
    plan -->|tool| call_tool[call_tool: approval interrupt if state-changing]
    plan -->|answer| answer[generate_answer]
    retrieve --> evaluate[evaluate: enough evidence?]
    call_tool --> evaluate
    evaluate -->|need more and steps < max| plan
    evaluate -->|sufficient or budget hit| answer
    answer --> Finish([answer + sources + trace])
```

State carried through the graph: `question`, `history`, `steps[]` (high-level trace shown
to the user), `retrieved_chunks[]`, `tool_results[]`, `step_count`, `pending_approval`,
`final_answer`, `sources`.

## Guiding simplifications

- LlamaIndex is used for ingestion only; embedding, upsert and search are explicit in our
  code so each step can be explained and tested.
- LangChain is used for interfaces (`ChatOllama`, `@tool`, prompts, structured output),
  never for opaque chains or agent executors.
- One LLM call per graph step and a hard step budget keep the agent inspectable.
- No external databases beyond Qdrant; the document registry is SQLite.
