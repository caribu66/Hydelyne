from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text

from app.auth.decorators import require_admin_rest, require_api_key
from app.config import get_settings
from app.database import get_engine
from app.models import CrewMember
from app.services.cache import get_redis
from app.services.qdrant import QDRANT_REQUEST_TIMEOUT_SECONDS

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])
MAX_OLLAMA_HEALTH_RESPONSE_BYTES = 256 * 1024


async def _read_ollama_health_json(
    response: httpx.Response,
) -> dict[str, Any] | None:
    """Read the optional model-list response without unbounded buffering."""
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_OLLAMA_HEALTH_RESPONSE_BYTES:
                return None
        except ValueError:
            pass
    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in response.aiter_bytes():
        total_bytes += len(chunk)
        if total_bytes > MAX_OLLAMA_HEALTH_RESPONSE_BYTES:
            return None
        chunks.append(chunk)
    try:
        payload = json.loads(b"".join(chunks))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _is_prod() -> bool:
    return settings.APP_ENV == "production"


def _redacted_or_detail(detail: str) -> dict[str, str]:
    """Return a safe health failure response in every environment.

    These endpoints are public in development and may still be reachable
    through an accidentally exposed dev deployment. Exception text can carry
    database URLs, Redis credentials, or internal hostnames.
    """
    return {"status": "unhealthy", "detail": "Service temporarily unavailable"}


def _readiness_response(results: dict[str, str]) -> dict[str, Any]:
    """Return readiness data, using a non-2xx status when dependencies fail."""
    response: dict[str, Any] = {
        "status": "healthy" if all(value == "healthy" for value in results.values()) else "degraded",
        "services": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if response["status"] != "healthy":
        raise HTTPException(status_code=503, detail=response)
    return response


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
            async with httpx.AsyncClient(timeout=5.0) as client:
                async with client.stream(
                    "GET", f"{settings.OLLAMA_BASE_URL}/api/tags"
                ) as response:
                    return "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            return "unhealthy"

    async def dropbox() -> str:
        from app.services.dropbox_auth import dropbox_request_status, token_provider

        if not token_provider.configured:
            return "unconfigured"
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                status_code = await dropbox_request_status(
                    client,
                    "POST",
                    "https://api.dropboxapi.com/2/users/get_current_account",
                )
            return "healthy" if status_code == 200 else "unhealthy"
        except Exception:
            return "unhealthy"

    values = await asyncio.gather(database(), redis(), ollama(), dropbox())
    return dict(zip(("database", "redis", "ollama", "dropbox"), values))


@router.get("/")
async def health_check() -> dict[str, Any]:
    """Basic health check — always public."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/services")
async def service_status(current_user: CrewMember = Depends(require_admin_rest)) -> dict[str, Any]:
    """Live dependency indicators for the authenticated admin test console."""
    return {
        "services": await _dependency_statuses(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db")
async def database_health(
    request: Request,
    api_key: bool = Depends(require_api_key) if _is_prod() else Depends(lambda: True),
) -> dict[str, Any]:
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
        logger.error("Database health check failed (%s)", type(e).__name__)
        raise HTTPException(
            status_code=503,
            detail=_redacted_or_detail(str(e)),
        )


@router.get("/redis")
async def redis_health(
    request: Request,
    api_key: bool = Depends(require_api_key) if _is_prod() else Depends(lambda: True),
) -> dict[str, Any]:
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
        logger.error("Redis health check failed (%s)", type(e).__name__)
        raise HTTPException(
            status_code=503,
            detail=_redacted_or_detail(str(e)),
        )


@router.get("/ollama")
async def ollama_health(
    request: Request,
    api_key: bool = Depends(require_api_key) if _is_prod() else Depends(lambda: True),
) -> dict[str, Any]:
    """Check Ollama connectivity.

    In production, requires an API key and does not return the model list.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            req = client.build_request("GET", f"{settings.OLLAMA_BASE_URL}/api/tags")
            response = await client.send(req, stream=True)
            try:
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama returned status {response.status_code}")
                body: dict[str, Any] = {
                    "status": "healthy",
                    "service": "ollama",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                # Only expose model names in non-prod.
                if not _is_prod():
                    payload = await _read_ollama_health_json(response)
                    if payload is None:
                        raise RuntimeError("Ollama returned invalid health payload")
                    models = payload.get("models", [])
                    body["models"] = [
                        model.get("name")
                        for model in models
                        if isinstance(model, dict) and isinstance(model.get("name"), str)
                    ] if isinstance(models, list) else []
                return body
            finally:
                await response.aclose()
    except Exception as e:
        logger.error("Ollama health check failed (%s)", type(e).__name__)
        raise HTTPException(
            status_code=503,
            detail=_redacted_or_detail(str(e)),
        )


@router.get("/qdrant")
async def qdrant_health(
    request: Request,
    api_key: bool = Depends(require_api_key) if _is_prod() else Depends(lambda: True),
) -> dict[str, Any]:
    """Check Qdrant connectivity.

    In production, requires an API key and never leaks ``str(e)``.
    """
    try:
        from qdrant_client import QdrantClient

        def _get_collection_names() -> list[str]:
            client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=QDRANT_REQUEST_TIMEOUT_SECONDS,
            )
            return [item.name for item in client.get_collections().collections]

        collection_names = await asyncio.to_thread(_get_collection_names)
        body: dict[str, Any] = {
            "status": "healthy",
            "service": "qdrant",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if not _is_prod():
            body["collections"] = collection_names
        return body
    except Exception as e:
        logger.error("Qdrant health check failed (%s)", type(e).__name__)
        raise HTTPException(
            status_code=503,
            detail=_redacted_or_detail(str(e)),
        )


@router.get("/all")
async def full_health_check(
    request: Request,
    api_key: bool = Depends(require_api_key) if _is_prod() else Depends(lambda: True),
) -> dict[str, Any]:
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
        logger.error("Database health check failed (%s)", type(e).__name__)
        results["database"] = "unhealthy"

    try:
        redis = await get_redis()
        await redis.ping()
        results["redis"] = "healthy"
    except Exception as e:
        logger.error("Redis health check failed (%s)", type(e).__name__)
        results["redis"] = "unhealthy"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            async with client.stream(
                "GET", f"{settings.OLLAMA_BASE_URL}/api/tags"
            ) as response:
                results["ollama"] = "healthy" if response.status_code == 200 else "unhealthy"
    except Exception as e:
        logger.error("Ollama health check failed (%s)", type(e).__name__)
        results["ollama"] = "unhealthy"

    try:
        from qdrant_client import QdrantClient

        def _probe_qdrant() -> None:
            qdrant_client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=QDRANT_REQUEST_TIMEOUT_SECONDS,
            )
            qdrant_client.get_collections()

        await asyncio.to_thread(_probe_qdrant)
        results["qdrant"] = "healthy"
    except Exception as e:
        logger.error("Qdrant health check failed (%s)", type(e).__name__)
        results["qdrant"] = "unhealthy"

    return _readiness_response(results)
