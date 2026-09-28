"""Phase 11 - evidence provenance tiers & investigation isolation."""

import asyncio
import json
from typing import Any

from apps.investigator.graph import run_investigation_async
from domain.services.audit_service import get_investigation_audit
from infrastructure.database.persistence import persist_investigation


def _run_and_persist(engine, transaction_id: str) -> dict[str, Any]:
    async def _flow() -> dict[str, Any]:
        state = await run_investigation_async(transaction_id)
        result = await persist_investigation(
            engine,
            investigation_id=state["investigation_id"],
            transaction_id=state["transaction_id"],
            alert_id=state.get("alert_id"),
            report=state["report"],
            evidence=state["evidence"],
            audit_events=state.get("audit_events", []),
        )
        return {"state": state, "result": result}

    return asyncio.run(_flow())


# --------------------------------------------------------------------------- #
# Provenance tiers
# --------------------------------------------------------------------------- #


def test_txn001_evidence_tiers_map_to_capabilities(pipeline_env) -> None:
    audit = asyncio.run(
        get_investigation_audit(
            pipeline_env, _run_and_persist(pipeline_env, "TXN-001")["result"]["case_id"]
        )
    )
    tiers = {e["tier"] for e in audit["evidence"]}
    assert tiers == {"FACT", "STRUCTURAL_SIGNAL", "MODEL_OUTPUT"}

    by_category = {e["category"]: e for e in audit["evidence"]}
    # Facts: PostgreSQL / transaction capability.
    for category in ("TRANSACTION", "ACCOUNT", "HISTORY", "DEVICE", "IP"):
        assert category in by_category
        assert by_category[category]["tier"] == "FACT"
        assert by_category[category]["source"] == "TRANSACTION"
        assert by_category[category]["producer"] == "TransactionCapability"
    # Structural signals: graph capability.
    assert by_category["GRAPH"]["tier"] == "STRUCTURAL_SIGNAL"
    assert by_category["GRAPH"]["producer"] == "GraphCapability"
    # Risk: model output with MOCK provenance preserved.
    assert by_category["RISK"]["tier"] == "MODEL_OUTPUT"
    assert by_category["RISK"]["producer"] == "RiskCapability"


def test_mock_risk_provenance_survives_persistence(pipeline_env) -> None:
    audit = asyncio.run(
        get_investigation_audit(
            pipeline_env, _run_and_persist(pipeline_env, "TXN-001")["result"]["case_id"]
        )
    )
    risk_items = [e for e in audit["evidence"] if e["category"] == "RISK"]
    assert risk_items
    dumped = json.dumps(risk_items)
    assert '"source": "MOCK"' in dumped or '"source":"MOCK"' in dumped or "MOCK" in dumped
    assert "mock-risk-v1" in dumped
    # The seeded alert stays a distinct fact: 0.87 must appear, un-merged
    # with the mock 0.9 score.
    seeded = [e for e in risk_items if e["category"] == "RISK" and "seeded_alert" in json.dumps(e)]
    assert seeded and "0.87" in json.dumps(seeded)


def test_agent_findings_are_not_labeled_as_facts(pipeline_env) -> None:
    """Agent output lives in the report with AGENT provenance - never in
    FACT-tier evidence rows."""
    flow = _run_and_persist(pipeline_env, "TXN-001")
    audit = asyncio.run(get_investigation_audit(pipeline_env, flow["result"]["case_id"]))

    fact_categories = {"TRANSACTION", "ACCOUNT", "HISTORY", "DEVICE", "IP"}
    for item in audit["evidence"]:
        if item["category"] in fact_categories:
            assert item["tier"] == "FACT"
            assert "agent" not in item["producer"].lower()

    report = audit["report"]
    assert report["provenance"]["llm_provider"]  # explicit agent provenance
    assert report["provenance"]["agent_version"]
    # Findings are distinct from fact rows: they live only in the report.
    finding_texts = {f["finding"] for f in report["findings"]}
    for item in audit["evidence"]:
        assert item["description"] not in finding_texts


def test_findings_reference_only_own_investigation_evidence(pipeline_env) -> None:
    flow = _run_and_persist(pipeline_env, "TXN-001")
    audit = asyncio.run(get_investigation_audit(pipeline_env, flow["result"]["case_id"]))
    valid_ids = {e["evidence_id"] for e in audit["evidence"]}
    assert audit["evidence"]
    for finding in audit["findings"]:
        assert finding["evidence_ids"]
        assert set(finding["evidence_ids"]) <= valid_ids


def test_evidence_completeness_for_txn001(pipeline_env) -> None:
    """Observable categories, not a fragile exact count."""
    audit = asyncio.run(
        get_investigation_audit(
            pipeline_env, _run_and_persist(pipeline_env, "TXN-001")["result"]["case_id"]
        )
    )
    categories = {e["category"] for e in audit["evidence"]}
    assert {"TRANSACTION", "ACCOUNT", "HISTORY", "DEVICE", "IP", "GRAPH", "RISK"} <= categories


# --------------------------------------------------------------------------- #
# Isolation (sequential + concurrent)
# --------------------------------------------------------------------------- #


