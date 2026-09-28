"""SQLAlchemy 2.x async engine and session factory for PostgreSQL.

The application engine is created lazily so the database URL can be
reconfigured (tests point it at the isolated omerta_test database) before the
first connection is made. Application code calls :func:`get_engine`; tests set
the URL once in conftest via :func:`set_engine_url`.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool


class Base(DeclarativeBase):
    """Declarative base for all Omerta.ai ORM models."""


_engine: AsyncEngine | None = None

# Loop/task-local engine override (mirrors infrastructure.neo4j.client.use_driver):
# lets one unit of work (a run, a script scenario, a test) bind its own engine
# without mutating process-global state. asyncpg connections are event-loop
# bound, so pooled connections must never be shared across loops.
_override_engine: ContextVar[AsyncEngine | None] = ContextVar("db_engine_override", default=None)


def create_engine(database_url: str | None = None, *, use_null_pool: bool = False) -> AsyncEngine:
    """Create an async engine (defaults to settings.DATABASE_URL)."""
    from infrastructure.config import get_settings

    url = database_url if database_url is not None else get_settings().database_url
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool if use_null_pool else None,
    )


def get_engine() -> AsyncEngine:
    """Return the database engine: context-local override first, else shared."""
    override = _override_engine.get()
    if override is not None:
        return override
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def use_engine(engine: AsyncEngine):
    """Context manager: bind ``engine`` to the current context/task only.

    Inside the block, ``get_engine()`` returns ``engine``; other tasks and the
    process-global cache are untouched. Used by cross-loop entry points
    (scripts, repeated asyncio.run calls) so each loop owns its connections.
    """

    @contextmanager
    def _ctx():
        token = _override_engine.set(engine)
        try:
            yield
        finally:
            _override_engine.reset(token)

    return _ctx()


def set_engine_url(url: str) -> AsyncEngine:
    """Point the application engine at ``url`` (used by the test suite).

    Fails if the engine was already materialized, which would indicate that
    connections were opened before test configuration - a bug.
    """
    global _engine
    if _engine is not None:
        raise RuntimeError(
            "Engine already created; set_engine_url must be called before any "
            "database connection is opened."
        )
    _engine = create_engine(url, use_null_pool=True)
    return _engine


def reset_engine() -> None:
    """Drop the cached engine reference (used by tests for cleanup)."""
    global _engine
    _engine = None


@asynccontextmanager
async def session_scope(engine_: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Open a transactional session scope; commit on success, rollback on error."""
    session = async_sessionmaker(engine_, expire_on_commit=False)()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
