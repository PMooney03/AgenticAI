from pydantic import BaseModel, Field

from app.schemas.chat import WorkflowEvent


class ToolInfo(BaseModel):
    name: str
    description: str
    read_only: bool
    requires_approval: bool


class ToolListResponse(BaseModel):
    tools: list[ToolInfo]


class AgentTraceResponse(BaseModel):
    request_id: str
    nodes_visited: list[str] = Field(description="Graph nodes visited, in order.")
    workflow: list[WorkflowEvent]
    retrieved_chunks: int
    tools: list[str] = Field(description="Allowlisted tool names that ran (no arguments).")
    prompt_version: str
    model: str
