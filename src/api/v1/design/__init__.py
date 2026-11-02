"""Design endpoints."""

from fastapi import APIRouter
from src.api.v1.design.case.router import router as case_router
from src.api.v1.design.results.router import router as results_router
from src.api.v1.design.study.router import router as study_router
from src.api.v1.design.study.tasks import TASK_MODULES as study_task_modules

router = APIRouter(prefix="/design")
router.include_router(case_router)
router.include_router(study_router)
router.include_router(results_router)

TASK_MODULES = (*study_task_modules,)
