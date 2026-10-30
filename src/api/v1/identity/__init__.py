"""Identity endpoints."""

from fastapi import APIRouter
from src.api.v1.identity.authn.jobs import JOB_MODULES as authn_job_modules
from src.api.v1.identity.authn.router import router as authn_router
from src.api.v1.identity.me.jobs import JOB_MODULES as me_job_modules
from src.api.v1.identity.me.router import router as me_router
from src.api.v1.identity.users.router import router as users_router

router = APIRouter(prefix="/identity")
router.include_router(authn_router)
router.include_router(me_router)
router.include_router(users_router)

JOB_MODULES = (*authn_job_modules, *me_job_modules)
