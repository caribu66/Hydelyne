import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import strawberry
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter
from strawberry.schema.config import StrawberryConfig

from app.api.documents import router as documents_router
from app.api.dropbox import router as dropbox_router
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.config import get_settings, validate_prod_secrets
from app.graphql.schema import Mutation, Query
from app.graphql.validation import DepthValidationExtension, DisableIntrospection
from app.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.services.sentry import init_sentry

settings = get_settings()


def configure_logging() -> None:
    """Configure structured JSON logging for production."""
    import sys

    level = getattr(logging, (settings.LOG_LEVEL or "INFO").upper(), logging.INFO)

    if settings.APP_ENV != "production":
        logging.basicConfig(level=level)
        return

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            import json as _json

            base = {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            for key in (
                "request_id",
                "method",
                "path",
                "status",
                "duration_ms",
                "client",
                "error",
                "error_type",
            ):
                val = getattr(record, key, None)
                if val is not None:
                    base[key] = val
            try:
                return _json.dumps(base, default=str)
            except Exception:
                return record.getMessage()

    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    # Remove existing default handlers to avoid duplicate output
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)


async def get_graphql_context(request: Request, response: Response) -> dict:
    """Strawberry context getter.

    FastAPI resolves ``response: Response`` via dependency injection (supported
    by Strawberry 0.246+), giving us the actual Starlette response object so
    mutations can call ``response.set_cookie()`` / ``response.delete_cookie()``.
    """
    return {"request": request, "response": response}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    validate_prod_secrets()
    init_sentry()
    # Migrations are a discrete deployment step (backend/Dockerfile entrypoint);
    # the API assumes the schema is already current and will not start if it
    # isn't. See ADR-0002 for the rationale and ``app.database.init_db`` for
    # the SQLite dev/test helper.
    # Bootstrap admin user if configured
    try:
        from app.services.crew import bootstrap_admin

        await bootstrap_admin()
    except Exception as exc:
        logging.getLogger(__name__).warning("Admin bootstrap skipped (%s)", type(exc).__name__)
    # Setup Meilisearch indexes if available (non-blocking)
    try:
        from app.services.meilisearch import meilisearch_client

        await meilisearch_client.setup_indexes()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Meilisearch index setup skipped (%s)", type(exc).__name__
        )
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hydenlyne Crew DMS",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        openapi_url="/openapi.json" if settings.APP_ENV != "production" else None,
    )

    # CORS: localhost origins are safe for dev; in production only explicitly
    # configured origins are allowed so a missing/leaked FRONTEND_URL cannot
    # silently leave dev origins open.
    cors_origins: list[str] = []
    if settings.APP_ENV != "production":
        cors_origins.extend(
            [
                "http://localhost:5173",
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:5173",
            ]
        )
    is_prod = settings.APP_ENV == "production"
    for url in [
        settings.APP_URL,
        getattr(settings, "FRONTEND_URL", ""),
        getattr(settings, "CORS_ORIGINS", ""),
    ]:
        if not url:
            continue
        for part in str(url).split(","):
            part = part.strip().rstrip("/")
            if not part or part in cors_origins:
                continue
            if part == "*":
                raise RuntimeError(
                    "Refusing to start: CORS_ORIGINS='*' is incompatible with "
                    "allow_credentials=True. List explicit origins instead."
                )
            if is_prod and part.startswith("http://localhost"):
                # A localhost default must never become a trusted prod origin.
                continue
            cors_origins.append(part)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    if settings.APP_ENV == "production":
        app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    schema = strawberry.Schema(
        query=Query,
        mutation=Mutation,
        config=StrawberryConfig(auto_camel_case=True),
        extensions=[DepthValidationExtension]
        + ([DisableIntrospection] if settings.APP_ENV == "production" else []),
    )

    graphql_router = GraphQLRouter(
        schema,
        path="/graphql",
        graphql_ide="apollo-sandbox" if settings.APP_ENV != "production" else None,
        context_getter=get_graphql_context,
    )
    app.include_router(graphql_router)
    app.include_router(documents_router)
    app.include_router(dropbox_router)
    app.include_router(health_router)
    app.include_router(search_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        response = {
            "name": "Hydenlyne Crew DMS",
            "version": "1.0.0",
            "graphql": "/graphql",
        }
        if settings.APP_ENV != "production":
            response["docs"] = "/docs"
        return response

    return app


app = create_app()
