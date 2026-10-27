"""Version 1 of the HTTP API."""

from fastapi import APIRouter

from src.api.v1.identity import JOB_MODULES as identity_job_modules
from src.api.v1.identity import router as identity_router
from src.api.v1.system import JOB_MODULES as system_job_modules
from src.api.v1.system import router as system_router

router = APIRouter(prefix="/api/v1")
router.include_router(system_router)
router.include_router(identity_router)

JOB_MODULES = (*system_job_modules, *identity_job_modules)
