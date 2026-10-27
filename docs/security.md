# Security and privacy decisions

This document records the concrete controls in the codebase and the reasoning behind them.
It grows with each phase.

## Principles

1. Everything runs locally; no document, question or answer leaves the machine.
2. Untrusted input is validated at the boundary (HTTP) and treated as data, not instructions,
   when it reaches the model.
3. Fail closed with safe, generic error messages; details go to logs, not clients.
4. Logs carry timings, counts and identifiers, never content or secrets.

## Upload handling (`app/security/files.py`, `app/ingestion/service.py`)

| Threat | Control |
| --- | --- |
| Path traversal via filename | `safe_filename()` strips directories on both separators, normalises unicode to ASCII, replaces anything outside `[A-Za-z0-9._-]`, removes leading dots, caps length. The file is stored under a server-generated UUID directory; the client name is never a path component on its own. |
| Disguised file types | Extension allowlist (`.pdf`, `.txt`, `.md`) **and** content sniffing: PDFs must start with `%PDF-`; text files must be UTF-8 without NUL bytes. The client `Content-Type` header is ignored. |
| Resource exhaustion | `MAX_UPLOAD_MB` enforced while streaming to disk; the request is rejected as soon as the limit is crossed and the partial file is removed. Empty files are rejected. |
| Half-processed state | The registry records `processing` before indexing and `failed` with a short public error on any exception, so nothing silently disappears. |
| Clean-up on delete | `DELETE /documents/{id}` removes Qdrant points (filtered by `document_id`), the file directory, and the registry row. |

## Prompt injection via documents (`app/prompts/rag_system_v1.py`, `app/rag/context.py`)

Uploaded documents may contain text such as "ignore previous instructions". Controls:

- The system prompt states that excerpts are untrusted data and instructions inside them
  must not be followed.
- Each excerpt is wrapped in `<<< >>>` delimiters; look-alike delimiters inside document
  text are neutralised so an excerpt cannot "close itself" and inject text that appears to
  come from the system.
- Citations use server-assigned labels; the model cannot invent sources the API will accept
  (`extract_citations` drops out-of-range labels).

This reduces, but does not eliminate, injection risk. The agent phases add the stronger
control: tools that change state require explicit human approval regardless of what the
model was persuaded to do.

## CORS (Phase 3)

The API allowlists browser origins from `CORS_ORIGINS` (default `http://localhost:5173`
and `http://127.0.0.1:5173`). Unknown origins get no `Access-Control-Allow-Origin`.
Credentials are off (no cookies). `X-Request-ID` is exposed so the UI can correlate
errors with logs.

## API input validation (`app/schemas/`)

- Pydantic models with `extra="forbid"`, `max_length` on messages and history, bounded
  `top_k`. Unknown fields are rejected rather than ignored.
- Validation errors return the failing field locations but **not** the submitted input.
- History roles are limited to `user` / `assistant`; a client cannot inject a `system` turn.

## Error handling (`app/main.py`, routers)

- Dependency failures (Ollama, embeddings, Qdrant) map to `503` with a fixed, actionable
  message. Underlying exception text is logged, not returned.
- Unhandled exceptions return a generic `500` with the request ID for correlation.

## Logging (`app/observability/`)

- JSON lines; every record carries `request_id`.
- Logged: model names, prompt versions, durations, token counts, chunk counts, document IDs,
  status codes, sizes.
- Not logged: user messages, model answers, document text, filenames of uploads (only IDs),
  or any key named like a secret (`api_key`, `token`, `authorization`, ... are redacted).

## Configuration

- All settings come from environment variables / `.env` (gitignored). `.env.example`
  documents them with safe defaults.
- `QDRANT_API_KEY` is a `SecretStr`: it is never printed in reprs or logs.

## Data at rest

- Uploaded files: `data/uploads/<document_id>/<safe_name>` (gitignored).
- Vectors and chunk text: Qdrant volume at `data/qdrant/` (gitignored).
- Document registry: `data/registry.db` (gitignored).

Deleting a document removes it from all three.

## Known gaps (to be addressed or documented in later phases)

- No authentication: the API is intended for a single local user. Phase 8 documents how to
  bind to localhost only in Docker.
- No rate limiting.
- No antivirus scanning of uploads.
- PDF parsing uses `pypdf`; a malicious PDF could still exercise parser bugs. Parsing runs
  in-process today; sandboxing it is listed as a future improvement.
