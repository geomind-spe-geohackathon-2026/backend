import uvicorn

from fastapi import FastAPI
from src.api import router
from src.core.lifespan import lifespan
from src.core.logging.logger import configure_logging
from src.core.middlewares import include_middlewares
from src.core.settings import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)
app.include_router(router)
include_middlewares(app)


def run() -> None:
    configure_logging()
    uvicorn.run(
        "src.fastapi:app",
        host="0.0.0.0",
        port=80,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
