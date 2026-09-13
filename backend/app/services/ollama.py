from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0
REQUEST_TIMEOUT = 120.0
MODEL_LOAD_TIMEOUT = 30.0
MAX_OLLAMA_RESPONSE_BYTES = 1_000_000


def _check_content_length(response: httpx.Response) -> None:
    content_length = response.headers.get("content-length")
    if content_length is None:
        return
    try:
        declared_length = int(content_length)
    except ValueError:
        return
    if declared_length > MAX_OLLAMA_RESPONSE_BYTES:
        raise ValueError("Ollama response is too large")


async def _read_json_response(response: httpx.Response) -> dict[str, Any]:
    """Read and parse a provider response without unbounded buffering."""
    response.raise_for_status()
    _check_content_length(response)
    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in response.aiter_bytes():
        total_bytes += len(chunk)
        if total_bytes > MAX_OLLAMA_RESPONSE_BYTES:
            raise ValueError("Ollama response is too large")
        chunks.append(chunk)
    body = json.loads(b"".join(chunks))
    if not isinstance(body, dict):
        raise ValueError(f"Ollama returned non-object JSON: {type(body)}")
    return body


def _read_json_response_sync(response: httpx.Response) -> dict[str, Any]:
    """Synchronous counterpart to :func:`_read_json_response`."""
    response.raise_for_status()
    _check_content_length(response)
    chunks: list[bytes] = []
    total_bytes = 0
    for chunk in response.iter_bytes():
        total_bytes += len(chunk)
        if total_bytes > MAX_OLLAMA_RESPONSE_BYTES:
            raise ValueError("Ollama response is too large")
        chunks.append(chunk)
    body = json.loads(b"".join(chunks))
    if not isinstance(body, dict):
        raise ValueError(f"Ollama returned non-object JSON: {type(body)}")
    return body


class OllamaClient:
    """Client for Ollama LLM inference with model swapping and retry logic."""

    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.extraction_model = getattr(
            settings, "OLLAMA_EXTRACTION_MODEL", "llama3.1:8b-instruct-q4_K_M"
        )
        self.vision_model = getattr(
            settings, "OLLAMA_VISION_MODEL", "llama3.2-11b-vision-instruct-q4_K_M"
        )
        self.report_model = getattr(
            settings, "OLLAMA_EXTRACTION_MODEL", "llama3.1:8b-instruct-q4_K_M"
        )

    async def extract(
        self,
        prompt: str,
        model: str | None = None,
        images: list[str] | None = None,
        json_format: bool = True,
    ) -> dict[str, Any]:
        """Run inference on Ollama with retry logic.

        json_format=True (default) constrains Ollama's decoding to valid
        JSON — needed for structured extraction/classification callers.
        Pass json_format=False for narrative-prose responses (e.g. crew
        summaries): with the constraint on, the model still emits valid
        JSON as instructed, but wraps whatever prose it wanted to write in
        an object like {"profile": "..."} rather than writing plain text,
        regardless of what the prompt asks for — the constraint operates
        below the prompt, at the token-sampling level.
        """
        from asyncio import sleep

        selected_model = model or self.extraction_model
        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
        }
        if json_format:
            payload["format"] = "json"
        if images:
            payload["images"] = images

        last_exception: BaseException | None = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    request = client.build_request(
                        "POST", f"{self.base_url}/api/generate", json=payload
                    )
                    response = await client.send(request, stream=True)
                    try:
                        return await _read_json_response(response)
                    finally:
                        await response.aclose()
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(
                    "Ollama timeout (attempt %s/%s, %s)",
                    attempt + 1,
                    MAX_RETRIES,
                    type(e).__name__,
                )
                if attempt < MAX_RETRIES - 1:
                    await sleep(RETRY_BACKOFF_FACTOR**attempt)
            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.warning(
                    "Ollama HTTP error (attempt %s/%s, %s)",
                    attempt + 1,
                    MAX_RETRIES,
                    type(e).__name__,
                )
                if e.response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    await sleep(RETRY_BACKOFF_FACTOR**attempt)
                else:
                    raise
            except Exception as e:
                last_exception = e
                logger.error("Ollama unexpected error (%s)", type(e).__name__)
                raise

        raise last_exception or Exception("Max retries exceeded")

    async def load_model(self, model_name: str) -> bool:
        """Load a model into VRAM."""
        async with httpx.AsyncClient(timeout=MODEL_LOAD_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={"model": model_name, "keep_alive": -1},
            ) as response:
                return response.status_code == 200

    async def unload_model(self, model_name: str) -> bool:
        """Unload a model from VRAM."""
        async with httpx.AsyncClient(timeout=MODEL_LOAD_TIMEOUT) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/generate",
                json={"model": model_name, "keep_alive": 0},
            ) as response:
                return response.status_code == 200

    def extract_sync(
        self,
        prompt: str,
        model: str | None = None,
        images: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run inference on Ollama synchronously (for Celery tasks) with retry logic."""
        from time import sleep

        selected_model = model or self.extraction_model
        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        if images:
            payload["images"] = images

        last_exception: BaseException | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                    request = client.build_request(
                        "POST", f"{self.base_url}/api/generate", json=payload
                    )
                    response = client.send(request, stream=True)
                    try:
                        return _read_json_response_sync(response)
                    finally:
                        response.close()
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(
                    "Ollama timeout (attempt %s/%s, %s)",
                    attempt + 1,
                    MAX_RETRIES,
                    type(e).__name__,
                )
                if attempt < MAX_RETRIES - 1:
                    sleep(RETRY_BACKOFF_FACTOR**attempt)
            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.warning(
                    "Ollama HTTP error (attempt %s/%s, %s)",
                    attempt + 1,
                    MAX_RETRIES,
                    type(e).__name__,
                )
                if e.response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    sleep(RETRY_BACKOFF_FACTOR**attempt)
                else:
                    raise
            except Exception as e:
                last_exception = e
                logger.error("Ollama unexpected error (%s)", type(e).__name__)
                raise

        raise last_exception or Exception("Max retries exceeded")


ollama_client = OllamaClient()
