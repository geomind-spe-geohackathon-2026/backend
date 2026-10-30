"""Version 1 of the HTTP API."""

from fastapi import APIRouter
from src.api.v1.identity import TASK_MODULES as identity_task_modules
from src.api.v1.identity import router as identity_router
from src.api.v1.system import TASK_MODULES as system_task_modules
from src.api.v1.system import router as system_router
from src.api.v1.workspace import TASK_MODULES as workspace_task_modules
from src.api.v1.workspace import router as workspace_router

router = APIRouter(prefix="/api/v1")
router.include_router(system_router)
router.include_router(identity_router)
router.include_router(workspace_router)

TASK_MODULES = (*system_task_modules, *identity_task_modules, *workspace_task_modules)
