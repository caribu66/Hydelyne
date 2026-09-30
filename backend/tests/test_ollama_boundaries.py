"""Regression tests for bounded Ollama provider responses."""

import pytest


class _StreamResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class _StreamClient:
    def __init__(self):
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    def stream(self, method: str, url: str, **kwargs: object):
        self.calls.append((method, url, kwargs))
        return _StreamResponse()


class _AsyncResponse:
    headers = {}

    def raise_for_status(self):
        return None

    async def aiter_bytes(self):
        yield b"{" + b'"response":"' + (b"x" * 1_000_001) + b'"}'

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_async_ollama_response_is_bounded_before_json_parsing():
    from app.services.ollama import _read_json_response

    with pytest.raises(ValueError, match="too large"):
        await _read_json_response(_AsyncResponse())


@pytest.mark.asyncio
async def test_model_lifecycle_requests_stream_and_close_provider_response(monkeypatch):
    import app.services.ollama as ollama

    client = _StreamClient()
    monkeypatch.setattr(ollama.httpx, "AsyncClient", lambda **kwargs: client)
    ollama_client = ollama.OllamaClient()

    assert await ollama_client.load_model("model-a") is True
    assert await ollama_client.unload_model("model-a") is True
    assert [call[0] for call in client.calls] == ["POST", "POST"]
    assert client.calls[0][2]["json"] == {"model": "model-a", "keep_alive": -1}
    assert client.calls[1][2]["json"] == {"model": "model-a", "keep_alive": 0}
