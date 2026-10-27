"""Request-ID middleware.

Each request gets a correlation ID (an incoming ``X-Request-ID`` header is honoured so
the frontend or a proxy can propagate its own). The ID is stored in a ``ContextVar`` for
logging, exposed on ``request.state`` for handlers, and echoed in the response header.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.observability.logging import request_id_var

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_HEADER_ID_LENGTH = 128


def _incoming_or_new_request_id(request: Request) -> str:
    candidate = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if candidate and len(candidate) <= _MAX_HEADER_ID_LENGTH and candidate.isprintable():
        return candidate
    return uuid.uuid4().hex


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = _incoming_or_new_request_id(request)
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            metrics = getattr(request.app.state, "metrics", None)
            if metrics is not None:
                metrics.observe_http(method=request.method, path=request.url.path, status_code=500)
            raise
        finally:
            request_id_var.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        metrics = getattr(request.app.state, "metrics", None)
        if metrics is not None:
            metrics.observe_http(
                method=request.method, path=request.url.path, status_code=response.status_code
            )
        return response
