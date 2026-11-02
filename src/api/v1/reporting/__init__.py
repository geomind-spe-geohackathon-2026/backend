"""Reporting endpoints."""

from fastapi import APIRouter
from src.api.v1.reporting.design.router import router as design_router

router = APIRouter(prefix="/reporting")
router.include_router(design_router)

TASK_MODULES = ()
