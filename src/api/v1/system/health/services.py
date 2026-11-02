from src.api.v1.system.health import schemas
from src.core.settings import settings


def get_health_status() -> schemas.HealthStatus:
    scripted = settings.ASSISTANT_LLM == "fake"
    return schemas.HealthStatus(
        status="ok",
        assistant="scripted" if scripted else "model",
    )
