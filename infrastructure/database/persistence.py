"""Investigation run persistence: durable evidence & audit trail (Phase 11).

Stores, inside ONE transaction:
- the agent's validated report on the case (reconstruction snapshot),
- every evidence item as an immutable Evidence row (SHA-256 content hash,
  verified on repeat persistence - silent content changes are rejected),
- every collected AuditEventItem as an append-only audit_events row.

Provenance rule: evidence rows store facts and signals as collected, each
with an explicit tier (FACT / STRUCTURAL_SIGNAL / MODEL_OUTPUT /
AGENT_FINDING). Findings/typologies live in the case report with explicit
agent provenance - never mixed into fact rows.

Idempotency: case upserted on external_id (== investigation_id); evidence on
(case, evidence_id); audit events on (case, event_id). Re-persisting the same
investigation updates nothing semantically; a genuinely new investigation
gets new rows throughout.
"""

import logging
from typing import Any

from domain.evidence import ActorType, EvidenceTier, content_hash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.database.models import (
    Alert,
    AuditEvent,
    Evidence,
    InvestigationCase,
    Transaction,
)

logger = logging.getLogger(__name__)

PENDING_REVIEW_STATUS = "REVIEW"

TIER_BY_CATEGORY: dict[str, str] = {
    "TRANSACTION": EvidenceTier.FACT.value,
    "ACCOUNT": EvidenceTier.FACT.value,
    "HISTORY": EvidenceTier.FACT.value,
    "DEVICE": EvidenceTier.FACT.value,
    "IP": EvidenceTier.FACT.value,
    "GRAPH": EvidenceTier.STRUCTURAL_SIGNAL.value,
    "RISK": EvidenceTier.MODEL_OUTPUT.value,
    "KNOWLEDGE": EvidenceTier.KNOWLEDGE.value,
}

PRODUCER_BY_SOURCE: dict[str, str] = {
    "transaction": "TransactionCapability",
    "graph": "GraphCapability",
    "risk": "RiskCapability",
    "knowledge": "KnowledgeCapability",
}


def _hash_evidence(item: dict[str, Any], investigation_id: str, transaction_id: str) -> str:
    """Deterministic integrity hash for one evidence item (Phase 11).

    Uses the semantic (lowercase) source name so storage casing never
    affects content identity - matching the reconstruction service.
    """
    return content_hash(
        {
            "evidence_id": item["evidence_id"],
            "investigation_id": investigation_id,
            "transaction_id": transaction_id,
            "category": item["category"],
            "source": item["source"].lower(),
            "tier": TIER_BY_CATEGORY.get(item["category"], EvidenceTier.FACT.value),
            "producer": PRODUCER_BY_SOURCE.get(item["source"], item["source"]),
            "producer_version": "",
            "reference": item["reference"],
            "description": item["description"],
            "data": item.get("data", {}),
        }
    )


def _stored_row_hash(existing: Evidence) -> str:
    """Recompute the content hash from a persisted row's stored fields.

    Comparing content-to-content (rather than new-content vs creation-time
    hash) keeps idempotent re-persistence robust across canonicalization
    evolution; the stored ``content_hash`` remains the creation-time record
    used by reconstruction-time tamper detection.
    """
    return content_hash(
        {
            "evidence_id": existing.evidence_id,
            "investigation_id": existing.investigation_id,
            "transaction_id": existing.transaction_id or "",
            "category": existing.evidence_type,
            "source": existing.source.lower(),
            "tier": existing.tier,
            "producer": existing.producer,
            "producer_version": existing.producer_version,
            "reference": existing.source_reference.split("#")[0]
            if existing.source_reference
            else "",
            "description": existing.description,
            "data": (existing.data or {}).get("payload", {}),
        }
    )


async def _upsert_case(
    session: AsyncSession,
    *,
    investigation_id: str,
    transaction_id: str,
    alert_id: str | None,
    report: dict[str, Any],
) -> InvestigationCase:
    """Create or update the case row for this investigation."""
    txn_pk = await session.scalar(
        select(Transaction.id).where(Transaction.external_id == transaction_id)
    )
    if txn_pk is None:
        raise ValueError(f"cannot persist case for unknown transaction {transaction_id}")

    alert_pk = None
    if alert_id:
        alert_pk = await session.scalar(select(Alert.id).where(Alert.external_id == alert_id))
    if alert_pk is None:
        alert_pk = await session.scalar(select(Alert.id).where(Alert.transaction_id == txn_pk))
    if alert_pk is None:
        raise ValueError(
            "cannot persist a case without an alert linkage; the schema requires "
            "alert_id on investigation_cases"
        )

    existing = await session.scalar(
        select(InvestigationCase).where(InvestigationCase.external_id == investigation_id)
    )
    values = {
        "alert_id": alert_pk,
        "status": PENDING_REVIEW_STATUS,
        "severity": report.get("risk_level", "MEDIUM"),
        "assigned_to": None,
        "report": report or None,
    }
    if existing is None:
        case = InvestigationCase(external_id=investigation_id, **values)
        session.add(case)
        await session.flush()
        return case
    for key, value in values.items():
        setattr(existing, key, value)
    await session.flush()
    return existing


