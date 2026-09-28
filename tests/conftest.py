"""Shared fixtures: isolated ``omerta_test`` PostgreSQL database.

Tests never touch the dev database (``omerta``) or any external database.
At session start the fixture suite:

1. creates ``omerta_test`` if missing (against the same Dockerized PostgreSQL),
2. migrates it with the project's own Alembic migrations (tables are never
   created outside migrations),
3. reset+seeds a deterministic dataset for each test and rolls back the
   test's writes afterwards.

The engine fixture is deliberately *synchronous*: async fixtures live on a
per-test event loop, and pooled asyncpg connections are loop-bound, so a
session-scoped async fixture would leak connections across loops. A sync
fixture + ``NullPool`` (fresh connection per use) sidesteps that entirely.

Requires ``docker compose up -d postgres`` (see README).
"""

import asyncio
import subprocess
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import TypeVar

import asyncpg
import pytest
from infrastructure.config import get_settings
from infrastructure.database import session as db_session_module
from infrastructure.database.seed import reset_all, seed
from infrastructure.database.session import create_engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

settings = get_settings()
TEST_DB_URL = settings.test_database_url
TEST_GRAPH_PROJECTION = "test"
T = TypeVar("T")


def run_with_graph[T](coro_fn: Callable[[], Awaitable[T]]) -> T:
    """Run an async graph operation on a private loop with a fresh driver.

    The Neo4j asyncio driver is event-loop-bound like asyncpg, so every graph
    test gets its own driver, created and closed inside the same loop.
    """
    from infrastructure.neo4j import client as graph_client

    from neo4j import AsyncGraphDatabase

    async def runner() -> T:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        graph_client.set_driver(driver)
        try:
            return await coro_fn()
        finally:
            await driver.close()
            graph_client.set_driver(None)

    return asyncio.run(runner())


def _ensure_test_database_exists() -> None:
    """Create omerta_test on the Dockerized PostgreSQL if it does not exist."""

    async def _create() -> None:
        conn = await asyncpg.connect(
            host="127.0.0.1",
            port=15432,
            user="omerta",
            password="omerta_dev_password",
            database="postgres",
        )
        try:
            await conn.execute("CREATE DATABASE omerta_test OWNER omerta")
        except asyncpg.exceptions.DuplicateDatabaseError:
            pass
        finally:
            await conn.close()

    asyncio.run(_create())


def _migrate_test_database() -> None:
    """Run `alembic upgrade head` against omerta_test via a subprocess.

    A subprocess keeps Alembic's asyncio.run() out of pytest's event loops.
    Runs unconditionally (idempotent): schema evolution (e.g. Phase 11
    evidence/audit columns) must reach an existing omerta_test database too.
    """
    subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"db_url={TEST_DB_URL}", "upgrade", "head"],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def test_engine() -> Iterator[AsyncEngine]:
    """Session-scoped engine bound to the migrated omerta_test database.

    Synchronous fixture (no event loop attached); uses NullPool so every
    connection is created on the borrowing test's own loop. Also re-points the
    *application* engine (used by MCP tools and the API) at the test database
    so every layer - not just direct repository use - stays isolated.
    """
    assert "omerta_test" in TEST_DB_URL, (
        f"Tests must use the isolated omerta_test database, got: {TEST_DB_URL}"
    )
    _ensure_test_database_exists()
    _migrate_test_database()
    db_session_module.set_engine_url(TEST_DB_URL)
    engine = create_engine(TEST_DB_URL, use_null_pool=True)
    yield engine
    # Dispose outside any test loop: NullPool keeps no idle connections, so
    # this is safe synchronously.
    asyncio.run(engine.dispose())
    asyncio.run(db_session_module.get_engine().dispose())
    db_session_module.reset_engine()


