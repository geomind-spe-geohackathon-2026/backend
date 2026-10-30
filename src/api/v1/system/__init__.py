"""System endpoints."""

from fastapi import APIRouter
from src.api.v1.system.health.jobs import JOB_MODULES as health_job_modules
from src.api.v1.system.health.router import router as health_router

router = APIRouter(prefix="/system")
router.include_router(health_router)

JOB_MODULES = (*health_job_modules,)
