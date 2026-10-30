from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from fastapi import FastAPI
from src.core.errors import ErrorMiddleware
from src.core.logging.middleware import RequestLoggingMiddleware
from src.core.ratelimit.middleware import RateLimitMiddleware
from src.core.security.middleware import SecurityMiddleware
from src.core.settings import settings


def include_middlewares(app: FastAPI) -> None:
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityMiddleware)
    app.add_middleware(ErrorMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.APP_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