@pytest.fixture(scope="session")
def graph_test_projection() -> Iterator[str]:
    """Isolate graph tests in the 'test' projection namespace.

    Every Omerta node carries a ``projection`` property, so test data lives
    alongside dev data safely: queries are namespace-scoped and cleanup only
    ever deletes nodes where ``projection = 'test'``. A developer's unrelated
    Neo4j data is never touched.
    """
    from infrastructure.neo4j import client as graph_client

    original = graph_client.projection
    graph_client.projection = lambda: TEST_GRAPH_PROJECTION  # type: ignore[method-assign]
    yield TEST_GRAPH_PROJECTION
    graph_client.projection = original  # type: ignore[method-assign]

    async def _cleanup() -> None:
        await graph_client.write_query(
            "MATCH (n) WHERE n.projection = $projection DETACH DELETE n",
            {"projection": TEST_GRAPH_PROJECTION},
        )

    run_with_graph(_cleanup)


@pytest.fixture(scope="session")
def graph_seeded(test_engine: AsyncEngine, graph_test_projection: str) -> None:
    """Seed PostgreSQL, then project it into Neo4j (once per session).

    Per-test PostgreSQL reseeds produce identical business keys, so the
    session-scoped graph projection stays valid for every test.
    """
    from infrastructure.neo4j.projection import project_all

    async def _project() -> None:
        await reset_all(test_engine)
        await seed(test_engine)
        await project_all(test_engine)

    run_with_graph(_project)


@pytest.fixture(autouse=True)
def _pg_seeded_for_graph(test_engine: AsyncEngine, request: pytest.FixtureRequest) -> None:
    """Reset+seed PostgreSQL for graph tests (marked with @pytest.mark.graph)."""
    if "graph" not in request.keywords:
        return

    async def _reseed() -> None:
        await reset_all(test_engine)
        await seed(test_engine)

    asyncio.run(_reseed())


@pytest.fixture
async def seeded_db(test_engine: AsyncEngine) -> None:
    """Reset and seed the test database (committed state, no session held)."""
    await reset_all(test_engine)
    await seed(test_engine)


@pytest.fixture
def graph_seeded_env(test_engine: AsyncEngine, graph_test_projection: str) -> None:
    """Seed PostgreSQL and project to Neo4j before a test (Phase 11 suite).

    Synchronous wrapper so every async fixture/test runs on its own loop with
    its own graph driver lifecycle.
    """

    async def _seed() -> None:
        from infrastructure.config import get_settings
        from infrastructure.database.seed import reset_all, seed
        from infrastructure.neo4j import client as graph_client
        from infrastructure.neo4j.projection import project_all

        settings = get_settings()
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        graph_client.set_driver(driver)
        try:
            await reset_all(test_engine)
            await seed(test_engine)
            await project_all(test_engine)
        finally:
            await driver.close()
            graph_client.set_driver(None)

    asyncio.run(_seed())


@pytest.fixture
def investigation_env(test_engine: AsyncEngine, graph_seeded_env: None) -> AsyncEngine:
    """Seeded PostgreSQL + graph environment for full-pipeline Phase 11 tests."""
    return test_engine


@pytest.fixture
def pipeline_env(investigation_env: AsyncEngine) -> AsyncEngine:
    """Alias used by the Phase 11 evidence/audit test modules."""
    return investigation_env


@pytest.fixture
async def db_session(test_engine: AsyncEngine, seeded_db: None) -> AsyncIterator[AsyncSession]:
    """Session over a freshly seeded database, wrapped in a rolled-back transaction.

    The test's own writes roll back and do not leak between tests; the seeded
    data itself is committed beforehand by the ``seeded_db`` fixture.
    """
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest.fixture
async def knowledge_session(
    test_engine: AsyncEngine, seeded_db: None
) -> AsyncIterator[AsyncSession]:
    """Committed-session over a freshly seeded DB (Phase 12 knowledge included).

    Unlike ``db_session`` this session may commit (ingestion upserts are part
    of the behavior under test); the next test's ``seeded_db`` reset cleans up.
    """
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
