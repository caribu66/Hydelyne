import pytest
from fastapi import HTTPException

from app.api.health import _read_ollama_health_json, _readiness_response


class _OversizedHealthResponse:
    headers = {}

    async def aiter_bytes(self):
        yield b"{" + b"x" * (256 * 1024 + 1) + b"}"


def test_readiness_returns_503_when_a_dependency_is_unhealthy() -> None:
    with pytest.raises(HTTPException) as raised:
        _readiness_response({"api": "healthy", "database": "unhealthy"})

    assert raised.value.status_code == 503
    assert raised.value.detail["status"] == "degraded"
    assert raised.value.detail["services"]["database"] == "unhealthy"


def test_readiness_returns_data_when_all_dependencies_are_healthy() -> None:
    response = _readiness_response({"api": "healthy", "database": "healthy"})

    assert response["status"] == "healthy"
    assert response["services"]["database"] == "healthy"


@pytest.mark.asyncio
async def test_ollama_health_payload_is_bounded_before_json_parsing() -> None:
    assert await _read_ollama_health_json(_OversizedHealthResponse()) is None
