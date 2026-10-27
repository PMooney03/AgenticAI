# Docker Compose

## What it is

Docker packages an app and its runtime into an image. Compose is a YAML file that starts
several containers on one network, with volumes, health checks and port mappings. Here
that is Qdrant, the FastAPI backend, and an nginx frontend.

Ollama is **not** in Compose. The models and (usually) the GPU already live on the host;
the backend reaches them at `http://host.docker.internal:11434`.

## Why we use it

- One command brings up the stack a teammate or an interviewer can actually run.
- Qdrant needs a persistent volume; Compose mounts `./data/qdrant` so indexes survive
  container recreation.
- Binding published ports to `127.0.0.1` is the local equivalent of a network policy:
  the API is not on the LAN.

## What problem it solves

"It works on my machine" for a three-process app (API, UI, vector DB) plus a host LLM.
Without Compose you document four terminals and hope the URLs match.

## Alternatives

| Option | Trade-off |
| --- | --- |
| Host processes only (`uv` + `npm` + one Qdrant container) | Fastest inner loop; what Phases 1-7 used |
| Kubernetes / AKS | Real production orchestrator; far too much for a single-user local app |
| Devcontainers | Nice for VS Code; does not show a deployable image |
| Put Ollama in Compose too | Reproducible; huge image, GPU passthrough is painful on Windows/macOS |

## How it is wired in this project

```
docker compose up -d qdrant                  # inner loop: only the vector DB
docker compose --profile app up -d --build   # UI :8080, API :8000, Qdrant :6333
docker compose -f docker-compose.fake.yml up --build -d --wait  # CI smoke, no Ollama
```

- `qdrant` has no profile, so the original `up -d qdrant` workflow is unchanged.
- `backend` and `frontend` sit on profile `app`. The backend image is Python 3.12 via
  `uv sync --frozen`. The frontend is a multi-stage Node build copied into nginx.
- nginx serves the SPA and reverse-proxies `/chat`, `/documents`, `/agent`, `/metrics`,
  `/eval` to `backend:8000` via Docker DNS (`resolver 127.0.0.11`) so nginx can start
  before the backend hostname exists. The browser uses one origin (`:8080`); CORS is a
  fallback.
- `DATA_DIR=/data` is a bind mount of `./data` (uploads, SQLite, notes.jsonl).
- Health checks: Qdrant TCP probe (the image has no curl); backend `GET /health`.
- `docker-compose.fake.yml` is a separate Compose project (`asb-fake`) on port 18000.
  `LLM_PROVIDER=fake` and `QDRANT_URL=:memory:` mean it never talks to Ollama or the
  inner-loop Qdrant. No volume: the image's `/data` stays writable by uid 10001.

## How I would explain it in an interview

"Compose is the local production shape. Qdrant is a service on the Docker network;
Ollama stays on the host because that is where the weights and GPU are; the UI is a
static nginx image that proxies the API so I do not fight CORS in the packaged app.
I bind `127.0.0.1` on published ports because this is a single-user box with no auth.
`uv sync --frozen` and `npm ci` mean the image is the lockfile, not 'whatever pip
resolved today'."

## Gotchas worth mentioning

- Inside the container `localhost` is the container, not the host. That is why Ollama
  is `host.docker.internal` and Qdrant is the service name `qdrant`.
- The process inside the container must listen on `0.0.0.0`. Localhost-binding happens
  on the *published* port, not in uvicorn.
- Bind-mount permissions vs a non-root USER differ on Linux and Docker Desktop. Named
  volumes are smoother in production.
- Recreating the backend wipes in-memory traces and metrics. HITL checkpoints live in
  `data/checkpoints.sqlite` on the `./data` volume, so a pending approval survives a
  bounce. Traces and live metrics still reset.
