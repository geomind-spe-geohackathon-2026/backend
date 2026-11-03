"""Workspace endpoints."""

from fastapi import APIRouter
from src.api.v1.workspace.mcp.router import router as mcp_router
from src.api.v1.workspace.overview.router import router as overview_router
from src.api.v1.workspace.projects.router import router as projects_router
from src.api.v1.workspace.rag.router import router as rag_router
from src.api.v1.workspace.rag.tasks import TASK_MODULES as rag_task_modules

router = APIRouter(prefix="/workspace")
router.include_router(projects_router)
router.include_router(overview_router)
router.include_router(rag_router)
router.include_router(mcp_router)

TASK_MODULES = (*rag_task_modules,)
