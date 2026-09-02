"""Test configuration and fixtures."""
# ruff: noqa: E402 - imports below intentionally follow test-DB setup
import os
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.auth.decorators as auth_decorators
from app.database import Base, get_db
from app.main import app
from app.models import CrewMember
from app.services.crew import auth_service

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test.db",
)

try:
    test_engine = create_async_engine(TEST_DATABASE_URL, future=True)
except Exception:
    # Fallback to sqlite if asyncpg/postgres not available
    TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
    test_engine = create_async_engine(TEST_DATABASE_URL, future=True)

test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

# --- Mock auth for tests: bypass token check (default user is admin so admin-
# gated endpoints like upload remain testable) ---
_dummy_user = CrewMember(
    id=str(uuid.uuid4()),
    full_name="Test User",
    email="test@test.com",
    role="admin",
)
auth_service.get_user_from_token = AsyncMock(return_value=_dummy_user)
auth_decorators._extract_token = lambda request: "test-token"

# Patch app's DB globals to use test DB so all `get_session_factory` calls use test DB
import app.database as app_db

app_db._engine = test_engine
app_db._session_factory = test_session_factory

# Ensure DB tables exist for sqlite test db
import asyncio


async def _init_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

try:
    asyncio.get_event_loop().run_until_complete(_init_test_db())
except RuntimeError:
    # Already in event loop (pytest-asyncio will handle)
    pass

@pytest_asyncio.fixture(autouse=True)
async def _ensure_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


async def override_get_db():
    async with test_session_factory() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session():
    async with test_session_factory() as session:
        yield session


@pytest.fixture
def sample_crew_data():
    return {
        "full_name": "John Smith",
        "email": "john.smith@example.com",
        "phone": "+44 1234 567890",
        "nationality": "British",
    }
