"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.trace import TraceStore
from app.api import agent, chat, documents, health
from app.config import Settings, get_settings
from app.observability import RequestContextMiddleware, configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    logger.info(
        "app_started",
        extra={
            "model": settings.ollama_model,
            "embedding_model": settings.embedding_model,
            "ollama_base_url": settings.ollama_base_url_str,
            "qdrant_url": settings.qdrant_url,
            "log_level": settings.log_level,
        },
    )
    yield
    logger.info("app_stopped")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _sanitise_validation_errors(exc: RequestValidationError) -> list[dict]:
    # Drop the echoed ``input`` (could contain user content) and docs ``url`` noise.
    return [{k: v for k, v in error.items() if k not in {"input", "url"}} for error in exc.errors()]


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "Request validation failed.",
            "errors": jsonable_encoder(_sanitise_validation_errors(exc)),
            "request_id": _request_id(request),
        },
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Logged by RequestContextMiddleware; never leak internals to the client.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error.", "request_id": _request_id(request)},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Local, agentic second brain. Phase 4: a LangGraph agent decides whether to "
            "retrieve documents, call an allowlisted tool, or answer, then returns sources "
            "and a high-level workflow trace."
        ),
        lifespan=_lifespan,
    )
    app.state.settings = settings
    app.state.traces = TraceStore()

    app.add_middleware(RequestContextMiddleware)
    # CORS is added last so it is the outermost middleware (handles OPTIONS preflight).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)

    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(documents.router)
    app.include_router(agent.router)
    return app


app = create_app()