def test_evidence_does_not_leak_between_investigations(pipeline_env) -> None:
    flow_a = _run_and_persist(pipeline_env, "TXN-001")
    flow_b = _run_and_persist(pipeline_env, "TXN-1006")
    audit_a = asyncio.run(get_investigation_audit(pipeline_env, flow_a["result"]["case_id"]))
    audit_b = asyncio.run(get_investigation_audit(pipeline_env, flow_b["result"]["case_id"]))

    ids_a = {e["evidence_id"] for e in audit_a["evidence"]}
    ids_b = {e["evidence_id"] for e in audit_b["evidence"]}
    # Evidence ids repeat per investigation (EV-001...), so isolation is
    # scoped by investigation: each row belongs to exactly one.
    assert ids_a and ids_b
    inv_a = {e["investigation_id"] for e in audit_a["evidence"]}
    inv_b = {e["investigation_id"] for e in audit_b["evidence"]}
    assert inv_a == {flow_a["result"]["case_id"]}
    assert inv_b == {flow_b["result"]["case_id"]}
    assert inv_a.isdisjoint(inv_b)
    # Findings reference only their own investigation's evidence.
    for audit in (audit_a, audit_b):
        valid = {e["evidence_id"] for e in audit["evidence"]}
        for finding in audit["findings"]:
            assert set(finding["evidence_ids"]) <= valid


def test_concurrent_investigations_stay_isolated(pipeline_env) -> None:
    async def _two() -> tuple[dict[str, Any], dict[str, Any]]:
        task_a = asyncio.create_task(run_investigation_async("TXN-001"))
        task_b = asyncio.create_task(run_investigation_async("TXN-1006"))
        state_a, state_b = await asyncio.gather(task_a, task_b)
        return state_a, state_b

    state_a, state_b = asyncio.run(_two())
    assert state_a["status"] == "COMPLETED" and state_b["status"] == "COMPLETED"
    result_a = asyncio.run(
        persist_investigation(
            pipeline_env,
            investigation_id=state_a["investigation_id"],
            transaction_id=state_a["transaction_id"],
            alert_id=state_a.get("alert_id"),
            report=state_a["report"],
            evidence=state_a["evidence"],
            audit_events=state_a.get("audit_events", []),
        )
    )
    result_b = asyncio.run(
        persist_investigation(
            pipeline_env,
            investigation_id=state_b["investigation_id"],
            transaction_id=state_b["transaction_id"],
            alert_id=state_b.get("alert_id"),
            report=state_b["report"],
            evidence=state_b["evidence"],
            audit_events=state_b.get("audit_events", []),
        )
    )
    assert result_a["case_id"] != result_b["case_id"]
    audit_a = asyncio.run(get_investigation_audit(pipeline_env, result_a["case_id"]))
    audit_b = asyncio.run(get_investigation_audit(pipeline_env, result_b["case_id"]))
    assert {e["investigation_id"] for e in audit_a["evidence"]} == {result_a["case_id"]}
    assert {e["investigation_id"] for e in audit_b["evidence"]} == {result_b["case_id"]}


# --------------------------------------------------------------------------- #
# Idempotency & new-run semantics
# --------------------------------------------------------------------------- #


def test_same_investigation_id_repersistence_is_idempotent(pipeline_env) -> None:
    flow = _run_and_persist(pipeline_env, "TXN-001")
    state = flow["state"]
    kwargs = dict(
        investigation_id=state["investigation_id"],
        transaction_id=state["transaction_id"],
        alert_id=state.get("alert_id"),
        report=state["report"],
        evidence=state["evidence"],
        audit_events=state.get("audit_events", []),
    )
    again = asyncio.run(persist_investigation(pipeline_env, **kwargs))
    assert again == flow["result"]
    audit = asyncio.run(get_investigation_audit(pipeline_env, state["investigation_id"]))
    ids = [e["evidence_id"] for e in audit["evidence"]]
    assert len(ids) == len(set(ids)) == len(state["evidence"])
    event_keys = [e["event_id"] for e in audit["audit_events"]]
    assert len(event_keys) == len(set(event_keys))


def test_new_investigation_gets_fresh_records(pipeline_env) -> None:
    first = _run_and_persist(pipeline_env, "TXN-001")
    second = _run_and_persist(pipeline_env, "TXN-001")
    assert first["result"]["case_id"] != second["result"]["case_id"]
    audit_one = asyncio.run(get_investigation_audit(pipeline_env, first["result"]["case_id"]))
    audit_two = asyncio.run(get_investigation_audit(pipeline_env, second["result"]["case_id"]))
    # Distinct audit trails; identical evidence shape (reproducibility).
    assert (
        audit_one["investigation"]["investigation_id"]
        != audit_two["investigation"]["investigation_id"]
    )
    assert len(audit_one["evidence"]) == len(audit_two["evidence"])
    assert [e["evidence_id"] for e in audit_one["evidence"]] == [
        e["evidence_id"] for e in audit_two["evidence"]
    ]


def test_evidence_ordering_is_deterministic(pipeline_env) -> None:
    case_id = _run_and_persist(pipeline_env, "TXN-001")["result"]["case_id"]
    one = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    two = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    assert [e["evidence_id"] for e in one["evidence"]] == [
        e["evidence_id"] for e in two["evidence"]
    ]
    assert one["evidence"] == two["evidence"]
