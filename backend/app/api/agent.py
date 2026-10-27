import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.agent.tools.policy import list_tools
from app.agent.trace import TraceStore
from app.api.chat import (
    _LLM_DOWN,
    _RETRIEVAL_DOWN,
    _store_trace,
    chat_response_from_result,
)
from app.dependencies import AgentDep
from app.embeddings import EmbeddingUnavailableError
from app.llm import LLMUnavailableError
from app.retrieval import VectorStoreUnavailableError
from app.schemas.agent import AgentTraceResponse, ApprovalDecision, ToolInfo, ToolListResponse
from app.schemas.chat import ChatResponse, ErrorResponse, WorkflowEvent

router = APIRouter(tags=["agent"])
logger = logging.getLogger(__name__)


def _trace_store(request: Request) -> TraceStore:
    return request.app.state.traces


@router.get("/agent/tools", response_model=ToolListResponse, summary="Allowlisted agent tools")
async def agent_tools() -> ToolListResponse:
    return ToolListResponse(
        tools=[
            ToolInfo(
                name=spec.name,
                description=spec.description,
                read_only=spec.read_only,
                requires_approval=spec.requires_approval,
                source=spec.source,
            )
            for spec in list_tools()
        ]
    )


@router.get(
    "/agent/trace/{request_id}",
    response_model=AgentTraceResponse,
    summary="High-level trace for a recent chat request",
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def agent_trace(request_id: str, request: Request) -> AgentTraceResponse:
    record = _trace_store(request).get(request_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No trace found for that request.")
    return AgentTraceResponse(
        request_id=record.request_id,
        nodes_visited=record.nodes_visited,
        workflow=[WorkflowEvent.model_validate(step) for step in record.workflow],
        retrieved_chunks=record.retrieved_chunks,
        tools=record.tools,
        prompt_version=record.prompt_version,
        model=record.model,
    )


@router.post(
    "/agent/runs/{request_id}/decision",
    response_model=ChatResponse,
    summary="Approve or reject a pending write tool",
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def agent_decision(
    request_id: str,
    payload: ApprovalDecision,
    request: Request,
    agent: AgentDep,
) -> ChatResponse:
    try:
        result = await agent.resume(request_id, approved=payload.approved)
    except LookupError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="No pending approval for that request."
        ) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=_LLM_DOWN) from exc
    except (EmbeddingUnavailableError, VectorStoreUnavailableError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=_RETRIEVAL_DOWN) from exc

    response = chat_response_from_result(result, request_id)
    _store_trace(request, result, request_id)
    logger.info(
        "approval_resolved",
        extra={
            "approved": payload.approved,
            "tool": (result.tool_names or [None])[0],
            "pending": result.pending_approval is not None,
        },
    )
    return response
