import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.eval.runner import run_golden_eval
from app.schemas.chat import ErrorResponse
from app.schemas.eval import EvalReport

router = APIRouter(tags=["llmops"])
logger = logging.getLogger(__name__)


@router.post(
    "/eval/run",
    response_model=EvalReport,
    summary="Run the local golden-set eval (fakes, no Ollama)",
)
async def eval_run(request: Request) -> EvalReport:
    report = await run_golden_eval()
    request.app.state.last_eval = report
    logger.info(
        "eval_completed",
        extra={
            "passed": report.passed,
            "failed": report.failed,
            "total": report.total,
            "duration_ms": report.duration_ms,
        },
    )
    return report


@router.get(
    "/eval/latest",
    response_model=EvalReport,
    summary="Most recent golden-set report from this process",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def eval_latest(request: Request) -> EvalReport:
    report = getattr(request.app.state, "last_eval", None)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No eval has been run yet.")
    return report
