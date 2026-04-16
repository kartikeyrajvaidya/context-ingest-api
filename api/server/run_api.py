"""Application boot module for ContextIngest API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.feedback import router as feedback_router
from api.routes.health import router as health_router
from api.routes.ingest import router as ingest_router
from api.routes.query import router as query_router
from api.server.errorhandlers import setup_exception_handlers
from api.server.middleware import IPRateLimitMiddleware
from configs.common import CommonConfig
from db import db
from libs.logger import get_logger

logger = get_logger(__name__)


def setup_middleware(app: FastAPI) -> None:
    """Attach middleware. Order matters — outermost is added last."""
    app.add_middleware(IPRateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CommonConfig.CORS_ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )


def setup_routers(app: FastAPI) -> None:
    """Register API routers."""
    app.include_router(health_router, tags=["health"])
    app.include_router(query_router, prefix="/v1/query", tags=["query"])
    app.include_router(feedback_router, prefix="/v1/feedback", tags=["feedback"])
    app.include_router(ingest_router, prefix="/v1/ingest", tags=["ingest"])


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifecycle hooks."""
    logger.info("Starting %s ...", CommonConfig.APP_NAME)
    logger.info("Connecting to database ...")
    await db.connect()
    yield
    logger.info("Disconnecting from database ...")
    await db.disconnect()
    logger.info("Shutting down %s ...", CommonConfig.APP_NAME)


app = FastAPI(
    title=CommonConfig.APP_NAME,
    redirect_slashes=False,
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

setup_middleware(app)
setup_routers(app)
setup_exception_handlers(app)
