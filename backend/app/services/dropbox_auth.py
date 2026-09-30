from __future__ import annotations

import asyncio
import json
import logging
import math
from typing import Any, Optional

import httpx
from httpx import BasicAuth

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Dropbox OAuth token endpoint URL, not a credential.
TOKEN_URL = "https://api.dropbox.com/oauth2/token"  # nosec B105

# Dropbox access tokens live ~4 hours.  Renew a little early so a token can
# never lapse midway through an in-flight request.
EXPIRY_SKEW_SECONDS = 300
DEFAULT_EXPIRES_IN = 14400
MAX_DROPBOX_TOKEN_RESPONSE_BYTES = 64 * 1024
MAX_DROPBOX_JSON_RESPONSE_BYTES = 512 * 1024


class DropboxAuthError(RuntimeError):
    """Raised when no usable Dropbox access token can be obtained."""


class DropboxTokenProvider:
    """Supplies a valid Dropbox access token, refreshing it when it expires.

    Dropbox no longer issues long-lived tokens: an ``sl.`` access token stops
    working after about four hours.  When a refresh token is configured this
    exchanges it for a fresh access token and caches that until shortly before
    it lapses, so the credential in the environment never needs replacing by
    hand.

    With no refresh token configured it falls back to the static
    ``DROPBOX_ACCESS_TOKEN``, preserving the previous behaviour.
    """

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def can_refresh(self) -> bool:
        """True when a refresh token and app credentials are all present."""
        return bool(
            settings.DROPBOX_REFRESH_TOKEN
            and settings.DROPBOX_APP_KEY
            and settings.DROPBOX_APP_SECRET
        )

    @property
    def configured(self) -> bool:
        """True when some credential exists, refreshable or not."""
        return bool(self.can_refresh or settings.DROPBOX_ACCESS_TOKEN)

    def _get_lock(self) -> asyncio.Lock:
        """Return a lock bound to the running loop.

        ``DocumentUploadService`` has a synchronous download path that spins up
        its own event loop, so the provider can legitimately be awaited from
        more than one loop over a process lifetime.  A lock bound to a retired
        loop would raise, so it is rebuilt whenever the loop changes.
        """
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    def _cached_token(self) -> Optional[str]:
        if not self._access_token:
            return None
        loop = asyncio.get_running_loop()
        if loop.time() >= self._expires_at:
            return None
        return self._access_token

    async def get_token(self, force_refresh: bool = False) -> str:
        """Return a usable access token, refreshing it if necessary.

        Raises ``DropboxAuthError`` when Dropbox is unconfigured or the refresh
        exchange fails.
        """
        if not self.can_refresh:
            if settings.DROPBOX_ACCESS_TOKEN:
                return settings.DROPBOX_ACCESS_TOKEN
            raise DropboxAuthError("Dropbox is not configured")

        if not force_refresh:
            cached = self._cached_token()
            if cached:
                return cached

        async with self._get_lock():
            # Another caller may have refreshed while this one waited.
            if not force_refresh:
                cached = self._cached_token()
                if cached:
                    return cached
            return await self._refresh()

    async def _refresh(self) -> str:
        """Exchange the refresh token for a new access token."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                request = client.build_request(
                    "POST",
                    TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": settings.DROPBOX_REFRESH_TOKEN,
                    },
                    timeout=30.0,
                )
                request = next(
                    BasicAuth(
                        settings.DROPBOX_APP_KEY,
                        settings.DROPBOX_APP_SECRET,
                    ).auth_flow(request)
                )
                response = await client.send(request, stream=True)
                try:
                    if response.status_code != 200:
                        # Provider bodies can echo credentials or request-specific data;
                        # keep this boundary to the status code only.
                        if response.status_code == 400:
                            logger.error(
                                "Dropbox refresh token rejected (%s). It may have been "
                                "revoked; re-run the one-time authorisation.",
                                response.status_code,
                            )
                        raise DropboxAuthError(
                            f"Dropbox token refresh failed ({response.status_code})"
                        )
                    payload = await _read_bounded_json(
                        response, max_bytes=MAX_DROPBOX_TOKEN_RESPONSE_BYTES
                    )
                finally:
                    await response.aclose()
        except httpx.HTTPError as exc:
            # Transport exceptions can include the configured URL or request
            # details. Keep the public error safe while preserving chaining
            # for internal diagnostics.
            raise DropboxAuthError("Dropbox token refresh unreachable") from exc

        if payload is None or not isinstance(payload, dict):
            raise DropboxAuthError("Dropbox token refresh returned an invalid payload")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise DropboxAuthError("Dropbox token refresh returned no access_token")

        raw_expires_in = payload.get("expires_in")
        expires_in = (
            raw_expires_in
            if isinstance(raw_expires_in, (int, float))
            and not isinstance(raw_expires_in, bool)
            and math.isfinite(float(raw_expires_in))
            and raw_expires_in > 0
            else DEFAULT_EXPIRES_IN
        )
        loop = asyncio.get_running_loop()
        self._access_token = token
        self._expires_at = loop.time() + max(expires_in - EXPIRY_SKEW_SECONDS, 60)
        logger.info("Refreshed Dropbox access token (expires in %ss)", expires_in)
        return token

    def invalidate(self) -> None:
        """Drop the cached token so the next call refreshes."""
        self._access_token = None
        self._expires_at = 0.0


token_provider = DropboxTokenProvider()


async def _read_bounded_json(
    response: httpx.Response,
    *,
    max_bytes: int,
) -> object | None:
    """Read one provider JSON response without unbounded buffering."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                return None
        except ValueError:
            pass
    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in response.aiter_bytes():
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            return None
        chunks.append(chunk)
    try:
        payload: object = json.loads(b"".join(chunks))
        return payload
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


