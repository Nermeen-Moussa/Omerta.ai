"""Phase 10 hardening tests: failure matrix, lifecycle, idempotency,
concurrency isolation, persistence atomicity, latency, observability.

All tests run against the real isolated omerta_test PostgreSQL + 'test'
Neo4j projection with the deterministic fake LLM provider.
"""

import asyncio
import json
from typing import Any

import pytest
from apps.investigator.graph import build_investigation_graph, run_investigation_async
from apps.investigator.nodes import (
    assemble_evidence,
    initialize_investigation,
    load_graph_context,
    load_risk_context,
)
from apps.investigator.state import InvestigationState, InvestigationStatus
from domain.report import (
    Finding,
    InvestigationReport,
    RecommendedAction,
    ReportRiskLevel,
)
from domain.schemas import ToolErrorOut
from infrastructure.database.models import InvestigationCase
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


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


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #


def test_lifecycle_transitions_are_explicit() -> None:
    state = InvestigationState(transaction_id="TXN-001")
    assert state.status == InvestigationStatus.PENDING
    updates = asyncio.run(initialize_investigation(state))
    assert updates["status"] == InvestigationStatus.RUNNING


def test_failed_run_can_never_become_completed() -> None:
    """FAILED -> COMPLETED is forbidden, even with an empty error list."""
    state = InvestigationState(
        transaction_id="TXN-999",
        status=InvestigationStatus.FAILED,
        investigation_id="INV-0042",
    )
    updates = asyncio.run(assemble_evidence(state))
    assert updates["status"] == InvestigationStatus.FAILED


def test_completed_requires_no_errors() -> None:
    state = InvestigationState(
        transaction_id="TXN-001",
        status=InvestigationStatus.RUNNING,
        errors=[ToolErrorOut(error="DEPENDENCY_ERROR", detail="graph down")],
    )
    updates = asyncio.run(assemble_evidence(state))
    assert updates["status"] == InvestigationStatus.FAILED


# --------------------------------------------------------------------------- #
# Failure matrix
# --------------------------------------------------------------------------- #


def test_failure_transaction_not_found() -> None:
    final = asyncio.run(run_investigation_async("TXN-999"))
    assert final["status"] == "FAILED"
    assert final["evidence"] == []
    assert final["report"] is None
    assert final["errors"][0]["error"] == "NOT_FOUND"


def test_failure_graph_capability_degrades_with_warning() -> None:
    """Graph failure: structured warning, run continues, no exception leak."""
    from apps.investigator.capabilities import GraphCapability

    class _BrokenGraph(GraphCapability):
        async def _invoke(self, method: str, *args: Any):
            raise RuntimeError("simulated neo4j outage")

    async def _run() -> dict:
        state = InvestigationState(transaction_id="TXN-001")
        state = state.model_copy(
            update={
                "transaction": {
                    "transaction_id": "TXN-001",
                    "sender": {"external_id": "ACC-1001"},
                    "recipient": {"external_id": "ACC-9001"},
                }
            }
        )
        return await load_graph_context(state, graphs=_BrokenGraph())

    updates = asyncio.run(_run())
    assert updates["warnings"][0].error == "DEPENDENCY_ERROR"
    # No silent fallback: sections stay None (absent), never fabricated.
    assert "shared_devices" not in updates or updates["shared_devices"] is None
    dumped = json.dumps(updates, default=str).lower()
    assert "simulated neo4j outage" not in dumped  # no internal detail leakage
    assert "traceback" not in dumped


def test_failure_risk_capability_no_fabricated_score() -> None:
    """Risk failure: warning, no risk score, never a zero-fill."""
    from apps.investigator.capabilities import RiskCapability

    class _BrokenRisk(RiskCapability):
        async def _invoke(self, method: str, *args: Any):
            raise RuntimeError("simulated risk outage")

    async def _run() -> dict:
        state = InvestigationState(transaction_id="TXN-001")
        state = state.model_copy(
            update={
                "transaction": {
                    "transaction_id": "TXN-001",
                    "sender": {"external_id": "ACC-1001"},
                }
            }
        )
        return await load_risk_context(state, risks=_BrokenRisk())

    updates = asyncio.run(_run())
    assert updates["warnings"][0].error == "DEPENDENCY_ERROR"
    for key in ("risk_score", "risk_features", "risk_feature_importance"):
        assert key not in updates or updates[key] is None
    dumped = json.dumps(updates, default=str)
    assert '"risk_score": 0' not in dumped and '"risk_score":0' not in dumped


