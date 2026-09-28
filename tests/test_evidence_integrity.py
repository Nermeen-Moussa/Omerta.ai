"""Phase 11 - evidence integrity: hashing, immutability, traceability."""

import asyncio
import json
from typing import Any

import pytest
from domain.evidence import content_hash
from domain.services.audit_service import ReconstructionError, get_investigation_audit
from infrastructure.database.models import Evidence
from infrastructure.database.persistence import IntegrityError, persist_investigation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _report() -> dict[str, Any]:
    from domain.report import (
        Finding,
        InvestigationReport,
        RecommendedAction,
        ReportRiskLevel,
    )

    return InvestigationReport(
        investigation_id="INV-TEST-INT",
        transaction_id="TXN-001",
        risk_level=ReportRiskLevel.HIGH,
        summary="integrity test summary",
        findings=[
            Finding(finding="f1", evidence_ids=["EV-001"], confidence=0.9),
            Finding(finding="f2", evidence_ids=["EV-002"], confidence=0.8),
        ],
        recommended_action=RecommendedAction.HUMAN_REVIEW,
        confidence=0.7,
    ).model_dump(mode="json")


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


def _persist_kwargs(investigation_id: str = "INV-TEST-INT") -> dict[str, Any]:
    return {
        "investigation_id": investigation_id,
        "transaction_id": "TXN-001",
        "alert_id": "ALERT-001",
        "report": _report(),
        "evidence": _evidence(),
    }


def _kwargs_with_investigation_report(investigation_id: str) -> dict[str, Any]:
    """Persist kwargs whose report carries the given investigation id."""
    report = _report()
    report["investigation_id"] = investigation_id
    return {**_persist_kwargs(investigation_id), "report": report}


# --------------------------------------------------------------------------- #
# Integrity hashing
# --------------------------------------------------------------------------- #


def test_content_hash_is_deterministic_and_sensitive() -> None:
    base = {
        "evidence_id": "EV-001",
        "investigation_id": "INV-1",
        "transaction_id": "TXN-001",
        "category": "TRANSACTION",
        "source": "transaction",
        "tier": "FACT",
        "producer": "p",
        "producer_version": "",
        "reference": "TXN-001",
        "description": "same content",
        "data": {"a": 1, "b": [1, 2]},
    }
    assert content_hash(base) == content_hash(dict(base))  # same -> same
    changed = dict(base, description="different content")
    assert content_hash(changed) != content_hash(base)  # different -> different


def test_content_hash_is_key_order_insensitive() -> None:
    """JSONB round-trips do not preserve key order; hashes must survive."""
    one = content_hash(
        {
            "evidence_id": "EV-1",
            "investigation_id": "INV-1",
            "transaction_id": "T",
            "category": "TRANSACTION",
            "source": "transaction",
            "tier": "FACT",
            "producer": "p",
            "producer_version": "",
            "reference": "r",
            "description": "d",
            "data": {"x": 1, "y": {"k1": 1, "k2": 2}},
        }
    )
    two = content_hash(
        {
            "data": {"y": {"k2": 2, "k1": 1}, "x": 1},
            "description": "d",
            "reference": "r",
            "producer_version": "",
            "producer": "p",
            "tier": "FACT",
            "source": "transaction",
            "category": "TRANSACTION",
            "transaction_id": "T",
            "investigation_id": "INV-1",
            "evidence_id": "EV-1",
        }
    )
    assert one == two


def test_hash_excludes_non_semantic_fields() -> None:
    """Timestamps/random ids are not part of HASHED_FIELDS."""
    from domain.evidence import HASHED_FIELDS

    assert "created_at" not in HASHED_FIELDS
    assert "id" not in HASHED_FIELDS


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #


def test_repersist_with_changed_content_is_rejected(investigation_env) -> None:
    """Append-only: altered evidence content cannot overwrite a stored row."""
    engine = investigation_env
    asyncio.run(persist_investigation(engine, **_kwargs_with_investigation_report("INV-IMMUT")))

    tampered = _evidence()
    tampered[0] = dict(tampered[0], description="tampered description")
    with pytest.raises(IntegrityError, match="append-only"):
        asyncio.run(
            persist_investigation(
                engine,
                investigation_id="INV-IMMUT",
                transaction_id="TXN-001",
                alert_id="ALERT-001",
                report=_report(),
                evidence=tampered,
            )
        )


