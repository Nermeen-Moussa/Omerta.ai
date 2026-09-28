"""Async Neo4j driver management (mirrors the lazy database engine pattern).

The driver is created lazily so tests can point it at a dedicated projection
namespace (or URI) before the first connection is opened.
"""

from contextvars import ContextVar
from typing import Any

from neo4j._async.driver import (
    AsyncDriver,  # type: ignore[import-untyped] - stable across neo4j 5/6
)

from infrastructure.config import get_settings
from neo4j import AsyncGraphDatabase

_driver: AsyncDriver | None = None

# Loop/task-local driver override: lets one investigation (or test) use its own
# driver without mutating process-global state. Contexts that never set it see
# the lazily-created shared driver, so concurrent investigations cannot race
# on driver creation/teardown.
_override_driver: ContextVar[AsyncDriver | None] = ContextVar("neo4j_driver_override", default=None)


def get_driver() -> AsyncDriver:
    """Return the Neo4j driver: context-local override first, else shared."""
    override = _override_driver.get()
    if override is not None:
        return override
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
    return _driver


def set_driver(driver: AsyncDriver | None) -> None:
    """Replace the cached driver (used by tests)."""
    global _driver
    _driver = driver


def use_driver(driver: AsyncDriver | None):
    """Context manager: bind ``driver`` to the current context/task only.

    Inside the block, ``get_driver()`` returns ``driver``; other tasks and the
    process-global cache are untouched. Used by the async investigation runner
    so each run owns its driver lifecycle without global mutation.
    """
    from contextlib import contextmanager

    @contextmanager
    def _ctx():
        token = _override_driver.set(driver)
        try:
            yield
        finally:
            _override_driver.reset(token)

    return _ctx()


def projection() -> str:
    """Namespace stamped on every node of the current graph projection."""
    return get_settings().graph_projection


async def read_query(query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a read query in the configured database; return plain dict records."""
    driver = get_driver()
    async with driver.session(database=get_settings().neo4j_database) as session:
        result = await session.run(query, parameters or {})
        return await result.data()


async def write_query(query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run a write query (auto-commit per statement); return dict records.

    Used only by the projection/cleanup paths, whose writes are idempotent
    MERGEs and namespace-scoped deletes - safe to re-run.
    """
    driver = get_driver()
    async with driver.session(database=get_settings().neo4j_database) as session:
        result = await session.run(query, parameters or {})
        data = await result.data()
        await result.consume()
    return data


async def close_driver() -> None:
    """Dispose the cached driver if it exists."""
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
