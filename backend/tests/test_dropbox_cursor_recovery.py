from unittest.mock import AsyncMock, patch

import pytest

from app.api.dropbox import (
    DropboxCursorUnavailable,
    continue_dropbox_listing,
    process_dropbox_account,
)


class _AsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_expired_dropbox_cursor_restarts_full_listing(monkeypatch):
    monkeypatch.setattr("app.api.dropbox.settings.DROPBOX_ACCESS_TOKEN", "test-token")

    with (
        patch("app.api.dropbox.httpx.AsyncClient", return_value=_AsyncClient()),
        patch("app.api.dropbox.dropbox_request_json", new=AsyncMock(return_value=(409, {}))),
        patch("app.api.dropbox.start_dropbox_listing", new=AsyncMock()) as restart,
    ):
        await continue_dropbox_listing("account-1", "expired-cursor")

    restart.assert_awaited_once_with("account-1")


@pytest.mark.asyncio
async def test_cursor_store_failure_does_not_start_full_listing(monkeypatch):
    monkeypatch.setattr(
        "app.api.dropbox.get_dropbox_cursor",
        AsyncMock(side_effect=DropboxCursorUnavailable),
    )

    with patch("app.api.dropbox.start_dropbox_listing", new=AsyncMock()) as start:
        await process_dropbox_account("account-1")

    start.assert_not_awaited()
