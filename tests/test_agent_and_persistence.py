"""Phase 9 tests: agent report generation, evidence integrity, persistence."""

import asyncio
import json
from typing import Any

import pytest
from apps.investigator.agent import _rule_based_fallback, run_agent
from apps.investigator.graph import run_investigation_async
from domain.report import AgentOutcome, RecommendedAction, Typology
from infrastructure.database.models import Evidence, InvestigationCase
from infrastructure.database.persistence import persist_investigation
from infrastructure.llm.base import LLMResponse
from infrastructure.llm.fake_provider import FakeLLMProvider
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.fixture(autouse=True)
def seeded_environment(test_engine: AsyncEngine, graph_test_projection: str) -> None:
    """Seed PostgreSQL and project to Neo4j before each test."""

    async def _seed() -> None:
        from infrastructure.config import get_settings
        from infrastructure.database.seed import reset_all, seed
        from infrastructure.neo4j import client as graph_client
        from infrastructure.neo4j.projection import project_all

        from neo4j import AsyncGraphDatabase

        settings = get_settings()
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
# Agent unit tests (deterministic fake provider - no network)
# --------------------------------------------------------------------------- #


def _snapshot() -> dict[str, Any]:
    """Minimal snapshot with evidence for unit tests."""
    return {
        "investigation_id": "INV-0001",
        "transaction_id": "TXN-001",
        "transaction": {
            "amount": "8400.00",
            "currency": "USD",
            "transaction_type": "WIRE",
            "is_new_device": True,
            "is_new_ip": True,
        },
        "risk_score": {"risk_score": 0.9, "risk_level": "HIGH", "source": "MOCK"},
        "fraud_ring_signals": {
            "signals": [
                {
                    "type": "SHARED_DEVICE",
                    "entity_id": "DEV-123",
                    "connected_accounts": ["ACC-3001"],
                    "description": "structural signal",
                }
            ]
        },
        "evidence": [
            {
                "evidence_id": "EV-001",
                "category": "TRANSACTION",
                "reference": "TXN-001",
                "description": "facts",
            },
            {
                "evidence_id": "EV-002",
                "category": "GRAPH",
                "reference": "ACC-1001",
                "description": "signal",
            },
            {
                "evidence_id": "EV-003",
                "category": "RISK",
                "reference": "TXN-001",
                "description": "score",
            },
        ],
    }


def test_rule_based_fallback_references_real_evidence() -> None:
    raw = _rule_based_fallback(_snapshot())
    valid = {item["evidence_id"] for item in _snapshot()["evidence"]}
    for finding in raw["findings"]:
        assert set(finding["evidence_ids"]).issubset(valid)
    assert raw["recommended_action"] == "HUMAN_REVIEW"


async def test_run_agent_with_fake_provider_produces_valid_report() -> None:
    outcome = await run_agent(_snapshot(), provider=FakeLLMProvider())

    assert isinstance(outcome, AgentOutcome)
    assert outcome.evidence_count == 3
    assert outcome.report.recommended_action == RecommendedAction.HUMAN_REVIEW
    assert outcome.report.typologies  # graph signals present
    assert outcome.report.provenance["llm_provider"] == "fake"
    assert outcome.report.provenance["risk_source"] == "MOCK"
    valid = {item["evidence_id"] for item in _snapshot()["evidence"]}
    for finding in outcome.report.findings:
        assert set(finding.evidence_ids).issubset(valid)


async def test_run_agent_rejects_unknown_evidence_ids() -> None:
    """A misbehaving LLM inventing evidence ids cannot pass validation."""
    calls: list[int] = []

    class BadProvider(FakeLLMProvider):
        name = "bad-llm"

        async def complete(self, system: str, user: str, **kwargs: Any) -> LLMResponse:
            calls.append(1)
            payload = {
                "risk_level": "HIGH",
                "summary": "suspicious",
                "findings": [
                    {"finding": "invented", "evidence_ids": ["EV-999"], "confidence": 0.9}
                ],
                "recommended_action": "CLOSE_NO_ACTION",
                "confidence": 0.9,
            }
            return LLMResponse(content=json.dumps(payload), provider=self.name, model=self.model)

    with pytest.raises(RuntimeError, match="could not produce a valid"):
        await run_agent(_snapshot(), provider=BadProvider())
    assert len(calls) == 2  # initial attempt + repair attempt, then explicit failure


async def test_run_agent_repairs_invalid_output() -> None:
    """First reply is invalid (no findings); repair pass returns valid JSON."""
    calls: list[int] = []

    class RepairProvider(FakeLLMProvider):
        name = "repair-llm"

        async def complete(self, system: str, user: str, **kwargs: Any) -> LLMResponse:
            calls.append(1)
            if len(calls) == 1:
                payload = {
                    "risk_level": "HIGH",
                    "summary": "first attempt broken",
                    "findings": [],
                    "recommended_action": "MONITOR",
                    "confidence": 0.5,
                }
            else:
                payload = {
                    "risk_level": "HIGH",
                    "summary": "repaired",
                    "typologies": ["LAYERING", "NOT_A_TYPOLOGY"],
                    "findings": [{"finding": "ok", "evidence_ids": ["EV-001"], "confidence": 0.8}],
                    "recommended_action": "MONITOR",
                    "confidence": 0.8,
                }
            return LLMResponse(content=json.dumps(payload), provider=self.name, model=self.model)

    outcome = await run_agent(_snapshot(), provider=RepairProvider())
    assert len(calls) == 2
    assert outcome.report.typologies == [Typology.LAYERING]  # unknown filtered
    assert outcome.report.summary == "repaired"


