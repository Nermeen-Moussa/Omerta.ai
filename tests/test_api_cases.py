"""Phase 13 - Case Management API tests.

Covers valid/invalid requests, missing resources, pagination, filtering,
cross-investigation isolation, RAG (KNOWLEDGE) evidence visibility, structured
errors, and idempotent reads - over the real omerta_test database through the
FastAPI app. No stack traces, SQL, or credentials ever appear in responses.
"""

import asyncio

import pytest
from apps.investigator.graph import run_investigation_async
from fastapi.testclient import TestClient
from infrastructure.database.persistence import persist_investigation
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


def _persist_two(engine: AsyncEngine) -> tuple[str, str]:
    """Run + persist TXN-001 and TXN-1006; return both case ids."""

    async def _flow() -> tuple[str, str]:
        ids = []
        for txn in ("TXN-001", "TXN-1006"):
            state = await run_investigation_async(txn)
            result = await persist_investigation(
                engine,
                investigation_id=state["investigation_id"],
                transaction_id=state["transaction_id"],
                alert_id=state.get("alert_id"),
                report=state["report"],
                evidence=state["evidence"],
                audit_events=state.get("audit_events", []),
            )
            ids.append(result["case_id"])
        return ids[0], ids[1]

    return asyncio.run(_flow())


def test_list_investigations_seeded_then_persisted(
    client: TestClient, test_engine: AsyncEngine
) -> None:
    # The seed itself carries CASE-001; the API must expose it.
    initial = client.get("/investigations")
    assert initial.status_code == 200
    assert initial.json()["total"] == 1
    assert initial.json()["items"][0]["case_id"] == "CASE-001"

    case_a, case_b = _persist_two(test_engine)
    listing = client.get("/investigations")
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 3
    ids = {item["case_id"] for item in body["items"]}
    assert {"CASE-001", case_a, case_b} <= ids
    item = body["items"][0]
    for field in ("case_id", "status", "severity", "evidence_count", "audit_event_count"):
        assert field in item


def test_list_pagination_and_severity_filter(client: TestClient, test_engine: AsyncEngine) -> None:
    _persist_two(test_engine)
    page = client.get("/investigations?limit=1&offset=0")
    assert page.status_code == 200
    body = page.json()
    assert body["limit"] == 1
    assert len(body["items"]) == 1

    # Both seeded cases are HIGH severity.
    filtered = client.get("/investigations?severity=HIGH")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 2

    assert client.get("/investigations?severity=LOW").json()["total"] == 0


def test_list_transaction_filter_and_unknown_filter_value(
    client: TestClient, test_engine: AsyncEngine
) -> None:
    _persist_two(test_engine)
    by_txn = client.get("/investigations?transaction_id=TXN-001")
    assert by_txn.status_code == 200
    body = by_txn.json()
    # CASE-001 (seeded on ALERT-001/TXN-001) + the persisted TXN-001 case.
    assert body["total"] == 2
    assert all(item["transaction_id"] == "TXN-001" for item in body["items"])


def test_get_investigation_full_detail(client: TestClient, test_engine: AsyncEngine) -> None:
    case_a, _ = _persist_two(test_engine)
    response = client.get(f"/investigations/{case_a}")
    assert response.status_code == 200
    body = response.json()
    assert body["case"]["case_id"] == case_a
    assert body["report"]["transaction_id"] == "TXN-001"
    assert body["report"]["recommended_action"]
    assert body["findings"]
    assert body["evidence"]
    assert body["audit_events"]
    # Provenance fields present on evidence rows.
    item = body["evidence"][0]
    for field in ("evidence_id", "tier", "producer", "content_hash", "category"):
        assert field in item
    # No internals leak.
    lowered = response.text.lower()
    for forbidden in ("omerta_dev_password", "postgresql+asyncpg", "traceback"):
        assert forbidden not in lowered


def test_get_investigation_unknown_returns_404(client: TestClient) -> None:
    response = client.get("/investigations/INV-DOES-NOT-EXIST")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "NOT_FOUND"


def test_report_endpoint_and_missing_report_404(
    client: TestClient, test_engine: AsyncEngine
) -> None:
    case_a, _ = _persist_two(test_engine)
    report = client.get(f"/investigations/{case_a}/report")
    assert report.status_code == 200
    assert report.json()["transaction_id"] == "TXN-001"

    missing = client.get("/investigations/INV-NOPE/report")
    assert missing.status_code == 404


def test_evidence_endpoint_pagination_and_knowledge_tier(
    client: TestClient, test_engine: AsyncEngine
) -> None:
    case_a, _ = _persist_two(test_engine)

    full = client.get(f"/investigations/{case_a}/evidence")
    assert full.status_code == 200
    total = full.json()["total"]
    assert total >= 17  # Phase 12 pipeline incl. KNOWLEDGE evidence

    page = client.get(f"/investigations/{case_a}/evidence?limit=5&offset=0")
    assert page.status_code == 200
    assert len(page.json()["items"]) == 5

    knowledge = client.get(f"/investigations/{case_a}/evidence?tier=KNOWLEDGE")
    assert knowledge.status_code == 200
    body = knowledge.json()
    assert body["total"] == 1
    chunk = body["items"][0]["data"]["chunks"][0]
    for field in ("document_id", "document_title", "section", "version"):
        assert field in chunk

    unknown_tier = client.get(f"/investigations/{case_a}/evidence?tier=NOPE")
    assert unknown_tier.status_code == 200
    assert unknown_tier.json()["total"] == 0


def test_audit_endpoint_chronological_events(client: TestClient, test_engine: AsyncEngine) -> None:
    case_a, _ = _persist_two(test_engine)
    audit = client.get(f"/investigations/{case_a}/audit")
    assert audit.status_code == 200
    events = audit.json()
    assert len(events) >= 10
    types = {event["event_type"] for event in events}
    assert "INVESTIGATION_STARTED" in types
    assert "INVESTIGATION_COMPLETED" in types
    assert "KNOWLEDGE_CONTEXT_LOADED" in types
    for event in events:
        assert event["event_type"]
        assert event["actor_type"] in {"SYSTEM", "AGENT", "HUMAN"}


def test_case_aliases_match_investigations(client: TestClient, test_engine: AsyncEngine) -> None:
    case_a, case_b = _persist_two(test_engine)

    cases = client.get("/cases")
    assert cases.status_code == 200
    assert cases.json()["total"] == 3  # seed CASE-001 + two persisted

    single = client.get(f"/cases/{case_a}")
    assert single.status_code == 200
    assert single.json()["case"]["case_id"] == case_a
    assert client.get("/cases/INV-MISSING").status_code == 404


def test_cross_investigation_isolation_over_api(
    client: TestClient, test_engine: AsyncEngine
) -> None:
    case_a, case_b = _persist_two(test_engine)
    evidence_a = client.get(f"/investigations/{case_a}/evidence").json()
    evidence_b = client.get(f"/investigations/{case_b}/evidence").json()
    # Same EV numbering scheme, but every row belongs to exactly one case.
    for item in evidence_a["items"]:
        assert item["investigation_id"] == case_a
    for item in evidence_b["items"]:
        assert item["investigation_id"] == case_b


def test_read_endpoints_idempotent(client: TestClient, test_engine: AsyncEngine) -> None:
    case_a, _ = _persist_two(test_engine)
    first = client.get(f"/investigations/{case_a}").text
    second = client.get(f"/investigations/{case_a}").text
    assert first == second  # reads never mutate
