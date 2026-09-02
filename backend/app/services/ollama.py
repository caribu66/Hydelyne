from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2.0
REQUEST_TIMEOUT = 120.0
MODEL_LOAD_TIMEOUT = 30.0


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

        import httpx

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
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                    )
                    response.raise_for_status()
                    body = response.json()
                    if not isinstance(body, dict):
                        raise ValueError(f"Ollama returned non-object JSON: {type(body)}")
                    return body
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"Ollama timeout (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await sleep(RETRY_BACKOFF_FACTOR**attempt)
            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.warning(f"Ollama HTTP error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if e.response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    await sleep(RETRY_BACKOFF_FACTOR**attempt)
                else:
                    raise
            except Exception as e:
                last_exception = e
                logger.error(f"Ollama unexpected error: {e}")
                raise

        raise last_exception or Exception("Max retries exceeded")

    async def load_model(self, model_name: str) -> bool:
        """Load a model into VRAM."""
        import httpx

        async with httpx.AsyncClient(timeout=MODEL_LOAD_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": model_name, "keep_alive": -1},
            )
            return response.status_code == 200

    async def unload_model(self, model_name: str) -> bool:
        """Unload a model from VRAM."""
        import httpx

        async with httpx.AsyncClient(timeout=MODEL_LOAD_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": model_name, "keep_alive": 0},
            )
            return response.status_code == 200

    def extract_sync(
        self,
        prompt: str,
        model: str | None = None,
        images: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run inference on Ollama synchronously (for Celery tasks) with retry logic."""
        from time import sleep

        import httpx

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
                    response = client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                    )
                    response.raise_for_status()
                    body = response.json()
                    if not isinstance(body, dict):
                        raise ValueError(f"Ollama returned non-object JSON: {type(body)}")
                    return body
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(f"Ollama timeout (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    sleep(RETRY_BACKOFF_FACTOR**attempt)
            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.warning(f"Ollama HTTP error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if e.response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    sleep(RETRY_BACKOFF_FACTOR**attempt)
                else:
                    raise
            except Exception as e:
                last_exception = e
                logger.error(f"Ollama unexpected error: {e}")
                raise

        raise last_exception or Exception("Max retries exceeded")


ollama_client = OllamaClient()
