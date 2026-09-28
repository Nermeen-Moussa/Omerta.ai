"""Phase 10 API hardening tests for ``POST /investigations/run``.

Covers input validation (422), failed investigations returned as structured
results, explicit ``persist`` opt-in, and persistence failure surfacing as a
structured 503 - never a stack trace or leaked credentials.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(autouse=True)
def seeded_environment(test_engine: AsyncEngine, graph_test_projection: str) -> None:
    """Seed PostgreSQL and project to Neo4j before each test."""

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


@pytest.fixture()
def client() -> TestClient:
    from apps.api.main import app

    return TestClient(app)


def test_run_validates_blank_transaction_id(client: TestClient) -> None:
    response = client.post("/investigations/run", json={"transaction_id": "   "})
    assert response.status_code == 422
    assert "must not be blank" in response.text


def test_run_rejects_empty_body_and_wrong_types(client: TestClient) -> None:
    assert client.post("/investigations/run", json={}).status_code == 422
    assert client.post("/investigations/run", json={"transaction_id": 12345}).status_code == 422


def test_run_unknown_transaction_returns_structured_failed_state(
    client: TestClient,
) -> None:
    """A FAILED investigation is a *successful run* with a failed outcome:
    200 + structured NOT_FOUND - no stack traces, no 500."""
    response = client.post("/investigations/run", json={"transaction_id": "TXN-999"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["errors"][0]["error"] == "NOT_FOUND"
    assert body["errors"][0]["id"] == "TXN-999"
    assert body["report"] is None and body["evidence"] == []
    lowered = response.text.lower()
    assert "traceback" not in lowered
    assert "omerta_dev_password" not in lowered


def test_run_txn001_without_persist_returns_state_only(client: TestClient) -> None:
    response = client.post(
        "/investigations/run", json={"transaction_id": "TXN-001", "persist": False}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["report"]["transaction_id"] == "TXN-001"
    assert "persistence" not in body  # explicit opt-in only


def test_run_txn001_with_persist_persists_case(client: TestClient) -> None:
    response = client.post(
        "/investigations/run", json={"transaction_id": "TXN-001", "persist": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert body["persistence"]["case_id"].startswith("INV-")
    assert body["persistence"]["evidence_rows"] == len(body["evidence"])


def test_run_persistence_failure_returns_structured_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from infrastructure.database import persistence as persistence_module

    async def _boom(*args: object, **kwargs: object) -> dict:
        raise RuntimeError("simulated persistence outage")

    monkeypatch.setattr(persistence_module, "persist_investigation", _boom)
    response = client.post(
        "/investigations/run", json={"transaction_id": "TXN-001", "persist": True}
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "PERSISTENCE_ERROR"
    lowered = response.text.lower()
    assert "simulated persistence outage" not in lowered
    assert "traceback" not in lowered


def test_run_result_contains_no_secrets(client: TestClient) -> None:
    response = client.post(
        "/investigations/run", json={"transaction_id": "TXN-001", "persist": True}
    )
    lowered = response.text.lower()
    for forbidden in (
        "omerta_dev_password",
        "postgresql+asyncpg://",
        "bolt://",
        "api_key",
        "authorization",
    ):
        assert forbidden not in lowered, f"leaked: {forbidden}"
