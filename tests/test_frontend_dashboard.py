"""Phase 16 - frontend dashboard tests.

The dashboard is a zero-build static SPA served by FastAPI at ``/`` and
``/static/*``. These tests verify (a) the UI assets are served, (b) the exact
API contract the JavaScript consumes (field names the UI renders), and (c)
the end-to-end data flow: run + persist an investigation, then read it back
through the same endpoints the dashboard calls. A live browser check of the
rendered UI is performed separately via scripts/phase16_ui_check.py.
"""

import asyncio

import pytest
from apps.investigator.graph import run_investigation_async
from fastapi.testclient import TestClient
from infrastructure.database.persistence import persist_investigation
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(autouse=True)
def seeded_environment(test_engine: AsyncEngine, graph_test_projection: str) -> None:
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


def _persist_one(engine: AsyncEngine, txn: str) -> str:
    async def _flow() -> str:
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
        return result["case_id"]

    return asyncio.run(_flow())


def test_ui_assets_served(client: TestClient) -> None:
    index = client.get("/static/index.html")
    assert index.status_code == 200
    assert "Omerta.ai" in index.text
    assert "static/app.js" in index.text

    js = client.get("/static/app.js")
    assert js.status_code == 200
    assert "/investigations" in js.text  # consumes the Case API

    css = client.get("/static/styles.css")
    assert css.status_code == 200

    root = client.get("/", follow_redirects=False)
    assert root.status_code in {200, 307}


def test_dashboard_list_contract_matches_ui_fields(
    client: TestClient, test_engine: AsyncEngine
) -> None:
    """Field names the dashboard renders must exist in the API payload."""
    case_id = _persist_one(test_engine, "TXN-001")
    body = client.get("/investigations").json()
    item = next(i for i in body["items"] if i["case_id"] == case_id)
    for field in (
        "case_id",
        "transaction_id",
        "status",
        "severity",
        "evidence_count",
        "audit_event_count",
        "created_at",
    ):
        assert field in item
    assert item["severity"] in {"HIGH", "MEDIUM", "LOW"}


def test_investigation_view_contract_matches_ui_fields(
    client: TestClient, test_engine: AsyncEngine
) -> None:
    """The detail view renders report/findings/evidence/audit - fields must exist."""
    case_id = _persist_one(test_engine, "TXN-001")
    detail = client.get(f"/investigations/{case_id}").json()

    report = detail["report"]
    for field in (
        "summary",
        "risk_level",
        "recommended_action",
        "confidence",
        "typologies",
        "provenance",
    ):
        assert field in report
    assert report["provenance"]["llm_provider"]
    assert report["provenance"]["agent_version"]

    for finding in detail["findings"]:
        for field in ("finding", "evidence_ids", "confidence"):
            assert field in finding

    for item in detail["evidence"]:
        for field in ("evidence_id", "tier", "category", "source", "producer", "description"):
            assert field in item
        assert item["tier"] in {
            "FACT",
            "STRUCTURAL_SIGNAL",
            "MODEL_OUTPUT",
            "AGENT_FINDING",
            "KNOWLEDGE",
        }

    for event in detail["audit_events"]:
        for field in ("event_type", "actor_type", "source", "created_at"):
            assert field in event


def test_graph_section_contract_structural_only(
    client: TestClient, test_engine: AsyncEngine
) -> None:
    """The graph panel renders STRUCTURAL_SIGNAL evidence, labeled as signals."""
    case_id = _persist_one(test_engine, "TXN-001")
    data = client.get(
        f"/investigations/{case_id}/evidence", params={"tier": "STRUCTURAL_SIGNAL"}
    ).json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["tier"] == "STRUCTURAL_SIGNAL"
        assert item["category"] == "GRAPH"


def test_ui_error_states_are_structured(client: TestClient) -> None:
    """The UI's error rendering relies on structured detail payloads."""
    response = client.get("/investigations/INV-MISSING")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "NOT_FOUND"


def test_end_to_end_flow_run_persist_render(client: TestClient, test_engine: AsyncEngine) -> None:
    """The full dashboard data path: run -> persist -> list -> detail -> panels."""
    run = client.post("/investigations/run", json={"transaction_id": "TXN-001", "persist": True})
    assert run.status_code == 200
    case_id = run.json()["persistence"]["case_id"]

    listing = client.get("/investigations").json()
    assert any(i["case_id"] == case_id for i in listing["items"])

    detail = client.get(f"/investigations/{case_id}").json()
    assert detail["report"] is not None
    assert detail["evidence"]
    assert detail["audit_events"]

    knowledge = client.get(
        f"/investigations/{case_id}/evidence", params={"tier": "KNOWLEDGE"}
    ).json()
    assert knowledge["total"] == 1  # knowledge references panel has data
    audit = client.get(f"/investigations/{case_id}/audit").json()
    assert len(audit) >= 10
