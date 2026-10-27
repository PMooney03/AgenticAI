# Runtime image for the FastAPI backend. Tests run in CI, not in this image.
# Python 3.12 matches pyproject.toml; uv installs from the lockfile so builds are reproducible.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /src/backend

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/src/backend/.venv/bin:$PATH"

# pyproject readme points at the repo-root README.
COPY backend/pyproject.toml backend/uv.lock ./
COPY README.md /src/README.md

RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
RUN uv sync --frozen --no-dev \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown -R app:app /src /data

USER app
EXPOSE 8000

# Listen on all interfaces inside the network namespace. The published port is bound to
# 127.0.0.1 on the host in docker-compose.yml so the API is not reachable from the LAN.
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
