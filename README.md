# Agentic Second Brain

A fully local, free, agentic AI system for working with your own documents. It evolves a
traditional RAG "second brain" into a LangGraph-driven agent that decides when to retrieve
documents, when to call tools (via MCP), and when to keep reasoning through a multi-step
workflow, with human approval for anything that changes state.

> Status: **Phase 1 complete** - FastAPI backend with a versioned prompt, an `LLMProvider`
> abstraction backed by Ollama, request-scoped logging, and a tested `/chat` endpoint.
> See [Build phases](#build-phases) for what comes next.

## Table of contents

- [Overview](#overview)
- [Motivation](#motivation)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Build phases](#build-phases)
- [Local setup](#local-setup)
- [API](#api)
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

Phase 1 implements the `FastAPI -> LLMProvider -> Ollama` path. See
[docs/architecture.md](docs/architecture.md) for the full target design and data flow.

## Technology stack

| Layer | Technology | Role |
| --- | --- | --- |
| Backend | Python 3.12, FastAPI, Pydantic | HTTP API, validation, error handling |
| LLM runtime | Ollama | Local inference for chat and embedding models |
| LLM abstraction | LangChain (`langchain-core`, `langchain-ollama`) | Provider-agnostic chat model, prompts, tool definitions |
| Ingestion | LlamaIndex (Phase 2) | Document loading and metadata-preserving chunking |
| Vector DB | Qdrant in Docker (Phase 2) | Semantic search over chunk embeddings |
| Agent | LangGraph (Phase 4) | Stateful, inspectable workflow with conditional routing |
| Tools | MCP (Phase 5) | Standard protocol for exposing allowlisted local tools |
| Frontend | React, TypeScript, Vite (Phase 3) | Chat, sources, agent activity, approvals |
| Infra | Docker Compose, GitHub Actions (Phase 8) | Local orchestration and CI |

## Build phases

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Architecture and plan | Done |
| 1 | FastAPI + Ollama chat, provider abstraction, prompt versioning, tests | Done |
| 2 | Document ingestion (LlamaIndex) + Qdrant + basic RAG | Planned |
| 3 | React frontend | Planned |
| 4 | LangGraph agent | Planned |
| 5 | MCP tools | Planned |
| 6 | Human-in-the-loop approval | Planned |
| 7 | Logging, metrics, evaluation (LLMOps) | Planned |
| 8 | Docker Compose + CI/CD hardening | Planned |

## Local setup

Prerequisites: [Ollama](https://ollama.com) running on the host, [uv](https://docs.astral.sh/uv/).

```powershell
# Pull models (once)
ollama pull qwen2.5:14b

# Configure
copy .env.example .env

# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for the interactive OpenAPI UI. If port 8000 is already in
use on your machine, pass a different `--port` (the frontend's API base URL is configurable
in Phase 3).

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Service status and Ollama reachability |
| POST | `/chat` | Chat with the configured model (Phase 1: direct, no retrieval) |

Example:

```powershell
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" `
  -d '{"message": "Explain what a vector database is in two sentences."}'
```

Response:

```json
{
  "answer": "...",
  "model": "qwen2.5:14b",
  "prompt_version": "chat-system-v1",
  "request_id": "7f3c...",
  "latency_ms": 1834
}
```

## Testing

Unit tests never require a running LLM. The `LLMProvider` is swapped for a `FakeLLMProvider`
through FastAPI dependency overrides.

```powershell
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Project structure

```
backend/
  app/
    main.py            FastAPI app factory, middleware, routers
    config.py          Settings from environment (pydantic-settings)
    dependencies.py    Dependency-injection seams (LLM provider, settings)
    api/               Routers: health, chat
    schemas/           Pydantic request/response models
    llm/               LLMProvider protocol, OllamaProvider, FakeLLMProvider
    prompts/           Versioned system prompts + registry
    observability/     Request-ID middleware, structured logging
  tests/
docs/
  architecture.md
  interview-notes/     One page per technology, written as it is introduced
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
  messages and model outputs are not logged by default; only lengths and timings are.

Full security and responsible-AI notes will be documented in `docs/security.md` and
`docs/responsible-ai.md` as those features land.

## Interview notes

Short explainers for each technology, written as it enters the project:

- [Ollama](docs/interview-notes/ollama.md)
- [FastAPI](docs/interview-notes/fastapi.md)

## Roadmap sections

The following README sections will be filled in by later phases: RAG explanation, LangGraph
workflow, LangChain role, LlamaIndex role, MCP explanation, vector database explanation,
security decisions, human-in-the-loop design, LLMOps features, Docker setup, screenshots,
CI/CD, limitations, future improvements, and an Azure mapping of each local component.
