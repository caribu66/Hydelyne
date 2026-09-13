from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import seeds


@pytest.mark.asyncio
async def test_seed_main_does_not_log_bootstrap_password(caplog):
    settings = SimpleNamespace(APP_ENV="development")
    ops = SimpleNamespace(role="user")

    with (
        patch("app.config.get_settings", return_value=settings),
        patch("app.seeds.get_engine") as get_engine,
        patch("app.seeds.seed_all", new=AsyncMock(return_value=0)),
        patch("app.seeds.bootstrap_admin", new=AsyncMock(return_value=True)),
        patch("app.seeds.seed_user", new=AsyncMock(return_value=ops)),
    ):
        engine = get_engine.return_value
        connection = SimpleNamespace(run_sync=AsyncMock())
        transaction = SimpleNamespace(
            __aenter__=AsyncMock(return_value=connection),
            __aexit__=AsyncMock(return_value=False),
        )
        engine.begin = MagicMock(return_value=transaction)

        await seeds.main()

    assert "OpsPass_123!x" not in caplog.text
    assert "ops@hydenlyne.com" not in caplog.text