async def dropbox_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    **kwargs: Any,
) -> httpx.Response:
    """Call a Dropbox endpoint with a managed token, retrying once on 401.

    A token can still lapse between the expiry check and Dropbox seeing it, so
    a 401 triggers one forced refresh and a single replay of the request.
    """
    token = await token_provider.get_token()
    request_headers = dict(headers or {})
    request_headers["Authorization"] = f"Bearer {token}"

    response = await client.request(method, url, headers=request_headers, **kwargs)

    if response.status_code == 401 and token_provider.can_refresh:
        logger.info("Dropbox returned 401; refreshing access token and retrying")
        token = await token_provider.get_token(force_refresh=True)
        request_headers["Authorization"] = f"Bearer {token}"
        response = await client.request(method, url, headers=request_headers, **kwargs)

    return response


async def dropbox_request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    max_bytes: int = MAX_DROPBOX_JSON_RESPONSE_BYTES,
    **kwargs: Any,
) -> tuple[int, dict[str, Any] | None]:
    """Request a Dropbox JSON payload with bounded streaming and token retry."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")

    async def _request(token: str) -> tuple[int, dict[str, Any] | None]:
        request_headers = dict(headers or {})
        request_headers["Authorization"] = f"Bearer {token}"
        request = client.build_request(method, url, headers=request_headers, **kwargs)
        response = await client.send(request, stream=True)
        try:
            if response.status_code != 200:
                return response.status_code, None
            payload = await _read_bounded_json(response, max_bytes=max_bytes)
            return response.status_code, payload if isinstance(payload, dict) else None
        finally:
            await response.aclose()

    token = await token_provider.get_token()
    status_code, payload = await _request(token)
    if status_code == 401 and token_provider.can_refresh:
        logger.info("Dropbox returned 401; refreshing token for bounded JSON request")
        token = await token_provider.get_token(force_refresh=True)
        status_code, payload = await _request(token)
    return status_code, payload


async def dropbox_request_status(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: Optional[dict[str, str]] = None,
    **kwargs: Any,
) -> int:
    """Call a Dropbox endpoint without buffering an unused response body."""

    async def _request(token: str) -> int:
        request_headers = dict(headers or {})
        request_headers["Authorization"] = f"Bearer {token}"
        request = client.build_request(method, url, headers=request_headers, **kwargs)
        response = await client.send(request, stream=True)
        try:
            return response.status_code
        finally:
            await response.aclose()

    token = await token_provider.get_token()
    status_code = await _request(token)
    if status_code == 401 and token_provider.can_refresh:
        logger.info("Dropbox returned 401; refreshing token for status request")
        token = await token_provider.get_token(force_refresh=True)
        status_code = await _request(token)
    return status_code


async def download_dropbox_content(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    max_bytes: int,
    headers: Optional[dict[str, str]] = None,
    **kwargs: Any,
) -> tuple[int, bytes | None]:
    """Download a Dropbox response without buffering beyond ``max_bytes``."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")

    async def _download(token: str) -> tuple[int, bytes | None]:
        request_headers = dict(headers or {})
        request_headers["Authorization"] = f"Bearer {token}"
        request = client.build_request(method, url, headers=request_headers, **kwargs)
        response = await client.send(request, stream=True)
        try:
            if response.status_code != 200:
                return response.status_code, None
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > max_bytes:
                        return response.status_code, None
                except ValueError:
                    pass
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    return response.status_code, None
                chunks.append(chunk)
            return response.status_code, b"".join(chunks)
        finally:
            await response.aclose()

    token = await token_provider.get_token()
    status_code, content = await _download(token)
    if status_code == 401 and token_provider.can_refresh:
        logger.info("Dropbox returned 401; refreshing token for bounded download")
        token = await token_provider.get_token(force_refresh=True)
        status_code, content = await _download(token)
    return status_code, content
