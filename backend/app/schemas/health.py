from typing import Literal

from pydantic import BaseModel


class OllamaStatus(BaseModel):
    reachable: bool
    model: str
    base_url: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    ollama: OllamaStatus
