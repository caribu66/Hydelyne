"""Tests for Dropbox access-token refresh handling."""
import httpx
import pytest

from app.services import dropbox_auth
from app.services.dropbox_auth import (
    DropboxAuthError,
    DropboxTokenProvider,
    dropbox_request,
)


@pytest.fixture
def creds(monkeypatch):
    """Configure a refreshable Dropbox credential set."""
    settings = dropbox_auth.settings
    monkeypatch.setattr(settings, "DROPBOX_APP_KEY", "app-key", raising=False)
    monkeypatch.setattr(settings, "DROPBOX_APP_SECRET", "app-secret", raising=False)
    monkeypatch.setattr(settings, "DROPBOX_REFRESH_TOKEN", "refresh-tok", raising=False)
    monkeypatch.setattr(settings, "DROPBOX_ACCESS_TOKEN", "", raising=False)
    return settings


def _token_transport(calls, tokens=("access-1", "access-2"), expires_in=14400):
    """Mock transport that mints a new access token per refresh call."""
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        issued = tokens[min(len(calls) - 1, len(tokens) - 1)]
        return httpx.Response(
            200, json={"access_token": issued, "token_type": "bearer", "expires_in": expires_in}
        )
    return httpx.MockTransport(handler)


def _patch_refresh_transport(monkeypatch, transport):
    """Point only dropbox_auth's httpx at *transport*.

    Patching the shared httpx module would also hijack the mock clients the
    tests build for the API side, so a shim is bound to the module's own
    ``httpx`` name instead.
    """
    class _HttpxShim:
        HTTPError = httpx.HTTPError

        @staticmethod
        def AsyncClient(**kwargs):
            kwargs.pop("transport", None)
            return httpx.AsyncClient(transport=transport, **kwargs)

    monkeypatch.setattr(dropbox_auth, "httpx", _HttpxShim)



@pytest.mark.asyncio
async def test_static_token_used_when_no_refresh_token(monkeypatch):
    """Without a refresh token the legacy static token still works."""
    settings = dropbox_auth.settings
    monkeypatch.setattr(settings, "DROPBOX_REFRESH_TOKEN", "", raising=False)
    monkeypatch.setattr(settings, "DROPBOX_ACCESS_TOKEN", "sl.static", raising=False)

    provider = DropboxTokenProvider()
    assert provider.configured is True
    assert provider.can_refresh is False
    assert await provider.get_token() == "sl.static"


@pytest.mark.asyncio
async def test_unconfigured_raises(monkeypatch):
    settings = dropbox_auth.settings
    monkeypatch.setattr(settings, "DROPBOX_REFRESH_TOKEN", "", raising=False)
    monkeypatch.setattr(settings, "DROPBOX_ACCESS_TOKEN", "", raising=False)

    provider = DropboxTokenProvider()
    assert provider.configured is False
    with pytest.raises(DropboxAuthError):
        await provider.get_token()


@pytest.mark.asyncio
async def test_refresh_token_exchanged_and_cached(creds, monkeypatch):
    """The refresh token buys an access token, reused until it nears expiry."""
    calls = []
    transport = _token_transport(calls)
    _patch_refresh_transport(monkeypatch, transport)

    provider = DropboxTokenProvider()
    assert provider.can_refresh is True

    assert await provider.get_token() == "access-1"
    assert len(calls) == 1

    # Second call is served from cache, not a second network round trip.
    assert await provider.get_token() == "access-1"
    assert len(calls) == 1

    # Basic auth carries the app key/secret; the refresh token is in the body.
    assert calls[0].headers["authorization"].startswith("Basic ")
    assert b"grant_type=refresh_token" in calls[0].content


@pytest.mark.asyncio
async def test_expired_cache_triggers_refresh(creds, monkeypatch):
    """A token past its skew-adjusted expiry is replaced, not reused."""
    calls = []
    transport = _token_transport(calls)
    _patch_refresh_transport(monkeypatch, transport)

    provider = DropboxTokenProvider()
    assert await provider.get_token() == "access-1"

    provider._expires_at = 0.0  # simulate the four hours elapsing
    assert await provider.get_token() == "access-2"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_refresh_failure_raises(creds, monkeypatch):
    """A revoked refresh token surfaces as DropboxAuthError, not a 200."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    transport = httpx.MockTransport(handler)
    _patch_refresh_transport(monkeypatch, transport)

    provider = DropboxTokenProvider()
    with pytest.raises(DropboxAuthError):
        await provider.get_token()


@pytest.mark.asyncio
async def test_dropbox_request_retries_once_on_401(creds, monkeypatch):
    """An expired token mid-flight is refreshed and the request replayed."""
    refresh_calls = []
    transport = _token_transport(refresh_calls)
    _patch_refresh_transport(monkeypatch, transport)

    provider = DropboxTokenProvider()
    monkeypatch.setattr(dropbox_auth, "token_provider", provider)

    seen = []

    def api_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        if len(seen) == 1:
            return httpx.Response(401, json={"error": {".tag": "expired_access_token"}})
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(api_handler)) as client:
        response = await dropbox_request(
            client, "POST", "https://api.dropboxapi.com/2/files/list_folder"
        )

    assert response.status_code == 200
    assert seen == ["Bearer access-1", "Bearer access-2"]
    assert len(refresh_calls) == 2


@pytest.mark.asyncio
async def test_dropbox_request_no_retry_without_refresh(monkeypatch):
    """A static-token deployment must not loop on 401."""
    settings = dropbox_auth.settings
    monkeypatch.setattr(settings, "DROPBOX_REFRESH_TOKEN", "", raising=False)
    monkeypatch.setattr(settings, "DROPBOX_ACCESS_TOKEN", "sl.expired", raising=False)

    provider = DropboxTokenProvider()
    monkeypatch.setattr(dropbox_auth, "token_provider", provider)

    seen = []

    def api_handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        return httpx.Response(401, json={"error": {".tag": "expired_access_token"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(api_handler)) as client:
        response = await dropbox_request(
            client, "POST", "https://api.dropboxapi.com/2/files/list_folder"
        )

    assert response.status_code == 401
    assert seen == ["Bearer sl.expired"]
