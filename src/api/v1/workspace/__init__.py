"""Workspace endpoints."""

from fastapi import APIRouter
from src.api.v1.workspace.connectors.router import router as connectors_router
from src.api.v1.workspace.documents.router import router as documents_router
from src.api.v1.workspace.documents.tasks import TASK_MODULES as documents_task_modules
from src.api.v1.workspace.overview.router import router as overview_router
from src.api.v1.workspace.projects.router import router as projects_router

router = APIRouter(prefix="/workspace")
router.include_router(projects_router)
router.include_router(overview_router)
router.include_router(documents_router)
router.include_router(connectors_router)

TASK_MODULES = (*documents_task_modules,)
