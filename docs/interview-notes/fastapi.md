# FastAPI

## What it is

FastAPI is an asynchronous Python web framework built on Starlette (ASGI) and Pydantic.
You declare request and response shapes as typed Python models; FastAPI validates input,
serialises output, and generates an OpenAPI schema and interactive docs (`/docs`) for free.

## Why we use it

- The backend is I/O bound (waiting on Ollama, Qdrant, MCP servers), so `async` handlers
  let one process serve many concurrent requests without threads.
- Pydantic models double as validation, documentation and the contract the React
  frontend codes against.
- Dependency injection (`Depends`) gives clean seams for swapping the LLM provider,
  retriever or settings in tests.

## What problem it solves

It removes the boilerplate around parsing, validating and documenting HTTP APIs, and
returns consistent, machine-readable validation errors, which matters when an LLM-backed
service must fail predictably on bad input.

## Alternatives

| Option | Trade-off |
| --- | --- |
| Flask | Simpler, synchronous by default, validation and docs are add-ons |
| Django / DRF | Batteries included (ORM, admin, auth); heavier than needed for an AI service |
| Litestar | Similar philosophy to FastAPI; smaller ecosystem |

## How it is wired in this project

- `app/main.py` - `create_app()` factory: middleware, exception handlers, routers.
  A factory (rather than a module-level singleton) lets tests build an app with custom
  settings.
- `app/api/` - one router per concern (`health.py`, `chat.py`).
- `app/schemas/` - Pydantic request/response models with limits (`max_length`,
  `extra="forbid"`) so oversized or unexpected payloads are rejected before any LLM call.
- `app/dependencies.py` - `get_settings`, `get_llm_provider`. Tests override these with
  `app.dependency_overrides[...]` to inject `FakeLLMProvider`.
- `app/observability/middleware.py` - assigns a request ID, times the request, logs a
  structured completion record, echoes `X-Request-ID` back to the client.
- Error handling: validation failures return 422 with a sanitised error list (no echoed
  input), an unavailable model returns 503 with a safe message, and anything unexpected
  returns a generic 500 while the full traceback goes to the logs only.

## How I would explain it in an interview

"FastAPI is the HTTP boundary. Every route is thin: validate with Pydantic, call a
service through an injected dependency, map the result to a response model. Business
logic lives in plain Python modules (`llm/`, `prompts/`, later `rag/` and `agent/`), which
is what makes it unit-testable without a running model. The request-ID middleware is the
root of the observability story: every log line and every response can be correlated,
which becomes essential once a single chat request fans out into retrieval, tool calls and
several LLM calls."

## Gotchas worth mentioning

- Blocking calls inside `async def` handlers stall the event loop; use async clients or
  `run_in_threadpool`.
- `BaseHTTPMiddleware` is convenient but buffers streaming responses in some versions;
  when SSE streaming is added, a pure ASGI middleware may be preferable.
- Validation error payloads echo the offending input by default; this project strips it
  so user content does not end up in error responses or logs.
