"""HTTP API package."""

from fastapi import APIRouter

from src.api.v1 import JOB_MODULES as v1_job_modules
from src.api.v1 import router as v1_router

router = APIRouter()
router.include_router(v1_router)

JOB_MODULES = (*v1_job_modules,)
