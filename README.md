# Agentic Second Brain

A fully local, free, agentic AI system for working with your own documents. It evolves a
traditional RAG "second brain" into a LangGraph-driven agent that decides when to retrieve
documents, when to call tools (via MCP), and when to keep reasoning through a multi-step
workflow, with human approval for anything that changes state.

> Status: **Phase 5 complete** - the LangGraph agent calls allowlisted tools over MCP
> (calculator and clock). The UI shows the real high-level workflow trace.
> See [Build phases](#build-phases) for what comes next.

## Table of contents

- [Overview](#overview)
- [Motivation](#motivation)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Build phases](#build-phases)
- [Local setup](#local-setup)
- [API](#api)
- [How RAG works here](#how-rag-works-here)
- [Where each framework is used](#where-each-framework-is-used)
- [Security and privacy](#security-and-privacy)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Design decisions](#design-decisions)
- [Interview notes](#interview-notes)
- [Roadmap sections](#roadmap-sections)

## Overview

The user uploads PDF / TXT / Markdown documents and chats with them. Unlike a basic RAG
app, the backend runs a stateful agent workflow:

```
User question
  -> LangGraph agent
  -> plan: what is required?
       - retrieve document context
       - call an approved MCP tool
       - answer directly
  -> evaluate results, loop if more evidence is needed (bounded)
  -> generate a grounded answer
  -> return answer + sources + high-level workflow trace
```

Everything runs locally: Ollama for inference, Qdrant in Docker for vectors, a local MCP
server for tools. No paid APIs, no cloud.

## Motivation

Built to practise and demonstrate the skills expected of an AI Engineer: LLM application
design, RAG, vector databases, agent orchestration with LangGraph, tool integration via
MCP, responsible-AI controls (human-in-the-loop, permission boundaries), LLMOps
(prompt versioning, structured logging, evaluation), Docker and CI/CD.

## Architecture

```
                ┌──────────────┐
                │ React UI     │
                └──────┬───────┘
                       │
                  FastAPI API
                       │
                ┌──────▼───────┐
                │ LangGraph    │
                │ Agent        │
                └──────┬───────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
   RAG Retrieval    MCP Tools      LLM
         │             │             │
   LlamaIndex       MCP Server     Ollama
         │
      Qdrant
         │
   Local Embeddings
```

Phases 1-3 implement `React UI -> FastAPI -> RAG -> LlamaIndex / Qdrant / Embeddings ->
Ollama`. See [docs/architecture.md](docs/architecture.md) for the full target design and
data flow.

## Technology stack

| Layer | Technology | Role |
| --- | --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic | HTTP API, validation, error handling |
| LLM runtime | Ollama (`qwen2.5:14b`) | Local inference for the chat model |
| Embeddings | Ollama (`nomic-embed-text`) | Local 768-d embeddings for chunks and queries |
| LLM abstraction | LangChain (`langchain-core`, `langchain-ollama`) | Provider-agnostic chat model, prompts, tool definitions |
| Ingestion | LlamaIndex (`PDFReader`, `SentenceSplitter`) | Page-aware PDF loading and sentence-aware overlapping chunks |
| Vector DB | Qdrant in Docker | Cosine similarity search over chunk embeddings with metadata payloads |
| Registry | SQLite (stdlib) | Document list, status, chunk/page counts |
| Agent | LangGraph | Stateful, inspectable workflow with conditional routing |
| Tools | MCP (`mcp` 2.x) | Allowlisted local tools over the Model Context Protocol |
| Frontend | React, TypeScript, Vite | Sidebar, chat, source citations, LangGraph activity panel |
| Infra | Docker Compose, GitHub Actions (Phase 8) | Local orchestration and CI |

## Build phases

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Architecture and plan | Done |
| 1 | FastAPI + Ollama chat, provider abstraction, prompt versioning, tests | Done |
| 2 | Document ingestion (LlamaIndex) + local embeddings + Qdrant + grounded RAG with citations | Done |
| 3 | React frontend (upload, chat, sources, activity placeholder) | Done |
| 4 | LangGraph agent | Done |
| 5 | MCP tools | Done |
| 6 | Human-in-the-loop approval | Planned |
| 7 | Logging, metrics, evaluation (LLMOps) | Planned |
| 8 | Docker Compose + CI/CD hardening | Planned |

## Local setup

Prerequisites: [Ollama](https://ollama.com) running on the host, Docker Desktop,
[uv](https://docs.astral.sh/uv/).

```powershell
# Pull models (once)
ollama pull qwen2.5:14b
ollama pull nomic-embed-text

# Configure
copy .env.example .env

# Vector database (persists to ./data/qdrant)
docker compose up -d qdrant

# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --reload-exclude .venv --port 8000

# Frontend (new terminal)
cd frontend
copy .env.example .env   # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev
```

Open http://localhost:5173 for the UI, http://localhost:8000/docs for OpenAPI, and
http://localhost:6333/dashboard for Qdrant. If port 8000 is already in use, start the
backend with `--port 8010` and set `VITE_API_BASE_URL=http://localhost:8010` in
`frontend/.env`. The backend allowlists `http://localhost:5173` via `CORS_ORIGINS`.

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Status of Ollama, the embedding model, Qdrant (chunk count) and the registry |
| POST | `/documents/upload` | Multipart upload of a `.pdf`, `.txt` or `.md`; validates, chunks, embeds, indexes |
| GET | `/documents` | List documents with status (`processing` / `ready` / `failed`) and counts |
| GET | `/documents/{id}` | One document |
| DELETE | `/documents/{id}` | Remove the document, its chunks in Qdrant and the stored file |
| POST | `/chat` | Ask a question. LangGraph plans retrieve / tool / answer. `use_documents` (default `true`) allows retrieval |
| GET | `/agent/tools` | Allowlisted MCP tools (`calculator`, `clock`) |
| GET | `/agent/trace/{request_id}` | High-level nodes and labels for a recent chat (no content) |

Example:

```powershell
curl -X POST http://localhost:8000/documents/upload -F "file=@handbook.pdf"

curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" `
  -d '{"message": "How many days of annual leave do employees get?"}'
```

Response (abridged):

```json
{
  "answer": "Full-time employees receive 27 days of paid annual leave per year [Source 1].",
  "mode": "rag",
  "model": "qwen2.5:14b",
  "prompt_version": "rag-system-v1",
  "request_id": "0cfeeb7d...",
  "latency_ms": 2392,
  "sources": [
    {
      "label": 1,
      "document_name": "handbook.pdf",
      "page": 4,
      "score": 0.7489,
      "snippet": "Full-time employees receive 27 days of paid annual leave per year, ...",
      "cited": true
    }
  ],
  "retrieval": { "retrieved_chunks": 4, "retrieval_ms": 296, "cited_sources": 1 },
  "workflow": [
    { "id": "plan-0", "node": "plan", "label": "Analysed request", "done": true },
    { "id": "retrieve-1", "node": "retrieve", "label": "Searched documents", "done": true },
    { "id": "retrieve-2", "node": "retrieve", "label": "Retrieved 4 chunks", "done": true },
    { "id": "evaluate-3", "node": "evaluate", "label": "Evaluated results", "done": true },
    { "id": "answer-4", "node": "generate_answer", "label": "Generated response", "done": true }
  ]
}
```

When the documents do not cover the question the model is instructed to say so:

> The uploaded documents do not contain enough information to answer this.
> [General knowledge: The capital of Australia is Canberra.]

## How RAG works here

```
upload  : file -> validate -> LlamaIndex PDFReader (per page) -> SentenceSplitter (400 tok, 60 overlap)
          -> nomic-embed-text -> Qdrant upsert (vector + text + document/page payload) -> registry "ready"

question: LangGraph plan -> (retrieve | MCP tool | answer)
          retrieve: nomic-embed-text -> Qdrant top-k -> rag-system-v1 -> cited answer
          calculator / clock: MCP tools/call -> agent-answer-v1
          answer: chat-system-v1 when no retrieval was needed
```

The grounding prompt (`rag-system-v1`) instructs the model to answer only from the excerpts,
cite every statement, explicitly say when the documents are insufficient, and treat excerpt
text as untrusted data (so instructions hidden inside a document are not followed).

Full explanation: [docs/interview-notes/rag.md](docs/interview-notes/rag.md).

## Where each framework is used

| Concern | Tool | Why |
| --- | --- | --- |
| PDF loading with page numbers, sentence-aware chunking | LlamaIndex | Best-in-class for the data side; stops there so embed/store/search stay explicit |
| LLM client, prompts, (later) tool definitions and structured output | LangChain | Standard interfaces; no chains or agent executors that would hide control flow |
| Embeddings, vector store, retrieval, RAG pipeline | Our own code | Small, explicit, testable with fakes and Qdrant's in-memory mode |
| Agent orchestration | LangGraph | Explicit state machine: plan → retrieve / tool / answer, evaluate, bounded loop |

Details: [LlamaIndex](docs/interview-notes/llamaindex.md),
[embeddings](docs/interview-notes/embeddings.md),
[Qdrant](docs/interview-notes/vector-databases-qdrant.md).

## Security and privacy

Highlights (full list in [docs/security.md](docs/security.md)):

- Uploads: extension allowlist plus content sniffing (`%PDF-` magic, UTF-8 check), safe
  filenames, server-generated storage paths, streaming size limit.
- Prompt injection: retrieved text is delimited and declared untrusted; delimiter look-alikes
  are neutralised; citation labels are server-assigned.
- API: `extra="forbid"` schemas, bounded lengths, no `system` role from clients, validation
  errors never echo input.
- Logs: request IDs, timings, counts and model/prompt versions only; no message or document
  content; secret-like keys redacted.
- Everything stays on the machine: Ollama, Qdrant and files under `data/` (gitignored).

## Testing

Tests never require Ollama or a Qdrant server. Through FastAPI dependency overrides the LLM
becomes `FakeLLMProvider`, embeddings become a deterministic hashed-bag-of-words
`FakeEmbeddingProvider`, and the vector store is the real `QdrantVectorStore` running Qdrant's
in-process `:memory:` mode. PDFs for loader tests are generated by hand in `tests/helpers.py`.

```powershell
cd backend
uv run pytest            # 100+ tests, ~1 s
uv run ruff check .
uv run ruff format --check .

cd ..\frontend
npm test                 # Vitest + Testing Library, no backend required
npm run lint
npm run build
```

Backend coverage: config, prompt registry, upload validation, loaders, chunking, registry,
Qdrant, retriever, RAG pipeline, LangGraph routing/tools/graph, CORS, every API endpoint,
mocked Ollama/embeddings.

Frontend coverage: API client (request IDs, multipart upload, error parsing, tools),
citation splitting, source panel and agent-activity rendering of graph events.

## Project structure

```
docker-compose.yml       Qdrant (backend + frontend services arrive in Phase 8)
backend/
  app/
    main.py              FastAPI app factory, middleware, exception handlers, routers
    config.py            Settings from environment (pydantic-settings)
    dependencies.py      DI seams: LLM, embeddings, vector store, registry -> retriever, RAG, ingestion
    api/                 Routers: health, chat, documents
    schemas/             Pydantic request/response models
    llm/                 LLMProvider protocol, OllamaProvider (ChatOllama), FakeLLMProvider
    embeddings/          EmbeddingProvider protocol, LocalEmbeddingProvider (Ollama), fake
    ingestion/           loaders (LlamaIndex PDFReader), chunking (SentenceSplitter), SQLite registry, service
    retrieval/           VectorStore protocol, QdrantVectorStore, Retriever
    rag/                 context builder (sources + delimiters), RAGPipeline
    agent/               LangGraph state, nodes, routing, tool allowlist, in-memory traces
    mcp/                 MCPServer (calculator, clock) + in-process Client; `python -m app.mcp` for stdio
    security/            upload validation, safe filenames
    prompts/             versioned prompts (chat, rag, agent-planner, agent-answer) + registry
    observability/       request-ID middleware, structured JSON logging
  tests/
frontend/
  src/
    api/                 typed client + ApiError
    components/          Sidebar, Chat, SourcePanel, AgentActivity, ApprovalCard
    hooks/               documents, chat, health
    lib/                 citation parser, pending workflow placeholder
  tests live next to the modules they cover (Vitest)
docs/
  architecture.md  security.md
  interview-notes/       One page per technology, written as it is introduced
data/                    (gitignored) uploads/, qdrant/, registry.db
```

## Design decisions

- **Provider abstraction.** `LLMProvider` is a small `Protocol`; `OllamaProvider` is the only
  implementation today. Swapping to another runtime (or a hosted model such as Azure OpenAI)
  means adding one class, not touching routes or prompts.
- **Prompt versioning.** Prompts live in `app/prompts/` with explicit version IDs
  (`chat-system-v1`). Every response and log line carries the version used.
- **Request-scoped observability.** Each request gets an ID (honouring an incoming
  `X-Request-ID`), which is returned in the response header and body and attached to every
  log record for that request.
- **Secrets and privacy.** All configuration comes from environment variables. User
  messages, model outputs and document text are not logged; only lengths and timings are.
- **Explicit retrieval pipeline.** LlamaIndex handles loading and chunking only. Embedding,
  storage and search are our own small modules behind `EmbeddingProvider` and `VectorStore`
  protocols, so every step is visible, testable and swappable.
- **Chunk text lives in Qdrant payloads.** One round-trip returns everything needed for a
  citation; deleting a document is a single filtered delete.
- **Lazy, dimension-agnostic collection.** The Qdrant collection is created from the first
  vector's length, and a mismatch (after changing embedding model) fails with a clear message
  instead of corrupting search.
- **Offline-safe chunking.** `SentenceSplitter` is given a cheap tokenizer and a regex
  sentence splitter, so ingestion needs no tiktoken download or NLTK data at runtime.
- **LangGraph as an explicit state machine.** Routing lives in Python (`decide_plan`,
  `route_after_evaluate`), tools are allowlisted, evaluate is a heuristic (not another
  LLM call), and the UI only sees high-level step labels.
- **MCP for tools.** The graph names an allowlisted tool; an MCP client calls the local
  server. FastAPI uses the SDK in-memory transport; `python -m app.mcp` is stdio.

Security and privacy decisions are documented in [docs/security.md](docs/security.md).

## Interview notes

Short explainers for each technology, written as it enters the project:

- [Ollama](docs/interview-notes/ollama.md)
- [FastAPI](docs/interview-notes/fastapi.md)
- [RAG](docs/interview-notes/rag.md)
- [Embeddings](docs/interview-notes/embeddings.md)
- [Vector databases and Qdrant](docs/interview-notes/vector-databases-qdrant.md)
- [LlamaIndex](docs/interview-notes/llamaindex.md)
- [React and Vite](docs/interview-notes/react-vite.md)
- [LangGraph](docs/interview-notes/langgraph.md)
- [MCP](docs/interview-notes/mcp.md)

## Roadmap sections

The following README sections will be filled in by later phases: LangChain role in depth,
human-in-the-loop design, LLMOps features and evaluation, Docker setup
for all services, screenshots, CI/CD, limitations, future improvements, and an Azure
mapping of each local component.

## Screenshots

Add captures of the three-column UI (sidebar + chat + sources) here once you have used the
app with your own documents. The layout is: documents on the left, conversation in the
centre, source cards and agent activity on the right.
