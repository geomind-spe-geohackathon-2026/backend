"""HTTP API package."""

from fastapi import APIRouter
from src.api.v1 import TASK_MODULES as v1_task_modules
from src.api.v1 import router as v1_router

router = APIRouter()
router.include_router(v1_router)

TASK_MODULES = (*v1_task_modules,)
