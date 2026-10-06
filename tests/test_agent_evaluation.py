"""Phase 15 - agent evaluation (scenario-based, deterministic, observable).

For each seeded scenario the full pipeline (orchestrator + agent, fake LLM)
must produce a structurally valid investigation. Assertions target observable
properties - valid report, correct transaction, valid risk provenance, valid
evidence and knowledge references, allowed recommendations, confidence bounds
- never exact natural-language wording.
"""

import asyncio

import pytest
from apps.investigator.graph import run_investigation_async
from domain.report import RecommendedAction, ReportRiskLevel, Typology
from infrastructure.database.seed import reset_all, seed
from sqlalchemy.ext.asyncio import AsyncEngine

SCENARIOS = {
    "TXN-001": {"transaction": "TXN-001", "amount": "8400.00", "account": "ACC-1001"},
    "TXN-1006": {"transaction": "TXN-1006", "amount": "4250.00", "account": "ACC-3001"},
    "TXN-1001": {"transaction": "TXN-1001", "amount": "125.00", "account": "ACC-1001"},
}


@pytest.fixture(autouse=True)
def seeded_db_sync(test_engine: AsyncEngine) -> None:
    async def _seed() -> None:
        await reset_all(test_engine)
        await seed(test_engine)

    asyncio.run(_seed())


@pytest.mark.parametrize("transaction_id", sorted(SCENARIOS))
def test_scenario_evaluation(transaction_id: str) -> None:
    final = asyncio.run(run_investigation_async(transaction_id))
    expected = SCENARIOS[transaction_id]

    # --- valid report, correct transaction.
    assert final["status"] == "COMPLETED"
    report = final["report"]
    assert report["transaction_id"] == expected["transaction"]
    assert report["summary"]

    # --- transaction context correct.
    assert final["transaction"]["transaction_id"] == expected["transaction"]
    assert final["transaction"]["amount"] == expected["amount"]
    assert final["account"]["account_id"] == expected["account"]

    # --- valid risk provenance (MOCK by default; seeded alert separate).
    risk = final["risk_score"]
    assert risk["source"] in {"MOCK", "ML"}
    assert risk["model_version"]
    assert 0.0 <= risk["risk_score"] <= 1.0
    assert risk["risk_level"] in {"LOW", "MEDIUM", "HIGH"}

    # --- evidence + knowledge references valid.
    valid_ids = {item["evidence_id"] for item in final["evidence"]}
    assert final["evidence"]
    knowledge = [i for i in final["evidence"] if i["category"] == "KNOWLEDGE"]
    assert knowledge, "every scenario should retrieve policy context"
    for item in knowledge:
        chunks = item["data"]["chunks"]
        assert chunks
        assert all(c["document_id"] and c["section"] for c in chunks)

    # --- findings grounded, bounded confidence, valid categories.
    assert report["findings"]
    for finding in report["findings"]:
        assert finding["evidence_ids"]
        assert set(finding["evidence_ids"]) <= valid_ids
        assert 0.0 <= finding["confidence"] <= 1.0
        if finding.get("category"):
            assert finding["category"] in {
                "TRANSACTION",
                "ACCOUNT",
                "HISTORY",
                "DEVICE",
                "IP",
                "GRAPH",
                "RISK",
                "KNOWLEDGE",
            }

    # --- typologies + recommendation within enums; confidence bounded.
    assert all(t in Typology.__members__ for t in report["typologies"])
    assert report["recommended_action"] in {a.value for a in RecommendedAction}
    assert report["recommended_action"] != ""  # always an explicit recommendation
    assert 0.0 <= report["confidence"] <= 1.0

    # --- risk level of the report within the controlled set.
    assert report["risk_level"] in {level.value for level in ReportRiskLevel}

    # --- audit trail covers the workflow end to end.
    event_types = {e["event_type"] for e in final["audit_events"]}
    assert {
        "INVESTIGATION_STARTED",
        "TRANSACTION_LOADED",
        "KNOWLEDGE_CONTEXT_LOADED",
        "AGENT_STARTED",
        "AGENT_COMPLETED",
        "REPORT_CREATED",
        "INVESTIGATION_COMPLETED",
    } <= event_types


def test_scenario_risk_levels_order_sensibly() -> None:
    """HIGH scenario must not be calmer than the clean one (observably)."""
    high = asyncio.run(run_investigation_async("TXN-001"))
    clean = asyncio.run(run_investigation_async("TXN-1001"))
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    assert order[high["report"]["risk_level"]] >= order[clean["report"]["risk_level"]]
    assert high["report"]["recommended_action"] == RecommendedAction.HUMAN_REVIEW.value


def test_no_unsupported_claims_in_summaries() -> None:
    """Summaries must not assert confirmed fraud (structural language only)."""
    for txn in SCENARIOS:
        final = asyncio.run(run_investigation_async(txn))
        summary = final["report"]["summary"].lower()
        assert "fraud confirmed" not in summary
        assert "guilty" not in summary
