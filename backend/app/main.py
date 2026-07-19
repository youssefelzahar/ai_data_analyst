from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.database import create_database_tables


@asynccontextmanager
async def application_lifespan(app: FastAPI):
    create_database_tables()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.debug)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=application_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=_get_dev_cors_origin_regex(settings.debug),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Expose the download filename header so browser fetch() can read it
        # cross-origin (otherwise files save without a proper extension).
        expose_headers=["Content-Disposition"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


def _get_dev_cors_origin_regex(debug: bool) -> str | None:
    if not debug:
        return None
    return (
        r"^https?://("
        r"localhost|127\.0\.0\.1|0\.0\.0\.0|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?$"
    )


app = create_app()
