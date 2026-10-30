"""System endpoints."""

from fastapi import APIRouter
from src.api.v1.system.health.router import router as health_router
from src.api.v1.system.health.tasks import TASK_MODULES as health_task_modules

router = APIRouter(prefix="/system")
router.include_router(health_router)

TASK_MODULES = (*health_task_modules,)
