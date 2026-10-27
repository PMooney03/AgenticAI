# Architecture

This document captures the target design and is updated as phases land. Sections marked
*(planned)* describe components not yet implemented (Phase 8: Docker Compose + CI).

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
    API --> Obs[Structured logs + metrics + golden-set eval]
```

## Responsibilities

| Component | Responsibility | Status |
| --- | --- | --- |
| FastAPI | HTTP boundary, validation, error handling, request IDs | Phase 1 |
| `LLMProvider` / `OllamaProvider` | Vendor-neutral chat completion and health check | Phase 1 |
| Prompt registry | Versioned system prompts, version logged per request | Phase 1 |
| Observability | JSON logs with request correlation; in-process metrics | Phase 1 (logs), Phase 7 (metrics) |
| Upload security | Allowlist + content sniffing, safe filenames, streaming size cap | Phase 2 |
| LlamaIndex | `PDFReader` per-page loading, `SentenceSplitter` overlapping chunks | Phase 2 |
| `EmbeddingProvider` / `LocalEmbeddingProvider` | Local embeddings via Ollama `nomic-embed-text` | Phase 2 |
| `VectorStore` / `QdrantVectorStore` | Points: chunk UUID, vector, payload (document, page, text, metadata) | Phase 2 |
| `DocumentRegistry` | SQLite table of documents with status and counts | Phase 2 |
| `Retriever` + `RAGPipeline` | Embed question, search, build cited context, answer with sources | Phase 2 |
| React UI | Sidebar (upload/status/delete), chat, source citations, activity placeholder | Phase 3 |
| CORS | Allowlisted Vite origin; `X-Request-ID` exposed to the browser | Phase 3 |
| LangGraph | Stateful plan / retrieve / tool / evaluate loop with conditional routing | Phase 4 |
| Trace store | In-memory high-level steps keyed by request ID (no content) | Phase 4 |
| MCP server + client | Allowlisted calculator + clock over official `mcp` SDK | Phase 5 |
| Human-in-the-loop | `interrupt()` on `save_note`; `POST /agent/runs/{id}/decision` | Phase 6 |
| Evaluation | Golden set, citation rate, lexical groundedness, HITL checks | Phase 7 |
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

## Question flow (Phase 4)

```mermaid
sequenceDiagram
    participant C as Client
    participant A as POST /chat
    participant G as LangGraph Agent
    participant P as plan (agent-planner-v1)
    participant T as Retriever
    participant K as calculator (AST)
    participant L as OllamaProvider

    C->>A: {message, history, use_documents}
    A->>G: run(question, history)
    G->>P: structured JSON action
    alt retrieve
        G->>T: embed + Qdrant search
        T-->>G: chunks
        G->>G: evaluate (heuristic)
    else tool
        G->>K: allowlisted expression
        K-->>G: numeric result
        G->>G: evaluate (heuristic)
    else answer
        G->>L: chat-system / rag-system / agent-answer
    end
    G-->>A: answer + sources + workflow steps
    A-->>C: ChatResponse (mode rag|chat, workflow[], request_id)
```

`use_documents=false` clamps any `retrieve` decision to `answer`. Unknown tool names are
also clamped. The inspectable trace (`GET /agent/trace/{request_id}`) stores node names and
step labels only.

## Question flow (Phase 2, always-retrieve RAG — still used inside the retrieve node)

```mermaid
sequenceDiagram
    participant R as retrieve node
    participant T as Retriever
    participant E as LocalEmbeddingProvider
    participant Q as QdrantVectorStore
    participant X as build_context
    participant L as generate_answer

    R->>T: retrieve(question)
    T->>E: embed_query (search_query: prefix)
    T->>Q: search(vector, top_k, cosine)
    Q-->>T: [RetrievedChunk(score, document, page, text)]
    T-->>R: RetrievalResult(chunks)
    L->>X: build_context(chunks)
    X-->>L: "[Source N] file, page P <<< text >>>" + sources[]
    L->>L: rag-system-v1 + extract_citations
```

## Agent graph (Phase 4)

```mermaid
flowchart TD
    Start([question]) --> plan[plan: structured output -> action]
    plan -->|retrieve| retrieve[retrieve_documents]
    plan -->|tool| call_tool[call_tool: allowlisted MCP tools]
    plan -->|answer| answer[generate_answer]
    retrieve --> evaluate[evaluate: enough evidence?]
    call_tool --> evaluate
    evaluate -->|need more and steps < max| plan
    evaluate -->|sufficient or budget hit| answer
    answer --> Finish([answer + sources + trace])
```

State carried through the graph: `question`, `history`, `steps[]` (high-level trace shown
to the user), `chunks[]`, `tool_results[]`, `step_count`, `answer`, `sources`.
`save_note` calls `interrupt()`; `ChatResponse.pending_approval` carries the proposal.

## Tool calls (Phase 5)

```mermaid
sequenceDiagram
    participant G as call_tool node
    participant P as allowlist
    participant C as InProcessMCPClient
    participant S as MCPServer

    G->>P: name in TOOLS?
    P-->>G: yes / clamp to answer
    G->>C: call_tool(name, args)
    C->>S: tools/call (MCP)
    S-->>C: text or is_error
    C-->>G: str result
```

Default transport is in-process (`Client(server)`). `python -m app.mcp` serves the same
tools over stdio.

## Human approval (Phase 6)

```mermaid
sequenceDiagram
    participant U as UI
    participant C as POST /chat
    participant G as call_tool
    participant I as interrupt
    participant D as POST /agent/runs/id/decision
    participant S as save_note MCP

    U->>C: remember to buy milk
    C->>G: tool_name=save_note
    G->>I: pause (no write)
    C-->>U: pending_approval + preview
    U->>D: approved true or false
    alt approve
        D->>G: Command(resume=approve)
        G->>S: tools/call
        S-->>G: Saved note id
    else reject
        D->>G: Command(resume=reject)
        G-->>D: rejected, disk unchanged
    end
```

## Guiding simplifications

- LlamaIndex is used for ingestion only; embedding, upsert and search are explicit in our
  code so each step can be explained and tested.
- LangChain is used for interfaces (`ChatOllama`, `@tool`, prompts, structured output),
  never for opaque chains or agent executors.
- One LLM call per graph step and a hard step budget keep the agent inspectable.
- No external databases beyond Qdrant; the document registry is SQLite.

## LLMOps (Phase 7)

```mermaid
flowchart LR
    Chat[POST /chat] --> Q[score_quality]
    Q --> M[MetricsStore]
    M --> G[GET /metrics]
    Cases[Golden cases] --> R[run_golden_eval]
    R --> E[POST /eval/run]
```

Online: every finished (or paused) agent run records latency, tokens, tools, citation
rate and groundedness — never the answer text. Offline: the same graph runs against
fakes on a pinned dataset (`python -m app.eval`). Retrieval hit and generation quality
are separate checks.

