"""Version 1 of the HTTP API."""

from fastapi import APIRouter
from src.api.v1.assistant import TASK_MODULES as assistant_task_modules
from src.api.v1.assistant import router as assistant_router
from src.api.v1.design import TASK_MODULES as design_task_modules
from src.api.v1.design import router as design_router
from src.api.v1.identity import TASK_MODULES as identity_task_modules
from src.api.v1.identity import router as identity_router
from src.api.v1.plant import TASK_MODULES as plant_task_modules
from src.api.v1.plant import router as plant_router
from src.api.v1.reporting import TASK_MODULES as reporting_task_modules
from src.api.v1.reporting import router as reporting_router
from src.api.v1.system import TASK_MODULES as system_task_modules
from src.api.v1.system import router as system_router
from src.api.v1.workspace import TASK_MODULES as workspace_task_modules
from src.api.v1.workspace import router as workspace_router

router = APIRouter(prefix="/api/v1")
router.include_router(system_router)
router.include_router(identity_router)
router.include_router(workspace_router)
router.include_router(plant_router)
router.include_router(design_router)
router.include_router(reporting_router)
router.include_router(assistant_router)

TASK_MODULES = (
    *system_task_modules,
    *identity_task_modules,
    *workspace_task_modules,
    *plant_task_modules,
    *design_task_modules,
    *reporting_task_modules,
    *assistant_task_modules,
)
