"""Phase 11 - durable audit events: persistence, atomicity, semantics."""

import asyncio
import json
import logging
from typing import Any

import pytest
from apps.investigator.graph import run_investigation_async
from domain.evidence import AuditEventType
from domain.services.audit_service import get_investigation_audit
from infrastructure.database.models import AuditEvent, InvestigationCase
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


def test_completed_investigation_persists_expected_event_types(pipeline_env) -> None:
    case_id = _run_and_persist(pipeline_env, "TXN-001")
    audit = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    types = {e["event_type"] for e in audit["audit_events"]}
    expected = {
        AuditEventType.INVESTIGATION_STARTED.value,
        AuditEventType.TRANSACTION_LOADED.value,
        AuditEventType.ACCOUNT_CONTEXT_LOADED.value,
        AuditEventType.GRAPH_CONTEXT_LOADED.value,
        AuditEventType.RISK_CONTEXT_LOADED.value,
        AuditEventType.AGENT_STARTED.value,
        AuditEventType.AGENT_COMPLETED.value,
        AuditEventType.REPORT_CREATED.value,
        AuditEventType.EVIDENCE_VALIDATED.value,
        AuditEventType.REPORT_VALIDATED.value,
        AuditEventType.INVESTIGATION_COMPLETED.value,
    }
    assert expected <= types
    assert AuditEventType.INVESTIGATION_FAILED.value not in types


def test_failed_investigation_records_failure_event(pipeline_env) -> None:
    async def _flow() -> tuple[str, dict[str, Any]]:
        state = await run_investigation_async("TXN-999")
        return state["status"], state

    status, state = asyncio.run(_flow())
    assert status == "FAILED"
    event_types = {e["event_type"] for e in state.get("audit_events", [])}
    assert AuditEventType.INVESTIGATION_FAILED.value in event_types
    assert AuditEventType.INVESTIGATION_COMPLETED.value not in event_types
    # A failed run has no case (nothing persisted) - the audit trail for the
    # failed attempt lives in the state, not the database.


def test_agent_events_carry_agent_actor(pipeline_env) -> None:
    case_id = _run_and_persist(pipeline_env, "TXN-001")
    audit = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    agent_events = [e for e in audit["audit_events"] if e["actor_type"] == "AGENT"]
    assert agent_events, "agent events must be attributed to the AGENT actor"
    assert {e["event_type"] for e in agent_events} <= {
        AuditEventType.AGENT_STARTED.value,
        AuditEventType.AGENT_COMPLETED.value,
        AuditEventType.REPORT_CREATED.value,
    }
    # No invented human actions.
    assert all(e["actor_type"] != "HUMAN" for e in audit["audit_events"])


def test_audit_events_are_distinct_from_operational_logs(
    pipeline_env, caplog: pytest.LogCaptureFixture
) -> None:
    """Durable events are business records; log messages stay operational."""
    with caplog.at_level(logging.INFO, logger="apps.investigator.nodes"):
        case_id = _run_and_persist(pipeline_env, "TXN-001")
    audit = asyncio.run(get_investigation_audit(pipeline_env, case_id))

    log_messages = {r.message for r in caplog.records}
    durable_types = {e["event_type"] for e in audit["audit_events"]}
    # The two systems carry the same *history* but are separate mechanisms:
    # durable events are typed enum rows, logs are free-form message strings.
    assert durable_types and log_messages
    assert durable_types.isdisjoint(log_messages)
    assert AuditEventType.INVESTIGATION_STARTED.value in durable_types
    assert "investigation_started" in log_messages


def test_repersistence_does_not_duplicate_audit_events(pipeline_env) -> None:
    async def _flow() -> dict[str, Any]:
        return await run_investigation_async("TXN-001")

    state = asyncio.run(_flow())
    kwargs = _persist_kwargs(state)
    first = asyncio.run(persist_investigation(pipeline_env, **kwargs))
    second = asyncio.run(persist_investigation(pipeline_env, **kwargs))
    assert first["audit_events"] == second["audit_events"]

    async def _count() -> int:
        async with AsyncSession(pipeline_env, expire_on_commit=False) as session:
            case = await session.scalar(
                select(InvestigationCase).where(
                    InvestigationCase.external_id == state["investigation_id"]
                )
            )
            return len(
                (
                    await session.scalars(select(AuditEvent).where(AuditEvent.case_id == case.id))
                ).all()
            )

    assert asyncio.run(_count()) == first["audit_events"]


def test_audit_event_metadata_is_small_and_safe(pipeline_env) -> None:
    case_id = _run_and_persist(pipeline_env, "TXN-001")
    audit = asyncio.run(get_investigation_audit(pipeline_env, case_id))
    dumped = json.dumps(audit["audit_events"]).lower()
    for forbidden in ("password", "api_key", "authorization", "bolt://", "postgresql"):
        assert forbidden not in dumped
    for event in audit["audit_events"]:
        assert len(json.dumps(event)) < 2000  # no payload dumps