def test_row_cannot_be_updated_via_orm_without_detection(
    investigation_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Application-level guard: any ORM update path verifies hashes first."""
    engine = investigation_env
    asyncio.run(persist_investigation(engine, **_kwargs_with_investigation_report("INV-GUARD")))

    async def _tamper() -> None:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            row = await session.scalar(select(Evidence).where(Evidence.evidence_id == "EV-001"))
            row.description = "quietly rewritten"
            await session.commit()

    asyncio.run(_tamper())

    # Reconstruction recomputes hashes from stored fields and fails closed.
    with pytest.raises(ReconstructionError, match="integrity"):
        asyncio.run(get_investigation_audit(engine, "INV-GUARD"))


def test_repeated_persistence_is_hash_identical(investigation_env) -> None:
    engine = investigation_env

    async def _hashes() -> list[str]:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            rows = (
                await session.execute(
                    select(Evidence.content_hash)
                    .where(Evidence.investigation_id == "INV-HASH")
                    .order_by(Evidence.evidence_id)
                )
            ).all()
            return [r[0] for r in rows]

    asyncio.run(persist_investigation(engine, **_kwargs_with_investigation_report("INV-HASH")))
    first = asyncio.run(_hashes())
    asyncio.run(persist_investigation(engine, **_kwargs_with_investigation_report("INV-HASH")))
    second = asyncio.run(_hashes())
    assert first == second and len(first) == 2


# --------------------------------------------------------------------------- #
# Finding -> evidence traceability (persistence-side)
# --------------------------------------------------------------------------- #


def test_persisted_evidence_rows_carry_ids_and_investigation(investigation_env) -> None:
    engine = investigation_env
    asyncio.run(persist_investigation(engine, **_kwargs_with_investigation_report("INV-TRACE")))

    async def _verify() -> None:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            rows = (
                await session.scalars(
                    select(Evidence)
                    .where(Evidence.investigation_id == "INV-TRACE")
                    .order_by(Evidence.evidence_id)
                )
            ).all()
            assert [r.evidence_id for r in rows] == ["EV-001", "EV-002"]
            assert all(r.investigation_id == "INV-TRACE" for r in rows)
            assert all(r.transaction_id == "TXN-001" for r in rows)
            assert all(len(r.content_hash) == 64 for r in rows)
            assert {r.tier for r in rows} == {"FACT", "STRUCTURAL_SIGNAL"}

    asyncio.run(_verify())


def test_reconstruction_fails_on_unresolvable_evidence_reference(
    investigation_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A finding referencing evidence absent from the same investigation
    (including another investigation's id) fails closed at reconstruction."""
    engine = investigation_env
    report = _report()
    report["investigation_id"] = "INV-X1"
    report["findings"][0]["evidence_ids"] = ["EV-404"]  # unknown / foreign id
    asyncio.run(
        persist_investigation(
            engine,
            investigation_id="INV-X1",
            transaction_id="TXN-001",
            alert_id="ALERT-001",
            report=report,
            evidence=_evidence(),
        )
    )
    with pytest.raises(ReconstructionError, match="EV-404"):
        asyncio.run(get_investigation_audit(engine, "INV-X1"))


def test_reconstruction_rejects_empty_finding_evidence(
    investigation_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unsupported findings (no evidence) are rejected at reconstruction."""
    engine = investigation_env
    report = _report()
    report["investigation_id"] = "INV-EMPTY"
    report["findings"] = [{"finding": "unsupported", "evidence_ids": [], "confidence": 0.5}]
    asyncio.run(
        persist_investigation(
            engine,
            investigation_id="INV-EMPTY",
            transaction_id="TXN-001",
            alert_id="ALERT-001",
            report=report,
            evidence=_evidence(),
        )
    )
    with pytest.raises(ReconstructionError, match="no evidence"):
        asyncio.run(get_investigation_audit(engine, "INV-EMPTY"))


def test_audit_payload_is_json_serializable(investigation_env) -> None:
    engine = investigation_env
    asyncio.run(persist_investigation(engine, **_kwargs_with_investigation_report("INV-JSON")))
    audit = asyncio.run(get_investigation_audit(engine, "INV-JSON"))
    dumped = json.dumps(audit)
    assert "INV-JSON" in dumped
