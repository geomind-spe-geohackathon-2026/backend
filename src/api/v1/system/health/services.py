from src.api.v1.system.health import schemas


def get_health_status() -> schemas.HealthStatus:
    return schemas.HealthStatus(status="ok")
