from fastapi import APIRouter

from app.dependencies import LLMProviderDep, SettingsDep
from app.schemas.health import HealthResponse, OllamaStatus

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Service and dependency status")
async def health(settings: SettingsDep, llm: LLMProviderDep) -> HealthResponse:
    reachable = await llm.health()
    return HealthResponse(
        status="ok" if reachable else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        ollama=OllamaStatus(
            reachable=reachable,
            model=llm.model_name,
            base_url=settings.ollama_base_url_str,
        ),
    )
