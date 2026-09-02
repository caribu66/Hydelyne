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


async def get_db() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    from app.models import Certification, CrewMember, Document, Project, WorkHistory  # noqa: F401
    # In production use alembic migrations; create_all is dev fallback for sqlite
    if "sqlite" in settings.DATABASE_URL:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        return

    # PostgreSQL path: run alembic upgrade head via async engine
    try:
        import asyncio
        from pathlib import Path

        from alembic.config import Config

        from alembic import command

        # alembic.ini is at backend/alembic.ini
        backend_root = Path(__file__).resolve().parent.parent
        alembic_ini = backend_root / "alembic.ini"
        if alembic_ini.exists():
            # Run in thread to avoid blocking event loop; alembic is sync
            def _upgrade():
                cfg = Config(str(alembic_ini))
                cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
                command.upgrade(cfg, "head")

            await asyncio.to_thread(_upgrade)
            return
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning(f"Alembic upgrade failed, falling back to create_all: {e}")

    # Fallback if alembic not available
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
