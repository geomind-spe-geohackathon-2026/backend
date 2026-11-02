"""Assistant endpoints."""

from fastapi import APIRouter
from src.api.v1.assistant.chat.router import router as chat_router
from src.api.v1.assistant.runs.router import router as runs_router
from src.api.v1.assistant.runs.tasks import TASK_MODULES as runs_task_modules
from src.api.v1.assistant.usage.router import router as usage_router

router = APIRouter(prefix="/assistant")
router.include_router(chat_router)
router.include_router(runs_router)
router.include_router(usage_router)

TASK_MODULES = (*runs_task_modules,)
