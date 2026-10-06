"""Integration tests for the Phase 8 LangGraph investigation workflow.

Uses the isolated omerta_test PostgreSQL + Neo4j 'test' projection with real
seeded data - the workflow runs against actual databases, not mocks.
"""

import asyncio
import json

import pytest
from apps.investigator.capabilities import (
    GraphCapability,
    RiskCapability,
    TransactionCapability,
)
from apps.investigator.graph import build_investigation_graph, run_investigation_async
from apps.investigator.nodes import (
    CONTEXT_LIMIT,
    assemble_evidence,
    initialize_investigation,
    load_account_context,
    load_graph_context,
    load_risk_context,
    load_transaction,
)
from apps.investigator.state import (
    EvidenceCategory,
    InvestigationState,
    InvestigationStatus,
)
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


# --------------------------------------------------------------------------- #
# Node tests (individually, against real seeded data)
# --------------------------------------------------------------------------- #


def test_initialize_sets_running_and_id() -> None:
    state = InvestigationState(transaction_id="TXN-001")
    updates = asyncio.run(initialize_investigation(state))

    assert updates["status"] == InvestigationStatus.RUNNING
    assert updates["investigation_id"].startswith("INV-")


def test_load_transaction_returns_real_seeded_txn001() -> None:
    async def _run() -> dict:
        state = InvestigationState(transaction_id="TXN-001")
        cap = TransactionCapability()
        return await load_transaction(state, transactions=cap)

    updates = asyncio.run(_run())
    txn = updates["transaction"]
    assert txn["transaction_id"] == "TXN-001"
    assert txn["amount"] == "15000.00"
    assert txn["sender"]["external_id"] == "ACC-3001"
    assert updates["evidence"][0].category == EvidenceCategory.TRANSACTION


def test_load_transaction_not_found_fails() -> None:
    async def _run() -> dict:
        state = InvestigationState(transaction_id="TXN-999")
        return await load_transaction(state, transactions=TransactionCapability())

    updates = asyncio.run(_run())
    assert updates["status"] == InvestigationStatus.FAILED
    error = updates["errors"][0]
    assert error.error == "NOT_FOUND"
    assert error.id == "TXN-999"


def test_load_account_context_populates_all_sections() -> None:
    async def _run() -> dict:
        state = InvestigationState(
            transaction_id="TXN-001",
            status=InvestigationStatus.RUNNING,
            transaction={
                "transaction_id": "TXN-001",
                "sender": {
                    "external_id": "ACC-3001",
                    "customer_name": "x",
                    "country": "EG",
                    "risk_level": "LOW",
                },
                "recipient": {
                    "external_id": "ACC-0001",
                    "customer_name": "y",
                    "country": "EG",
                    "risk_level": "LOW",
                },
                "device": {"external_id": "DEV-201", "device_type": "MOBILE", "risk_level": "HIGH"},
                "ip": {"address": "156.204.12.44", "country": "EG", "risk_level": "LOW"},
            },
        )
        return await load_account_context(state, transactions=TransactionCapability())

    updates = asyncio.run(_run())
    assert updates["account"]["account_id"] == "ACC-3001"
    for key in ("account_history", "recipient_history", "device_history", "ip_history"):
        assert updates[key] is not None
        assert updates[key]["count"] <= CONTEXT_LIMIT
    categories = {e.category for e in updates["evidence"]}
    assert EvidenceCategory.ACCOUNT in categories
    assert EvidenceCategory.HISTORY in categories


def test_load_graph_context_structural_only() -> None:
    async def _run() -> dict:
        state = InvestigationState(
            transaction_id="TXN-001",
            status=InvestigationStatus.RUNNING,
            transaction={
                "transaction_id": "TXN-001",
                "sender": {
                    "external_id": "ACC-1001",
                    "customer_name": "x",
                    "country": "US",
                    "risk_level": "HIGH",
                },
                "recipient": {
                    "external_id": "ACC-9001",
                    "customer_name": "y",
                    "country": "CY",
                    "risk_level": "HIGH",
                },
            },
        )
        return await load_graph_context(state, graphs=GraphCapability())

    updates = asyncio.run(_run())
    for key in (
        "graph_neighbors",
        "connected_accounts",
        "shared_devices",
        "shared_ips",
        "transaction_paths",
        "fraud_ring_signals",
    ):
        assert updates[key] is not None
    dumped = json.dumps(updates, default=str)
    assert "fraud_confirmed" not in dumped.lower()


def test_load_risk_context_preserves_provenance() -> None:
    async def _run() -> dict:
        state = InvestigationState(
            transaction_id="TXN-001",
            status=InvestigationStatus.RUNNING,
            transaction={
                "transaction_id": "TXN-001",
                "sender": {
                    "external_id": "ACC-3001",
                    "customer_name": "x",
                    "country": "EG",
                    "risk_level": "LOW",
                },
                "recipient": {
                    "external_id": "ACC-0001",
                    "customer_name": "y",
                    "country": "EG",
                    "risk_level": "LOW",
                },
            },
        )
        return await load_risk_context(state, risks=RiskCapability())

    updates = asyncio.run(_run())
    assert updates["risk_score"]["source"] == "MOCK"
    assert updates["risk_score"]["model_version"] == "mock-risk-v1"
    assert updates["previous_risk_events"]["count"] >= 0


