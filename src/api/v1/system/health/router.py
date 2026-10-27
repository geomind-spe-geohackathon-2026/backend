from fastapi import APIRouter

from src.api.v1.system.health import schemas, services

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=schemas.HealthStatus)
async def health() -> schemas.HealthStatus:
    return services.get_health_status()
