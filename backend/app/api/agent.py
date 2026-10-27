from fastapi import APIRouter, HTTPException, Request, status

from app.agent.tools.policy import list_tools
from app.agent.trace import TraceStore
from app.schemas.agent import AgentTraceResponse, ToolInfo, ToolListResponse
from app.schemas.chat import ErrorResponse, WorkflowEvent

router = APIRouter(tags=["agent"])


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
