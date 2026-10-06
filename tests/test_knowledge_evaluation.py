"""Phase 12 - RAG evaluation (deterministic, scenario-based).

Evaluation questions per the Phase 12 spec, answered with observable
properties - never exact wording:

- retrieval relevance: scenario queries surface genuinely relevant documents;
- source correctness: every cited document/section resolves in the store;
- citation correctness: agent knowledge findings name document + section;
- version correctness: cited version equals the stored document version;
- answer grounding: every finding's evidence ids resolve to same-run evidence.

The fake provider keeps the whole pipeline deterministic, so these checks are
stable regression guards, not flaky LLM grading.
"""

import asyncio
from typing import Any

import pytest
from apps.investigator.graph import run_investigation_async
from domain.services.knowledge_service import KnowledgeService
from infrastructure.database.seed import reset_all, seed
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


@pytest.fixture(autouse=True)
def seeded_db_sync(test_engine: AsyncEngine) -> None:
    async def _seed() -> None:
        await reset_all(test_engine)
        await seed(test_engine)

    asyncio.run(_seed())


def _knowledge_evidence(final: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (item for item in final["evidence"] if item["category"] == "KNOWLEDGE"),
        None,
    )


def _knowledge_finding(report: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (f for f in report["findings"] if f.get("category") == "KNOWLEDGE"),
        None,
    )


SCENARIOS = ("TXN-001", "TXN-1006", "TXN-1001")


@pytest.mark.parametrize("transaction_id", SCENARIOS)
def test_retrieval_relevance_and_citation_integrity(transaction_id: str, test_engine) -> None:
    """One deterministic pass per scenario answering all evaluation questions."""

    async def _flow(engine) -> dict[str, Any]:
        final = await run_investigation_async(transaction_id)
        # Same loop: resolve every citation against the store.
        async with AsyncSession(engine, expire_on_commit=False) as session:
            service = KnowledgeService(session)
            stored = {}
            item = _knowledge_evidence(final)
            if item:
                for chunk in item["data"]["chunks"]:
                    document = await service.get_document(chunk["document_id"])
                    section = await service.get_document_section(
                        chunk["document_id"], chunk["section"]
                    )
                    stored[chunk["chunk_id"]] = (document, section, chunk)
        return final, stored

    final, stored = asyncio.run(_flow(test_engine))

    assert final["status"] == "COMPLETED"
    results = final["knowledge_results"]
    assert results is not None and results["count"] >= 1

    # --- retrieval relevance: top chunk has positive score and full provenance.
    top = results["results"][0]
    assert top["score"] > 0
    assert top["document_id"] and top["section"]

    # --- source correctness: each cited chunk resolves to stored content.
    item = _knowledge_evidence(final)
    assert item is not None
    for chunk in item["data"]["chunks"]:
        document, section, _ = stored[chunk["chunk_id"]]
        assert document.document_id == chunk["document_id"]
        assert section.content == chunk["content"]  # verbatim stored text

    # --- version correctness: cited version == stored document version.
    for chunk in item["data"]["chunks"]:
        document, _, _ = stored[chunk["chunk_id"]]
        assert chunk["version"] == document.version

    # --- citation correctness + answer grounding.
    finding = _knowledge_finding(final["report"])
    assert finding is not None
    assert item["evidence_id"] in finding["evidence_ids"]
    assert top["document_title"] in finding["finding"]
    assert top["section"] in finding["finding"]

    valid_ids = {e["evidence_id"] for e in final["evidence"]}
    for any_finding in final["report"]["findings"]:
        assert set(any_finding["evidence_ids"]) <= valid_ids


def test_high_risk_scenario_surfaces_takeover_or_threshold_guidance() -> None:
    """TXN-001 (HIGH, new device/IP, $8400): guidance must be on-topic."""
    final = asyncio.run(run_investigation_async("TXN-001"))
    item = _knowledge_evidence(final)
    assert item is not None
    docs = {chunk["document_id"] for chunk in item["data"]["chunks"]}
    assert docs & {
        "DOC-FATF-TYPOLOGIES",  # account takeover typology
        "DOC-THRESHOLD-POLICY",  # large transaction review threshold
        "DOC-SHARED-DEVICE-POLICY",  # escalation rule (>= 4000 USD)
    }, f"off-topic guidance for high-risk scenario: {docs}"


def test_shared_device_scenario_surfaces_shared_infrastructure_guidance() -> None:
    """TXN-1006 (shared device): the procedure/typology docs must surface."""
    final = asyncio.run(run_investigation_async("TXN-1006"))
    item = _knowledge_evidence(final)
    assert item is not None
    docs = {chunk["document_id"] for chunk in item["data"]["chunks"]}
    assert docs & {"DOC-SHARED-DEVICE-POLICY", "DOC-FATF-TYPOLOGIES"}, (
        f"off-topic guidance for shared-device scenario: {docs}"
    )
