"""Phase 11 - historical reconstruction of persisted investigations."""

import asyncio
import json
from typing import Any

import pytest
from apps.investigator.graph import run_investigation_async
from domain.services.audit_service import ReconstructionError, get_investigation_audit
from infrastructure.database.models import InvestigationCase
from infrastructure.database.persistence import persist_investigation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _persist_kwargs(state: dict[str, Any]) -> dict[str, Any]:
    return dict(
        investigation_id=state["investigation_id"],
        transaction_id=state["transaction_id"],
        alert_id=state.get("alert_id"),
        report=state["report"],
        evidence=state["evidence"],
        audit_events=state.get("audit_events", []),
    )


def _run_and_persist(engine, transaction_id: str) -> str:
    async def _flow() -> str:
        state = await run_investigation_async(transaction_id)
        result = await persist_investigation(engine, **_persist_kwargs(state))
        return result["case_id"]

    return asyncio.run(_flow())


def test_reconstruction_contains_all_sections(pipeline_env) -> None:
    case_id = _run_and_persist(pipeline_env, "TXN-001")
    audit = asyncio.run(get_investigation_audit(pipeline_env, case_id))

    assert set(audit) == {"investigation", "case", "report", "findings", "evidence", "audit_events"}
    assert audit["investigation"]["investigation_id"] == case_id
    assert audit["investigation"]["status"] == "REVIEW"  # pending human review
    assert audit["case"]["transaction_id"] == "TXN-001"
    assert audit["case"]["alert_id"] == "ALERT-001"
    assert audit["report"]["transaction_id"] == "TXN-001"
    assert audit["findings"] and audit["evidence"] and audit["audit_events"]
    json.dumps(audit)  # fully serializable


def test_reconstruction_is_repeatable_and_stable(pipeline_env) -> None:
    case_id = _run_and_persist(pipeline_env, "TXN-001")
    one = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    two = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    assert one == two


def test_reconstruction_unknown_investigation_fails_closed(pipeline_env) -> None:
    with pytest.raises(ReconstructionError, match="unknown investigation"):
        asyncio.run(get_investigation_audit(pipeline_env, "INV-DOES-NOT-EXIST"))


def test_reconstruction_fails_on_tampered_report(
    pipeline_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stored report that no longer validates cannot reconstruct."""
    case_id = _run_and_persist(pipeline_env, "TXN-001")

    async def _tamper() -> None:
        async with AsyncSession(pipeline_env, expire_on_commit=False) as session:
            case = await session.scalar(
                select(InvestigationCase).where(InvestigationCase.external_id == case_id)
            )
            case.report = dict(case.report, transaction_id="TXN-999")
            await session.commit()

    asyncio.run(_tamper())
    with pytest.raises(ReconstructionError, match="does not match"):
        asyncio.run(get_investigation_audit(pipeline_env, case_id))


def test_reconstruction_fails_on_missing_report(pipeline_env) -> None:
    case_id = _run_and_persist(pipeline_env, "TXN-001")

    async def _strip() -> None:
        async with AsyncSession(pipeline_env, expire_on_commit=False) as session:
            case = await session.scalar(
                select(InvestigationCase).where(InvestigationCase.external_id == case_id)
            )
            case.report = None
            await session.commit()

    asyncio.run(_strip())
    with pytest.raises(ReconstructionError, match="no stored report"):
        asyncio.run(get_investigation_audit(pipeline_env, case_id))


def test_reconstruction_preserves_alert_vs_mock_distinction(pipeline_env) -> None:
    """0.87 seeded alert and 0.9 mock score remain separate in the audit."""
    case_id = _run_and_persist(pipeline_env, "TXN-001")
    audit = asyncio.run(get_investigation_audit(pipeline_env, case_id))

    risk_payloads = [e["data"] for e in audit["evidence"] if e["category"] == "RISK"]
    dumped = json.dumps(risk_payloads)
    assert "0.87" in dumped and "ALERT-001" in dumped  # seeded fact
    assert "0.9" in dumped and "MOCK" in dumped  # mock signal
    assert audit["report"]["provenance"]["risk_source"] == "MOCK"
    assert audit["report"]["provenance"]["risk_model_version"] == "mock-risk-v1"


def test_historical_investigation_stays_reconstructable(pipeline_env) -> None:
    """A completed investigation remains intact after later runs."""
    first_case = _run_and_persist(pipeline_env, "TXN-001")
    snapshot = asyncio.run(get_investigation_audit(pipeline_env, first_case))

    _run_and_persist(pipeline_env, "TXN-1006")  # later, unrelated investigation

    after = asyncio.run(get_investigation_audit(pipeline_env, first_case))
    assert after == snapshot  # history was not touched