def test_failure_agent_down_is_explicit_not_fabricated() -> None:
    """Agent/provider crash -> structured DEPENDENCY_ERROR, no fake report."""
    from apps.investigator import agent as agent_module
    from apps.investigator import nodes as nodes_module

    class _Down:
        name = "down"
        model = "down-1"

        async def complete(self, system: str, user: str):
            raise TimeoutError("provider timeout")

    async def _run() -> dict:
        state = InvestigationState(transaction_id="TXN-001", status=InvestigationStatus.RUNNING)
        original = agent_module.get_llm_provider
        agent_module.get_llm_provider = lambda: _Down()  # type: ignore[assignment]
        try:
            return await nodes_module.analyze_with_agent(state)
        finally:
            agent_module.get_llm_provider = original  # type: ignore[assignment]

    updates = asyncio.run(_run())
    assert updates["errors"][0].error == "DEPENDENCY_ERROR"
    assert "TimeoutError" in updates["errors"][0].detail
    assert "report" not in updates


# --------------------------------------------------------------------------- #
# Report/evidence integrity guards (assemble_evidence)
# --------------------------------------------------------------------------- #


def _report_dict(transaction_id: str, evidence_ids: list[str]) -> dict[str, Any]:
    report = InvestigationReport(
        investigation_id="INV-0001",
        transaction_id=transaction_id,
        risk_level=ReportRiskLevel.HIGH,
        summary="test summary",
        findings=[
            Finding(finding="f1", evidence_ids=evidence_ids, confidence=0.9),
        ],
        recommended_action=RecommendedAction.HUMAN_REVIEW,
        confidence=0.8,
    )
    return report.model_dump(mode="json")


def _state_with(report: dict[str, Any] | None, evidence_ids: list[str]) -> InvestigationState:
    from apps.investigator.state import EvidenceCategory, EvidenceItem

    evidence = [
        EvidenceItem(
            evidence_id=eid,
            category=EvidenceCategory.TRANSACTION,
            source="transaction",
            reference="TXN-001",
            description="d",
        )
        for eid in evidence_ids
    ]
    return InvestigationState(
        transaction_id="TXN-001",
        status=InvestigationStatus.RUNNING,
        investigation_id="INV-0001",
        report=report,
        evidence=evidence,
    )


def test_report_referencing_unknown_evidence_fails_closed() -> None:
    state = _state_with(_report_dict("TXN-001", ["EV-001", "EV-999"]), ["EV-001"])
    updates = asyncio.run(assemble_evidence(state))
    assert updates["status"] == InvestigationStatus.FAILED
    assert updates["errors"][0].error == "VALIDATION_ERROR"
    assert "EV-999" in updates["errors"][0].detail


def test_report_with_mismatched_transaction_fails() -> None:
    state = _state_with(_report_dict("TXN-1006", ["EV-001"]), ["EV-001"])
    updates = asyncio.run(assemble_evidence(state))
    assert updates["status"] == InvestigationStatus.FAILED
    assert "does not match" in updates["errors"][0].detail


def test_duplicate_evidence_ids_fail_validation() -> None:
    state = _state_with(_report_dict("TXN-001", ["EV-001"]), ["EV-001", "EV-001"])
    updates = asyncio.run(assemble_evidence(state))
    assert updates["status"] == InvestigationStatus.FAILED
    assert "duplicate evidence ids" in updates["errors"][0].detail


def test_valid_report_passes_guard() -> None:
    state = _state_with(_report_dict("TXN-001", ["EV-001"]), ["EV-001"])
    updates = asyncio.run(assemble_evidence(state))
    assert updates["status"] == InvestigationStatus.COMPLETED