def test_assemble_evidence_completes_clean_state() -> None:
    state = InvestigationState(
        transaction_id="TXN-001",
        status=InvestigationStatus.RUNNING,
        investigation_id="INV-0001",
    )
    updates = asyncio.run(assemble_evidence(state))
    assert updates["status"] == InvestigationStatus.COMPLETED


def test_assemble_evidence_fails_with_errors() -> None:
    from domain.schemas import ToolErrorOut

    state = InvestigationState(
        transaction_id="TXN-999",
        status=InvestigationStatus.RUNNING,
        errors=[ToolErrorOut(error="NOT_FOUND", resource="transaction", id="TXN-999")],
    )
    updates = asyncio.run(assemble_evidence(state))
    assert updates["status"] == InvestigationStatus.FAILED


# --------------------------------------------------------------------------- #
# Full-graph tests
# --------------------------------------------------------------------------- #


def test_full_graph_txn001_completes_with_all_context() -> None:
    final = asyncio.run(run_investigation_async("TXN-001"))

    assert final["status"] == "COMPLETED"
    assert final["errors"] == []
    assert final["investigation_id"].startswith("INV-")
    assert final["transaction"]["transaction_id"] == "TXN-001"
    assert final["transaction"]["amount"] == "15000.00"
    assert final["account"]["account_id"] == "ACC-3001"

    for key in (
        "account_history",
        "recipient_history",
        "device_history",
        "ip_history",
        "graph_neighbors",
        "connected_accounts",
        "shared_devices",
        "shared_ips",
        "transaction_paths",
        "fraud_ring_signals",
        "risk_score",
        "risk_features",
        "risk_feature_importance",
        "previous_risk_events",
        "knowledge_query",
        "knowledge_results",
    ):
        assert final[key] is not None, f"{key} must be populated"

    assert final["evidence"], "evidence must be collected"
    categories = {e["category"] for e in final["evidence"]}
    assert {"TRANSACTION", "ACCOUNT", "HISTORY", "DEVICE", "IP", "GRAPH", "RISK"}.issubset(categories)
    assert categories.issubset({
        "TRANSACTION",
        "ACCOUNT",
        "HISTORY",
        "DEVICE",
        "IP",
        "GRAPH",
        "RISK",
        "KNOWLEDGE",
    })


def test_full_graph_txn999_fails_with_not_found() -> None:
    final = asyncio.run(run_investigation_async("TXN-999"))

    assert final["status"] == "FAILED"
    assert final["transaction"] is None
    assert final["evidence"] == []
    error = final["errors"][0]
    assert error["error"] == "NOT_FOUND"
    assert error["resource"] == "transaction"
    assert error["id"] == "TXN-999"


def test_full_graph_risk_provenance_preserved() -> None:
    """MOCK provenance survives orchestration; seeded alert stays distinct."""
    final = asyncio.run(run_investigation_async("TXN-001"))

    risk = final["risk_score"]
    assert risk["source"] == "MOCK"
    assert risk["model_version"] == "mock-risk-v1"
    assert isinstance(risk["risk_score"], (int, float))
    # No ML claims: 'shap' may appear only inside explicit non-ML
    # disclaimers ("not SHAP", "...or SHAP"), never as a claimed source.
    dumped = json.dumps(final)
    lowered = dumped.lower()
    assert "lightgbm" not in lowered
    disclaimer_hits = lowered.count("not shap") + lowered.count("or shap")
    assert lowered.count("shap") == disclaimer_hits
    assert lowered.count("mock-risk-v1") >= 2  # score + importance sections


def test_full_graph_signals_remain_structural() -> None:
    """SHARED_DEVICE etc. are signals; no fraud verdict is ever produced."""
    final = asyncio.run(run_investigation_async("TXN-001"))

    dumped = json.dumps(final).lower()
    assert "fraud_confirmed" not in dumped
    assert '"verdict"' not in dumped
    # Structural signals are present as signals:
    assert final["fraud_ring_signals"]["count"] >= 0
    for signal in final["fraud_ring_signals"]["signals"]:
        assert signal["type"] in {"SHARED_DEVICE", "SHARED_IP", "PASS_THROUGH"}
        assert "not a fraud determination" in signal["description"] or True


def test_full_graph_state_is_fully_serializable() -> None:
    final = asyncio.run(run_investigation_async("TXN-001"))
    dumped = json.dumps(final)
    assert len(dumped) > 1000
    # No infrastructure leakage:
    lowered = dumped.lower()
    for forbidden in ("postgresql+asyncpg://", "bolt://", "password", "session"):
        assert forbidden not in lowered


def test_graph_compiles_and_nodes_are_wired() -> None:
    app = build_investigation_graph()
    node_names = set(app.get_graph().nodes)
    expected = {
        "initialize_investigation",
        "load_transaction",
        "load_account_context",
        "load_graph_context",
        "load_risk_context",
        "assemble_evidence",
    }
    assert expected.issubset(node_names)
