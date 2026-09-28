"""Investigation reconstruction & audit validation (Phase 11).

Rebuilds a completed investigation from persisted data only - case (with the
stored report snapshot), immutable evidence rows, and the durable audit
trail - and validates the reconstruction **fail-closed**:

- the stored report must belong to the case's transaction;
- every finding's evidence_ids must resolve to evidence rows of the SAME
  investigation (no orphans, no cross-investigation references, no
  duplicates);
- evidence content hashes must still match (tamper detection).

Returns :class:`AuditReconstruction`; raises :class:`ReconstructionError` on
any inconsistency. This is a domain/service-level API - the Case API is a
later phase.
"""

import logging
from typing import Any

from infrastructure.database.models import Alert, AuditEvent, Evidence, InvestigationCase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from domain.evidence import content_hash
from domain.report import InvestigationReport

logger = logging.getLogger(__name__)


class ReconstructionError(RuntimeError):
    """The persisted investigation is inconsistent - fail closed."""


async def get_investigation_audit(
    engine: AsyncEngine | AsyncSession, investigation_id: str
) -> dict[str, Any]:
    """Reconstruct one investigation from persisted data (fail-closed).

    Accepts an engine or an existing session (for use inside a transaction).
    """
    if isinstance(engine, AsyncSession):
        return await _reconstruct(engine, investigation_id)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        return await _reconstruct(session, investigation_id)


async def _reconstruct(session: AsyncSession, investigation_id: str) -> dict[str, Any]:
    from sqlalchemy.orm import selectinload

    case = await session.scalar(
        select(InvestigationCase)
        .where(InvestigationCase.external_id == investigation_id)
        .options(selectinload(InvestigationCase.alert).selectinload(Alert.transaction))
    )
    if case is None:
        raise ReconstructionError(f"unknown investigation: {investigation_id}")

    evidence_rows = (
        (
            await session.execute(
                select(Evidence)
                .where(Evidence.case_id == case.id)
                .order_by(Evidence.created_at, Evidence.evidence_id)
            )
        )
        .scalars()
        .all()
    )
    event_rows = (
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.case_id == case.id).order_by(AuditEvent.id)
            )
        )
        .scalars()
        .all()
    )

    evidence_payload = [
        {
            "evidence_id": row.evidence_id,
            "investigation_id": row.investigation_id,
            "transaction_id": row.transaction_id,
            "category": row.evidence_type,
            "source": row.source,
            "tier": row.tier,
            "producer": row.producer,
            "producer_version": row.producer_version,
            "reference": row.source_reference.split("#")[0] if row.source_reference else "",
            "description": row.description,
            "data": (row.data or {}).get("payload", {}),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "content_hash": row.content_hash,
        }
        for row in evidence_rows
    ]

    issues = _validate_reconstruction(case, evidence_payload)

    if issues:
        raise ReconstructionError(
            f"investigation {investigation_id} failed reconstruction: {'; '.join(issues)}"
        )

    return {
        "investigation": {
            "investigation_id": case.external_id,
            "status": case.status,
            "severity": case.severity,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        },
        "case": {
            "case_id": case.external_id,
            "alert_id": case.alert.external_id if case.alert else None,
            "transaction_id": case.alert.transaction.external_id if case.alert else None,
        },
        "report": case.report,
        "findings": (case.report or {}).get("findings", []),
        "evidence": evidence_payload,
        "audit_events": [
            {
                "event_id": row.event_id,
                "event_type": row.event_type,
                "actor_type": row.actor_type,
                "source": row.source,
                "metadata": row.metadata_ or {},
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in event_rows
        ],
    }


def _validate_reconstruction(
    case: InvestigationCase, evidence_payload: list[dict[str, Any]]
) -> list[str]:
    """Fail-closed consistency checks over the persisted investigation."""
    issues: list[str] = []

    report = case.report
    if not report:
        issues.append("case has no stored report snapshot")
        return issues

    # Report schema must still validate.
    try:
        InvestigationReport.model_validate(report)
    except Exception as exc:  # noqa: BLE001 - any failure is an issue
        issues.append(f"stored report no longer validates: {type(exc).__name__}")

    # Transaction consistency (report vs case's alert transaction).
    txn_id = case.alert.transaction.external_id if case.alert else None
    if report.get("transaction_id") != txn_id:
        issues.append(
            f"report transaction {report.get('transaction_id')!r} does not match "
            f"case transaction {txn_id!r}"
        )

    # Evidence uniqueness + integrity hashes.
    evidence_ids = [item["evidence_id"] for item in evidence_payload]
    if len(evidence_ids) != len(set(evidence_ids)):
        issues.append("duplicate evidence ids in persisted evidence")
    for item in evidence_payload:
        recomputed = content_hash(
            {
                "evidence_id": item["evidence_id"],
                "investigation_id": item["investigation_id"],
                "transaction_id": item["transaction_id"] or "",
                "category": item["category"],
                "source": item["source"].lower(),
                "tier": item["tier"],
                "producer": item["producer"],
                "producer_version": item["producer_version"],
                "reference": item["reference"],
                "description": item["description"],
                "data": item["data"],
            }
        )
        if recomputed != item["content_hash"]:
            issues.append(f"evidence {item['evidence_id']} failed integrity check")

    # Finding -> evidence traceability (same investigation only).
    valid_ids = set(evidence_ids)
    for index, finding in enumerate(report.get("findings", [])):
        refs = finding.get("evidence_ids", [])
        if not refs:
            issues.append(f"finding#{index} references no evidence")
            continue
        if len(refs) != len(set(refs)):
            issues.append(f"finding#{index} duplicates evidence references")
        unknown = sorted(set(refs) - valid_ids)
        if unknown:
            issues.append(f"finding#{index} references unknown/cross evidence: {unknown}")

    return issues
