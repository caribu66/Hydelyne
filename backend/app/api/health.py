from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text

from app.auth.decorators import require_admin_rest, require_api_key
from app.config import get_settings
from app.database import get_engine
from app.services.cache import get_redis

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


def _is_prod() -> bool:
    return settings.APP_ENV == "production"


def _redacted_or_detail(detail: str) -> dict:
    """Return redacted detail in prod, full detail in dev."""
    if _is_prod():
        return {"status": "unhealthy", "detail": "Service temporarily unavailable"}
    return {"status": "unhealthy", "detail": detail}


async def _dependency_statuses() -> dict[str, str]:
    """Check service availability without returning credentials or payloads."""

    async def database() -> str:
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            return "healthy"
        except Exception:
            return "unhealthy"

    async def redis() -> str:
        try:
            client = await get_redis()
            await client.ping()
            return "healthy"
        except Exception:
            return "unhealthy"

    async def ollama() -> str:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            return "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            return "unhealthy"

    async def dropbox() -> str:
        from app.services.dropbox_auth import dropbox_request, token_provider

        if not token_provider.configured:
            return "unconfigured"
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await dropbox_request(
                    client,
                    "POST",
                    "https://api.dropboxapi.com/2/users/get_current_account",
                )
            return "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            return "unhealthy"

    values = await asyncio.gather(database(), redis(), ollama(), dropbox())
    return dict(zip(("database", "redis", "ollama", "dropbox"), values))


@router.get("/")
async def health_check():
    """Basic health check — always public."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/services")
async def service_status(current_user=Depends(require_admin_rest)):
    """Live dependency indicators for the authenticated admin test console."""
    return {
        "services": await _dependency_statuses(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db")
async def database_health(
    request: Request,
    api_key=Depends(require_api_key) if _is_prod() else Depends(lambda: True),
):
    """Check database connectivity.

    In production, requires an API key and never leaks ``str(e)``.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "database",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=_redacted_or_detail(str(e)),
        )


@router.get("/redis")
async def redis_health(
    request: Request,
    api_key=Depends(require_api_key) if _is_prod() else Depends(lambda: True),
):
    """Check Redis connectivity.

    In production, requires an API key and never leaks ``str(e)``.
    """
    try:
        redis = await get_redis()
        await redis.ping()
        return {
            "status": "healthy",
            "service": "redis",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=_redacted_or_detail(str(e)),
        )


@router.get("/ollama")
async def ollama_health(
    request: Request,
    api_key=Depends(require_api_key) if _is_prod() else Depends(lambda: True),
):
    """Check Ollama connectivity.

    In production, requires an API key and does not return the model list.
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                body = {
                    "status": "healthy",
                    "service": "ollama",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                # Only expose model names in non-prod
                if not _is_prod():
                    body["models"] = [m.get("name") for m in response.json().get("models", [])]
                return body
            raise Exception(f"Ollama returned status {response.status_code}")
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=_redacted_or_detail(str(e)),
        )


@router.get("/qdrant")
async def qdrant_health(
    request: Request,
    api_key=Depends(require_api_key) if _is_prod() else Depends(lambda: True),
):
    """Check Qdrant connectivity.

    In production, requires an API key and never leaks ``str(e)``.
    """
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        collections = client.get_collections()
        body = {
            "status": "healthy",
            "service": "qdrant",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not _is_prod():
            body["collections"] = [c.name for c in collections.collections]
        return body
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=_redacted_or_detail(str(e)),
        )


@router.get("/all")
async def full_health_check(
    request: Request,
    api_key=Depends(require_api_key) if _is_prod() else Depends(lambda: True),
):
    """Run all health checks.

    In production, requires an API key and returns only status strings.
    """
    results: dict[str, str] = {
        "api": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "ollama": "unknown",
        "qdrant": "unknown",
    }

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        results["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        results["database"] = "unhealthy" if _is_prod() else f"unhealthy: {e}"

    try:
        redis = await get_redis()
        await redis.ping()
        results["redis"] = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        results["redis"] = "unhealthy" if _is_prod() else f"unhealthy: {e}"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            results["ollama"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        results["ollama"] = "unhealthy" if _is_prod() else f"unhealthy: {e}"

    try:
        from qdrant_client import QdrantClient

        qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        qdrant_client.get_collections()
        results["qdrant"] = "healthy"
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        results["qdrant"] = "unhealthy" if _is_prod() else f"unhealthy: {e}"

    all_healthy = all(v == "healthy" for v in results.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
