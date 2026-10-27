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
| LlamaIndex | Load PDF/TXT/MD with page metadata, overlapping chunking | Phase 2 *(planned)* |
| `EmbeddingProvider` | Local embeddings via Ollama `nomic-embed-text` | Phase 2 *(planned)* |
| Qdrant | Vector store: chunk id, text, document, page, metadata, vector | Phase 2 *(planned)* |
| RAG pipeline | Embed question, retrieve, build grounded context, answer with sources | Phase 2 *(planned)* |
| React UI | Sidebar, chat, sources, agent activity, approvals | Phase 3 *(planned)* |
| LangGraph | Stateful plan / act / evaluate loop with conditional routing | Phase 4 *(planned)* |
| MCP server + client | Allowlisted local tools over a standard protocol | Phase 5 *(planned)* |
| Human-in-the-loop | `interrupt()` on state-changing tools, approve/reject endpoint | Phase 6 *(planned)* |
| Evaluation | Local dataset, retrieval and groundedness metrics | Phase 7 *(planned)* |
| Docker Compose + CI | `frontend`, `backend`, `qdrant`; GitHub Actions lint/test/build | Phase 8 *(planned)* |

## Request flow today (Phase 1)

```mermaid
sequenceDiagram
    participant C as Client
    participant M as RequestContextMiddleware
    participant R as /chat route
    participant P as Prompt registry
    participant L as OllamaProvider
    participant O as Ollama

    C->>M: POST /chat {message, history}
    M->>M: assign request_id, start timer
    M->>R: validated ChatRequest
    R->>P: get_prompt("chat-system")
    P-->>R: chat-system-v1
    R->>L: chat([system, ...history, user])
    L->>O: /api/chat via ChatOllama
    O-->>L: assistant message + usage
    L-->>R: LLMResult(content, model, latency, tokens)
    R-->>M: ChatResponse(answer, model, prompt_version, request_id, latency_ms)
    M-->>C: 200 + X-Request-ID header, JSON log line
```

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
