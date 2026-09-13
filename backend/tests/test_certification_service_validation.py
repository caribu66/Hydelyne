from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.crew import certification_service


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


@pytest.mark.asyncio
async def test_update_certification_rejects_login_account_owner(monkeypatch):
    session = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _Result("staff-1"),
                _Result(SimpleNamespace(password_hash="hashed", role="staff")),
            ]
        )
    )
    monkeypatch.setattr(
        "app.services.crew.get_session_factory",
        lambda: lambda: _SessionContext(session),
    )

    with pytest.raises(ValueError, match="Certification cert-1 not found"):
        await certification_service.update_certification("cert-1", "expired")


@pytest.mark.asyncio
async def test_update_certification_rejects_unknown_lifecycle_status_before_database_access():
    with pytest.raises(ValueError, match="Invalid certification status"):
        await certification_service.update_certification("cert-1", "approved")


@pytest.mark.asyncio
async def test_verify_certification_rejects_unknown_verification_status_before_database_access():
    with pytest.raises(ValueError, match="Invalid certification verification status"):
        await certification_service.verify_certification("cert-1", "approved")


@pytest.mark.asyncio
async def test_add_certification_rejects_login_account_target(monkeypatch):
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=_Result(SimpleNamespace(password_hash="hashed", role="staff"))
        )
    )
    monkeypatch.setattr(
        "app.services.crew.get_session_factory",
        lambda: lambda: _SessionContext(session),
    )

    with pytest.raises(ValueError, match="Crew member not found"):
        await certification_service.add_certification("staff-1", "STCW")

    session.execute.assert_awaited_once()
