from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.dropbox.com/oauth2/token"

# Dropbox access tokens live ~4 hours.  Renew a little early so a token can
# never lapse midway through an in-flight request.
EXPIRY_SKEW_SECONDS = 300
DEFAULT_EXPIRES_IN = 14400


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
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": settings.DROPBOX_REFRESH_TOKEN,
                    },
                    auth=(settings.DROPBOX_APP_KEY, settings.DROPBOX_APP_SECRET),
                    timeout=30.0,
                )
        except httpx.HTTPError as exc:
            raise DropboxAuthError(f"Dropbox token refresh unreachable: {exc}") from exc

        if response.status_code != 200:
            # The body can echo credentials, so only the status and Dropbox's
            # short error tag are logged.
            tag = ""
            try:
                tag = str(response.json().get("error", ""))[:100]
            except ValueError:
                pass
            if response.status_code == 400:
                logger.error(
                    "Dropbox refresh token rejected (%s). It may have been "
                    "revoked; re-run the one-time authorisation. %s",
                    response.status_code,
                    tag,
                )
            raise DropboxAuthError(
                f"Dropbox token refresh failed ({response.status_code}) {tag}"
            )

        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise DropboxAuthError("Dropbox token refresh returned no access_token")

        expires_in = payload.get("expires_in") or DEFAULT_EXPIRES_IN
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
