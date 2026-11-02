"""Plant endpoints."""

from fastapi import APIRouter
from src.api.v1.plant.flowsheet.router import router as flowsheet_router
from src.api.v1.plant.parameters.router import router as parameters_router

router = APIRouter(prefix="/plant")
router.include_router(flowsheet_router)
router.include_router(parameters_router)

TASK_MODULES = ()