async def _persist_evidence_rows(
    session: AsyncSession,
    case: InvestigationCase,
    evidence: list[dict[str, Any]],
    transaction_id: str,
) -> int:
    """Insert-or-verify one immutable Evidence row per item; returns row count.

    Append-only: an existing row with identical content passes (idempotent
    re-persistence); an existing row whose content hash differs raises
    IntegrityError - evidence is never silently edited.
    """
    for item in evidence:
        tier = TIER_BY_CATEGORY.get(item["category"], EvidenceTier.FACT.value)
        producer = PRODUCER_BY_SOURCE.get(item["source"], item["source"])
        values = {
            "evidence_type": item["category"],
            "source": item["source"].upper(),
            "source_reference": f"{item['reference']}#{item['evidence_id']}",
            "description": item["description"],
            "data": {"payload": item.get("data", {})},
            "evidence_id": item["evidence_id"],
            "investigation_id": case.external_id,
            "transaction_id": transaction_id,
            "tier": tier,
            "producer": producer,
            "producer_version": "",
            "content_hash": _hash_evidence(item, case.external_id, transaction_id or ""),
        }
        existing = await session.scalar(
            select(Evidence).where(
                Evidence.case_id == case.id,
                Evidence.evidence_id == item["evidence_id"],
            )
        )
        if existing is None:
            session.add(Evidence(case_id=case.id, **values))
        elif _stored_row_hash(existing) != values["content_hash"]:
            raise IntegrityError(
                f"evidence {item['evidence_id']} of investigation "
                f"{case.external_id} changed since creation; evidence is "
                "append-only - create a new investigation instead"
            )
    await session.flush()
    return len(evidence)


class IntegrityError(RuntimeError):
    """Raised when persisted evidence content differs from the stored hash."""


def _event_id(event_type: str, source: str, metadata: dict[str, Any]) -> str:
    """Stable idempotency key for one audit event within an investigation.

    Distinguishes repeated event types (e.g. two REPORT_VALIDATED outcomes)
    by their distinguishing metadata.
    """
    parts = [event_type, source]
    parts += [f"{key}={metadata[key]}" for key in sorted(metadata)]
    return "|".join(parts)[:80]


async def _persist_audit_events(
    session: AsyncSession,
    case: InvestigationCase,
    events: list[dict[str, Any]],
    transaction_id: str,
) -> int:
    """Insert-or-verify append-only audit events; returns event count.

    Re-persisting the same investigation re-inserts the same (case, event_id)
    keys - existing identical rows are skipped, so no duplicates and no
    silent rewrites.
    """
    for event in events:
        metadata = event.get("metadata") or {}
        values = {
            "investigation_id": case.external_id,
            "transaction_id": transaction_id,
            "event_type": event["event_type"],
            "actor_type": event.get("actor_type", ActorType.SYSTEM.value),
            "source": event.get("source", ""),
            "metadata_": metadata,
            "event_id": _event_id(event["event_type"], event.get("source", ""), metadata),
        }
        existing = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.case_id == case.id,
                AuditEvent.event_id == values["event_id"],
            )
        )
        if existing is None:
            session.add(AuditEvent(case_id=case.id, **values))
    await session.flush()
    return len(events)


async def persist_investigation(
    engine: AsyncEngine,
    *,
    investigation_id: str,
    transaction_id: str,
    alert_id: str | None,
    report: dict[str, Any],
    evidence: list[dict[str, Any]],
    audit_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Persist case + evidence + audit trail atomically."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            case = await _upsert_case(
                session,
                investigation_id=investigation_id,
                transaction_id=transaction_id,
                alert_id=alert_id,
                report=report,
            )
            count = await _persist_evidence_rows(session, case, evidence, transaction_id)
            event_count = await _persist_audit_events(
                session, case, audit_events or [], transaction_id
            )
            await session.commit()
            logger.info(
                "investigation_persisted: case=%s evidence_rows=%s audit_events=%s",
                case.external_id,
                count,
                event_count,
            )
            return {
                "case_id": case.external_id,
                "case_status": case.status,
                "evidence_rows": count,
                "audit_events": event_count,
            }
        except Exception:
            await session.rollback()
            raise