# --------------------------------------------------------------------------- #
# Latency + observability
# --------------------------------------------------------------------------- #


def test_node_timings_recorded_for_every_node() -> None:
    final = asyncio.run(run_investigation_async("TXN-001"))
    timings = final["node_timings_ms"]
    for node in (
        "initialize_investigation",
        "load_transaction",
        "load_account_context",
        "load_graph_context",
        "load_risk_context",
        "analyze_with_agent",
        "assemble_evidence",
    ):
        assert node in timings, f"missing timing for {node}"
        assert timings[node] >= 0.0


def test_lifecycle_log_events_emitted(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    with caplog.at_level(logging.INFO, logger="apps.investigator.nodes"):
        asyncio.run(run_investigation_async("TXN-001"))
    events = {r.message for r in caplog.records}
    assert {
        "investigation_started",
        "transaction_loaded",
        "account_loaded",
        "graph_loaded",
        "risk_loaded",
        "agent_started",
        "agent_completed",
        "evidence_validated",
        "investigation_completed",
    } <= events
    # Logs carry ids, not payloads or secrets.
    for record in caplog.records:
        assert "omerta_dev_password" not in str(record.__dict__)


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #


def test_repeated_runs_and_persistence_are_idempotent(test_engine: AsyncEngine) -> None:
    from infrastructure.database.persistence import persist_investigation

    first = asyncio.run(run_investigation_async("TXN-001"))
    assert first["status"] == "COMPLETED"
    kwargs: dict[str, Any] = {
        "investigation_id": first["investigation_id"],
        "transaction_id": first["transaction_id"],
        "alert_id": first.get("alert_id"),
        "report": first["report"],
        "evidence": first["evidence"],
    }
    result_one = asyncio.run(persist_investigation(test_engine, **kwargs))
    result_two = asyncio.run(persist_investigation(test_engine, **kwargs))
    assert result_one == result_two
    assert result_one["evidence_rows"] == len(first["evidence"])

    # Repeat runs stay safe (fresh loop each time; no driver/loop staleness).
    for _ in range(2):
        again = asyncio.run(run_investigation_async("TXN-001"))
        assert again["status"] == "COMPLETED"
        assert again["transaction_id"] == "TXN-001"


def test_three_sequential_runs_in_one_loop_are_stable() -> None:
    async def _run() -> list[dict[str, Any]]:
        return [await run_investigation_async("TXN-001") for _ in range(3)]

    results = asyncio.run(_run())
    assert all(r["status"] == "COMPLETED" for r in results)
    assert len({r["investigation_id"] for r in results}) == 3


def test_new_run_creates_distinct_historical_record(test_engine: AsyncEngine) -> None:
    """Same run id -> idempotent upsert; a genuinely new run -> a new case."""
    from infrastructure.database.models import InvestigationCase
    from infrastructure.database.persistence import persist_investigation
    from sqlalchemy import select

    run_one = asyncio.run(run_investigation_async("TXN-001"))
    result_one = asyncio.run(
        persist_investigation(
            test_engine,
            investigation_id=run_one["investigation_id"],
            transaction_id=run_one["transaction_id"],
            alert_id=run_one.get("alert_id"),
            report=run_one["report"],
            evidence=run_one["evidence"],
        )
    )
    run_two = asyncio.run(run_investigation_async("TXN-001"))  # new investigation
    assert run_two["investigation_id"] != run_one["investigation_id"]
    result_two = asyncio.run(
        persist_investigation(
            test_engine,
            investigation_id=run_two["investigation_id"],
            transaction_id=run_two["transaction_id"],
            alert_id=run_two.get("alert_id"),
            report=run_two["report"],
            evidence=run_two["evidence"],
        )
    )
    assert result_two["case_id"] != result_one["case_id"]

    async def _count() -> int:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            return len(
                (
                    await session.execute(
                        select(InvestigationCase).where(
                            InvestigationCase.external_id.in_(
                                [run_one["investigation_id"], run_two["investigation_id"]]
                            )
                        )
                    )
                ).all()
            )

    assert asyncio.run(_count()) >= 2


def test_alert_vs_mock_risk_regression_guard() -> None:
    """ALERT-001 (0.87, seeded fact) and the mock score (0.9, MOCK source)
    must coexist independently through the full pipeline - never conflated."""
    final = asyncio.run(run_investigation_async("TXN-001"))
    risk = final["risk_score"]
    assert risk["source"] == "MOCK"
    assert risk["model_version"] == "mock-risk-v1"
    assert risk["risk_score"] == 0.9
    assert risk["seeded_alert"]["alert_id"] == "ALERT-001"
    assert risk["seeded_alert"]["risk_score"] == "0.87"
    assert risk["seeded_alert"]["note"] == "seeded database fact, independent of the mock provider"
    # The report's provenance must not claim the mock score came from the alert.
    provenance = final["report"]["provenance"]
    assert provenance["risk_source"] == "MOCK"
    assert provenance["risk_model_version"] == "mock-risk-v1"


# --------------------------------------------------------------------------- #
# Concurrency + isolation
# --------------------------------------------------------------------------- #


def test_concurrent_investigations_are_isolated() -> None:
    async def _run() -> tuple[dict[str, Any], dict[str, Any]]:
        task_a = asyncio.create_task(run_investigation_async("TXN-001"))
        task_b = asyncio.create_task(run_investigation_async("TXN-1006"))
        return await asyncio.gather(task_a, task_b)

    run_a, run_b = asyncio.run(_run())
    assert run_a["status"] == "COMPLETED"
    assert run_b["status"] == "COMPLETED"

    # No cross-run state leakage.
    assert run_a["transaction_id"] == "TXN-001"
    assert run_b["transaction_id"] == "TXN-1006"
    assert run_a["report"]["transaction_id"] == "TXN-001"
    assert run_b["report"]["transaction_id"] == "TXN-1006"
    assert run_a["investigation_id"] != run_b["investigation_id"]

    # Evidence ids are unique within each run and consistent with its content.
    for run in (run_a, run_b):
        ids = [e["evidence_id"] for e in run["evidence"]]
        assert len(ids) == len(set(ids))
        assert all(e["reference"] for e in run["evidence"])


# --------------------------------------------------------------------------- #
# Persistence atomicity
# --------------------------------------------------------------------------- #


async def test_persistence_failure_rolls_back_case(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from infrastructure.database import persistence as persistence_module

    state = await run_investigation_async("TXN-001")

    async def _boom(session: AsyncSession, case: Any, evidence: list, txn: str) -> int:
        raise RuntimeError("simulated evidence-row failure")

    monkeypatch.setattr(persistence_module, "_persist_evidence_rows", _boom)
    with pytest.raises(RuntimeError, match="simulated evidence-row failure"):
        await persistence_module.persist_investigation(
            test_engine,
            investigation_id=state["investigation_id"],
            transaction_id=state["transaction_id"],
            alert_id=state.get("alert_id"),
            report=state["report"],
            evidence=state["evidence"],
        )

    # Atomic rollback: no half-persisted case remains.
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        count = await session.scalar(
            select(func.count())
            .select_from(InvestigationCase)
            .where(InvestigationCase.external_id == state["investigation_id"])
        )
    assert count == 0


# --------------------------------------------------------------------------- #
# Graph hardening
# --------------------------------------------------------------------------- #


def test_graph_reads_survive_repeated_investigations() -> None:
    """Repeated full runs re-read the graph cleanly (driver lifecycle)."""
    for i in range(2):
        final = asyncio.run(run_investigation_async("TXN-001"))
        assert final["status"] == "COMPLETED"
        assert final["graph_neighbors"] is not None
        if i == 0:
            continue
        assert final["shared_devices"] is not None


def test_workflow_graph_is_unchanged_and_compiles() -> None:
    app = build_investigation_graph()
    nodes = set(app.get_graph().nodes)
    assert {
        "initialize_investigation",
        "load_transaction",
        "load_account_context",
        "load_graph_context",
        "load_risk_context",
        "analyze_with_agent",
        "assemble_evidence",
    } <= nodes
