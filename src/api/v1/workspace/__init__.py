"""Workspace endpoints."""

from fastapi import APIRouter
from src.api.v1.workspace.projects.router import router as projects_router

router = APIRouter(prefix="/workspace")
router.include_router(projects_router)

TASK_MODULES = ()
