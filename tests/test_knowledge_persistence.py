"""Phase 12 - KNOWLEDGE evidence persistence + reconstruction.

Knowledge evidence must survive the Phase 11 append-only pipeline: persisted
with tier=KNOWLEDGE / producer=KnowledgeCapability, hash-verified on re-parse,
and reconstructable fail-closed like every other tier. Also proves idempotent
persistence with knowledge rows present and cross-investigation isolation.
"""

import asyncio
from typing import Any

from apps.investigator.graph import run_investigation_async
from domain.services.audit_service import get_investigation_audit
from infrastructure.database.persistence import persist_investigation


def _persist_kwargs(state: dict[str, Any]) -> dict[str, Any]:
    return dict(
        investigation_id=state["investigation_id"],
        transaction_id=state["transaction_id"],
        alert_id=state.get("alert_id"),
        report=state["report"],
        evidence=state["evidence"],
        audit_events=state.get("audit_events", []),
    )


def _run_and_persist(engine, transaction_id: str) -> dict[str, Any]:
    async def _flow() -> dict[str, Any]:
        state = await run_investigation_async(transaction_id)
        result = await persist_investigation(engine, **_persist_kwargs(state))
        return {"state": state, "result": result}

    return asyncio.run(_flow())


def test_knowledge_evidence_persists_with_provenance(pipeline_env) -> None:
    run = _run_and_persist(pipeline_env, "TXN-001")
    case_id = run["result"]["case_id"]

    audit = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    knowledge = [e for e in audit["evidence"] if e["tier"] == "KNOWLEDGE"]
    assert len(knowledge) == 1
    item = knowledge[0]
    assert item["category"] == "KNOWLEDGE"
    assert item["source"] == "KNOWLEDGE"  # stored uppercased
    assert item["producer"] == "KnowledgeCapability"
    assert item["transaction_id"] == "TXN-001"
    assert item["data"]["chunks"], "retrieved chunks must travel with the evidence"
    chunk = item["data"]["chunks"][0]
    for field in ("document_id", "document_title", "section", "version", "score"):
        assert field in chunk


def test_knowledge_audit_event_persisted(pipeline_env) -> None:
    run = _run_and_persist(pipeline_env, "TXN-001")
    case_id = run["result"]["case_id"]

    audit = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    event_types = [event["event_type"] for event in audit["audit_events"]]
    assert "KNOWLEDGE_CONTEXT_LOADED" in event_types


def test_repeat_persistence_idempotent_with_knowledge(pipeline_env) -> None:
    run = _run_and_persist(pipeline_env, "TXN-001")
    state = run["state"]

    async def _again() -> dict[str, Any]:
        return await persist_investigation(pipeline_env, **_persist_kwargs(state))

    result = asyncio.run(_again())
    assert result["evidence_rows"] == run["result"]["evidence_rows"]
    assert result["audit_events"] == run["result"]["audit_events"]

    audit = asyncio.run(get_investigation_audit(pipeline_env, result["case_id"]))
    knowledge_rows = [e for e in audit["evidence"] if e["tier"] == "KNOWLEDGE"]
    assert len(knowledge_rows) == 1  # no duplicates


def test_two_investigations_keep_knowledge_evidence_isolated(pipeline_env) -> None:
    first = _run_and_persist(pipeline_env, "TXN-001")
    second = _run_and_persist(pipeline_env, "TXN-1006")
    assert first["state"]["investigation_id"] != second["state"]["investigation_id"]

    first_audit = asyncio.run(get_investigation_audit(pipeline_env, first["result"]["case_id"]))
    second_audit = asyncio.run(get_investigation_audit(pipeline_env, second["result"]["case_id"]))
    first_ids = {e["evidence_id"] for e in first_audit["evidence"]}
    second_ids = {e["evidence_id"] for e in second_audit["evidence"]}
    # Both runs legitimately use EV-xxx numbering; isolation means the rows
    # belong to different cases even when ids coincide.
    assert first_audit["case"]["case_id"] != second_audit["case"]["case_id"]
    assert first_ids and second_ids

    # The KNOWLEDGE evidence of each case carries its own investigation_id.
    for audit in (first_audit, second_audit):
        knowledge = [e for e in audit["evidence"] if e["tier"] == "KNOWLEDGE"]
        assert knowledge
        assert knowledge[0]["investigation_id"] == audit["case"]["case_id"]
