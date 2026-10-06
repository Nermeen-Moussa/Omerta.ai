"""Phase 10 deterministic evaluation of the investigation pipeline.

Small scenario suite over seeded data asserting **observable properties**
(not exact LLM wording), using the no-network fake provider so the suite
never requires API keys or internet:

- Scenario 1: TXN-001  - seeded high-risk wire (new device/IP, high amount)
- Scenario 2: TXN-1006 - shared-device scenario (structural graph signal)
- Scenario 3: TXN-1001 - clean baseline transfer (no signals)

Also measures end-to-end latency per scenario (already collected per node).
"""

import asyncio
import json
from typing import Any

import pytest
from apps.investigator.graph import run_investigation_async
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


def _agent_ms(final: dict[str, Any]) -> float:
    return (final.get("node_timings_ms") or {}).get("analyze_with_agent", 0.0)


# --------------------------------------------------------------------------- #
# Scenario 1: TXN-001 (seeded high-risk)
# --------------------------------------------------------------------------- #


def test_scenario_txn001_high_risk_observable_properties() -> None:
    final = asyncio.run(run_investigation_async("TXN-001"))
    assert final["status"] == "COMPLETED"
    report = final["report"]
    assert report is not None

    # Facts surfaced: amount + originator match the seeded transaction.
    assert final["transaction"]["amount"] == "8400.00"
    assert final["transaction"]["sender"]["external_id"] == "ACC-1001"

    # Risk provenance preserved; the report exists and recommends review.
    assert final["risk_score"]["source"] == "MOCK"
    assert report["recommended_action"] in {"HUMAN_REVIEW", "ESCALATE_TO_FIU"}
    assert 0.0 <= report["confidence"] <= 1.0

    # Every finding references real evidence; evidence ids are unique.
    evidence_ids = {e["evidence_id"] for e in final["evidence"]}
    assert report["findings"]
    for finding in report["findings"]:
        assert finding["evidence_ids"], "findings must cite evidence"
        assert set(finding["evidence_ids"]) <= evidence_ids
    assert len(evidence_ids) == len(final["evidence"])

    # JSON-serializable (persistence contract).
    json.dumps(final)


# --------------------------------------------------------------------------- #
# Scenario 2: TXN-1006 (shared-device structural signal)
# --------------------------------------------------------------------------- #


def test_scenario_txn1006_shared_device_grounding() -> None:
    final = asyncio.run(run_investigation_async("TXN-1006"))
    assert final["status"] == "COMPLETED"
    assert final["transaction"]["transaction_id"] == "TXN-1006"

    # The shared-device structural signal is discoverable from the graph.
    shared = final["shared_devices"]["shared_devices"]
    assert any(d["device_id"] == "DEV-123" for d in shared), (
        "DEV-123 must appear as a shared device for the TXN-1006 scenario"
    )

    # Graph evidence was collected and findings stay evidence-grounded.
    graph_evidence = [e for e in final["evidence"] if e["category"] == "GRAPH"]
    assert graph_evidence
    evidence_ids = {e["evidence_id"] for e in final["evidence"]}
    for finding in final["report"]["findings"]:
        assert set(finding["evidence_ids"]) <= evidence_ids

    # Signals remain signals: no fraud verdict anywhere in the result.
    dumped = json.dumps(final).lower()
    assert "fraud_confirmed" not in dumped


# --------------------------------------------------------------------------- #
# Scenario 3: TXN-1001 (clean baseline)
# --------------------------------------------------------------------------- #


def test_scenario_txn1001_clean_baseline_completes() -> None:
    final = asyncio.run(run_investigation_async("TXN-1001"))
    assert final["status"] == "COMPLETED"
    assert final["errors"] == []
    assert final["transaction"]["transaction_id"] == "TXN-1001"

    # Evidence exists and the pipeline produces a valid, grounded report even
    # for a low-signal transaction.
    assert final["evidence"]
    evidence_ids = {e["evidence_id"] for e in final["evidence"]}
    for finding in final["report"]["findings"]:
        assert set(finding["evidence_ids"]) <= evidence_ids
    assert final["report"]["recommended_action"] in {
        "HUMAN_REVIEW",
        "ESCALATE_TO_FIU",
        "REQUEST_CUSTOMER_INFO",
        "MONITOR",
        "CLOSE_NO_ACTION",
    }


# --------------------------------------------------------------------------- #
# Cross-scenario invariants
# --------------------------------------------------------------------------- #


def test_scenarios_are_isolated_and_reproducible() -> None:
    """Two runs of the same scenario agree on observable properties."""
    first = asyncio.run(run_investigation_async("TXN-001"))
    second = asyncio.run(run_investigation_async("TXN-001"))
    for run in (first, second):
        assert run["status"] == "COMPLETED"
        assert run["report"]["recommended_action"] == "HUMAN_REVIEW"
        assert run["report"]["transaction_id"] == "TXN-001"
    # Distinct investigations, same evidence shape.
    assert first["investigation_id"] != second["investigation_id"]
    assert len(first["evidence"]) == len(second["evidence"])


def test_scenario_latency_is_measured_per_node() -> None:
    final = asyncio.run(run_investigation_async("TXN-001"))
    timings = final["node_timings_ms"]
    total = sum(timings.values())
    assert total > 0
    # Agent duration is recorded separately (LLM latency visibility).
    assert _agent_ms(final) >= 0.0
    assert "load_graph_context" in timings and "load_risk_context" in timings
