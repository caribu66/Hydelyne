"""Test configuration and fixtures."""

# ruff: noqa: E402 - imports below intentionally follow test-DB setup
import os
import uuid
from unittest.mock import AsyncMock, MagicMock

# A process-local test database avoids inheriting an interrupted run's SQLite
# write lock from the repository checkout.
# PIDs are not globally unique in managed/sandboxed runners. A PID-only path
# lets separate pytest processes inherit one another's SQLite locks and makes
# the autouse cleanup fixture hang before the first test body runs.
DEFAULT_TEST_DATABASE_URL = f"sqlite+aiosqlite:////tmp/hydenlyne-test-{uuid.uuid4().hex}.db"

# Set env vars before any app.* import so settings pick them up. ``get_settings``
# is called at import time in ``app.config``, ``app.database``, ``app.main`` and
# ``app.auth.session``; without these overrides the test would inherit whatever
# the host environment happens to have.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL))
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SESSION_SECRET_KEY", "test_secret_key_at_least_32_chars_long_xx")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.auth.decorators as auth_decorators  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CrewMember  # noqa: E402
from app.services.cache import cache_service  # noqa: E402
from app.services.crew import auth_service  # noqa: E402
from app.services.upload import document_upload_service  # noqa: E402
from app.services.upload import settings as upload_settings
from app.tasks.document_tasks import (  # noqa: E402
    cleanup_deleted_crew_projections,
    cleanup_document_projections,
    cleanup_local_document_cache,
    cleanup_orphaned_upload,
    index_document_embeddings,
    process_document_extraction,
    process_dropbox_document,
    reconcile_certificate_projection,
    reconcile_crew_projection,
    reconcile_document_search_projection,
)

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    DEFAULT_TEST_DATABASE_URL,
)

try:
    # asyncpg connections bind to the creating event loop, and pytest-asyncio
    # gives each test a fresh function-scoped loop: a pooled connection
    # checked out on one loop explodes on the next ("attached to a different
    # loop"). NullPool gives every checkout a loop-local connection, which is
    # required for both PostgreSQL and SQLite test runs.
    from sqlalchemy.pool import NullPool

    # Do not reuse SQLite connections across pytest-asyncio event loops either.
    # A connection retained by the async pool can leave aiosqlite's worker
    # thread waiting on the loop that created it during import-time setup.
    _poolclass = {"poolclass": NullPool}
    test_engine = create_async_engine(TEST_DATABASE_URL, future=True, **_poolclass)
except Exception:
    # Fallback to sqlite if asyncpg/postgres not available
    TEST_DATABASE_URL = DEFAULT_TEST_DATABASE_URL
    test_engine = create_async_engine(TEST_DATABASE_URL, future=True, poolclass=NullPool)

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

# Uploads must never hit the real Dropbox account: even with live credentials
# configured in .env, tests fall back to local-cache-only storage.
document_upload_service.dropbox_available = False
upload_settings.REQUIRE_DROPBOX_STORAGE = False

_orig_get_file_async = document_upload_service.get_file_async


async def _test_get_file_async(storage_path: str) -> bytes | None:
    res = await _orig_get_file_async(storage_path)
    if res is not None:
        return res
    if storage_path.startswith("/tmp/"):
        if storage_path.endswith(".png"):
            return (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
                b"\x00\x00\x00\x1f\x15c4"
            )
        return b"%PDF-1.4 mock content for testing"
    return None


document_upload_service.get_file_async = _test_get_file_async  # type: ignore[method-assign]

# .delay() publishes to the real Celery/Redis broker, which requires auth this
# environment's REDIS_URL doesn't carry. That doesn't fail fast: kombu retries
# the connection with no timeout, so any upload test blocks forever instead of
# hitting the `except Exception` around the call site in app/api/documents.py.
process_document_extraction.delay = MagicMock()
process_dropbox_document.delay = MagicMock()
index_document_embeddings.delay = MagicMock()
cleanup_document_projections.delay = MagicMock()
reconcile_document_search_projection.delay = MagicMock()
reconcile_certificate_projection.delay = MagicMock()
cleanup_deleted_crew_projections.delay = MagicMock()
reconcile_crew_projection.delay = MagicMock()
cleanup_orphaned_upload.delay = MagicMock()
cleanup_local_document_cache.delay = MagicMock()

# Meilisearch indexing (create/update/delete crew member) makes a real network
# call by default; the test environment has no Meilisearch server reachable,
# and the client's own try/except would otherwise just eat a connection-
# timeout on every crew mutation test. Mock it so tests are fast and so
# individual tests can assert it was called with the expected document.
from app.services.meilisearch import meilisearch_client
from app.services.qdrant import qdrant_service

meilisearch_client.index_crew_member = AsyncMock(return_value={"task_uid": 0})
meilisearch_client.delete_crew_member = AsyncMock(return_value=True)
meilisearch_client.index_document = AsyncMock(return_value={"task_uid": 0})
meilisearch_client.delete_document = AsyncMock(return_value=True)
meilisearch_client.delete_documents = AsyncMock(return_value=True)
qdrant_service.delete_document = AsyncMock(return_value=True)

# Default Redis availability to False so no test calls a real Redis by accident.
# Individual tests can monkeypatch cache_service.is_redis_available / specific
# methods to exercise Redis-backed behavior (see test_login_rate_limit.py).
cache_service.is_redis_available = AsyncMock(return_value=False)
# Cache invalidation is a best-effort side effect in application services. A
# health mock alone does not stop an actual ``delete`` call from opening a
# five-second localhost socket timeout, which can make DB tests appear hung.
cache_service.delete = AsyncMock(return_value=True)


# Patch app's DB globals to use test DB so all `get_session_factory` calls use test DB
import app.database as app_db

app_db._engine = test_engine
app_db._session_factory = test_session_factory

# Ensure DB tables exist for sqlite test db
import asyncio


async def _init_test_db():
    # Create the isolated SQLite test schema. Row isolation is handled by the
    # autouse fixture below; dropping the entire schema here can block before
    # pytest even collects tests when another SQLite connection is unwinding.
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


sync_test_engine = None
if TEST_DATABASE_URL.startswith("sqlite+aiosqlite"):
    # Import-time async setup can deadlock before pytest has installed its
    # event-loop fixtures. Use a short-lived synchronous SQLite engine for
    # schema creation; test queries still use the async engine below.
    from sqlalchemy import create_engine

    # Do not retain a synchronous SQLite connection beside the async engine;
    # a pooled cleanup connection can keep a file lock while the first test
    # session attempts its write.
    sync_test_engine = create_engine(
        TEST_DATABASE_URL.replace("+aiosqlite", ""), poolclass=NullPool
    )
    Base.metadata.create_all(sync_test_engine)
else:
    asyncio.run(_init_test_db())


@pytest_asyncio.fixture(autouse=True)
async def _ensure_tables():
    # Clear every table's rows (not just create_all, which is a no-op on
    # tables that already exist) so one test's committed rows can't feed
    # another's queries — e.g. a ranked/limited search silently swallowing a
    # just-inserted row behind leftover rows an earlier test committed.
    # A row-level delete is far cheaper than drop_all/create_all per test.
    if sync_test_engine is not None:
        with sync_test_engine.begin() as conn:
            Base.metadata.create_all(conn)
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
    else:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())
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
