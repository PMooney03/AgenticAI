from fastapi import APIRouter, Request

from app.observability.metrics import MetricsStore
from app.schemas.metrics import MetricsSnapshot

router = APIRouter(tags=["llmops"])


def _store(request: Request) -> MetricsStore:
    return request.app.state.metrics


@router.get("/metrics", response_model=MetricsSnapshot, summary="In-process LLMOps snapshot")
async def metrics(request: Request) -> MetricsSnapshot:
    return MetricsSnapshot.model_validate(_store(request).snapshot())
