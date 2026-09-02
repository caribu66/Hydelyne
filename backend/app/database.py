from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory = None


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        engine_kwargs = {
            "echo": settings.APP_ENV == "development",
            "future": True,
        }
        if "sqlite" in settings.DATABASE_URL:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            # SQLite uses NullPool by default; pool args not applicable
        else:
            engine_kwargs.update(
                {
                    "pool_size": 20,
                    "max_overflow": 10,
                    "pool_timeout": 30,
                    "pool_recycle": 1800,
                    "pool_pre_ping": True,
                }
            )
        _engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)
        _session_factory = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _engine


def get_session_factory():
    global _session_factory
    if _session_factory is None:
        get_engine()
    return _session_factory


async def dispose_engine() -> None:
    """Dispose the async engine and drop the singleton so the next call to
    get_engine()/get_session_factory() creates a fresh one.

    Needed by callers that run a short-lived event loop via asyncio.run()
    inside a long-lived process (e.g. a Celery worker calling the async
    profile-enrichment service from a sync task). asyncpg connections are
    bound to the event loop that created them; asyncio.run() opens a new
    loop each call, so reusing the engine singleton across calls raises
    "attached to a different loop" on the second and subsequent calls in
    the same worker process. Must be awaited from within the same loop
    that used the engine — disposal itself hits the same cross-loop error
    otherwise.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_db() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database schema.

    This function is reserved for SQLite dev/test only. PostgreSQL production
    deployments must run `alembic upgrade head` as a discrete step (see
    ``backend/Dockerfile`` entrypoint); the API must not start against an
    out-of-date PostgreSQL schema.
    """
    from app.models import Certification, CrewMember, Document, Project, WorkHistory  # noqa: F401

    if "sqlite" not in settings.DATABASE_URL:
        raise RuntimeError(
            "init_db() must not run against PostgreSQL. "
            "Run `alembic upgrade head` as a separate deployment step."
        )

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