# --------------------------------------------------------------------------- #
# End-to-end through the real graph (seeded DBs)
# --------------------------------------------------------------------------- #


def test_full_graph_txn001_produces_report() -> None:
    final = asyncio.run(run_investigation_async("TXN-001"))

    assert final["status"] == "COMPLETED"
    report = final["report"]
    assert report["transaction_id"] == "TXN-001"
    assert report["risk_level"] == "HIGH"
    assert report["recommended_action"] == "HUMAN_REVIEW"
    valid = {item["evidence_id"] for item in final["evidence"]}
    for finding in report["findings"]:
        assert set(finding["evidence_ids"]).issubset(valid)
    assert report["provenance"]["risk_source"] == "MOCK"
    assert report["provenance"]["llm_provider"] == "fake"


def test_full_graph_txn999_has_no_report() -> None:
    final = asyncio.run(run_investigation_async("TXN-999"))
    assert final["status"] == "FAILED"
    assert final["report"] is None


def test_full_graph_report_is_deterministic() -> None:
    """Same seeded input -> identical report (fake provider path)."""
    first = asyncio.run(run_investigation_async("TXN-001"))
    second = asyncio.run(run_investigation_async("TXN-001"))
    assert first["report"]["summary"] == second["report"]["summary"]
    assert first["report"]["findings"] == second["report"]["findings"]
    assert first["report"]["recommended_action"] == second["report"]["recommended_action"]


# --------------------------------------------------------------------------- #
# Persistence tests
# --------------------------------------------------------------------------- #


def _report(risk_level: str = "HIGH") -> dict[str, Any]:
    return {
        "risk_level": risk_level,
        "summary": "deterministic report",
        "typologies": ["MULE_ACCOUNT"],
        "findings": [
            {"finding": "shared device signal", "evidence_ids": ["EV-007"], "confidence": 0.8}
        ],
        "recommended_action": "HUMAN_REVIEW",
        "provenance": {"llm_provider": "fake", "risk_source": "MOCK"},
    }


def _evidence() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "EV-001",
            "category": "TRANSACTION",
            "source": "transaction",
            "reference": "TXN-001",
            "description": "facts",
            "data": {"amount": "8400.00"},
        },
        {
            "evidence_id": "EV-002",
            "category": "GRAPH",
            "source": "graph",
            "reference": "ACC-1001",
            "description": "signal",
            "data": {},
        },
    ]


def test_persist_investigation_creates_case_and_evidence(test_engine: AsyncEngine) -> None:
    async def _persist() -> dict[str, Any]:
        return await persist_investigation(
            test_engine,
            investigation_id="INV-TEST-002",
            transaction_id="TXN-001",
            alert_id="ALERT-001",
            report=_report(),
            evidence=_evidence(),
        )

    result = asyncio.run(_persist())
    assert result["case_id"] == "INV-TEST-002"
    assert result["case_status"] == "REVIEW"  # pending human review, never auto-final
    assert result["evidence_rows"] == 2

    async def _verify() -> None:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            case = await session.scalar(
                select(InvestigationCase).where(InvestigationCase.external_id == "INV-TEST-002")
            )
            assert case is not None
            assert case.severity == "HIGH"
            rows = (
                await session.scalars(select(Evidence).where(Evidence.case_id == case.id))
            ).all()
            assert {row.evidence_type for row in rows} == {"TRANSACTION", "GRAPH"}
            assert all(row.source_reference for row in rows)

    asyncio.run(_verify())


def test_persistence_is_idempotent(test_engine: AsyncEngine) -> None:
    kwargs: dict[str, Any] = {
        "investigation_id": "INV-TEST-003",
        "transaction_id": "TXN-001",
        "alert_id": "ALERT-001",
        "report": _report(),
        "evidence": _evidence()[:1],
    }

    first = asyncio.run(persist_investigation(test_engine, **kwargs))
    second = asyncio.run(persist_investigation(test_engine, **kwargs))
    assert first["case_id"] == second["case_id"]
    assert first["evidence_rows"] == second["evidence_rows"] == 1

    async def _count() -> int:
        async with AsyncSession(test_engine, expire_on_commit=False) as session:
            case = await session.scalar(
                select(InvestigationCase).where(InvestigationCase.external_id == "INV-TEST-003")
            )
            assert case is not None
            rows = (
                await session.scalars(select(Evidence).where(Evidence.case_id == case.id))
            ).all()
            return len(rows)

    assert asyncio.run(_count()) == 1


def test_persistence_requires_alert_linkage(test_engine: AsyncEngine) -> None:
    """TXN-1002 has no seeded alert: persisting a case for it must fail clearly."""

    async def _run() -> None:
        await persist_investigation(
            test_engine,
            investigation_id="INV-TEST-NOALERT",
            transaction_id="TXN-1002",
            alert_id=None,
            report=_report(risk_level="LOW"),
            evidence=[],
        )

    with pytest.raises(ValueError, match="alert linkage"):
        asyncio.run(_run())


def test_persistence_rejects_unknown_transaction(test_engine: AsyncEngine) -> None:
    async def _run() -> None:
        await persist_investigation(
            test_engine,
            investigation_id="INV-TEST-BADTXN",
            transaction_id="TXN-999",
            alert_id=None,
            report=_report(),
            evidence=[],
        )

    with pytest.raises(ValueError, match="unknown transaction"):
        asyncio.run(_run())
