"""Phase 11 - evidence/audit persistence: atomicity, constraints, migrations."""

import asyncio
import subprocess
import sys
from typing import Any

import pytest
from apps.investigator.graph import run_investigation_async
from infrastructure.config import get_settings
from infrastructure.database import persistence as persistence_module
from infrastructure.database.models import AuditEvent, Evidence, InvestigationCase
from infrastructure.database.persistence import persist_investigation
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


def _persist_kwargs(state: dict[str, Any]) -> dict[str, Any]:
    return dict(
        investigation_id=state["investigation_id"],
        transaction_id=state["transaction_id"],
        alert_id=state.get("alert_id"),
        report=state["report"],
        evidence=state["evidence"],
        audit_events=state.get("audit_events", []),
    )


# --------------------------------------------------------------------------- #
# Atomicity
# --------------------------------------------------------------------------- #


async def test_audit_failure_rolls_back_case_and_evidence(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, seeded_db: None
) -> None:
    """Failure during audit-event insert leaves NO case or evidence rows."""
    state = await run_investigation_async("TXN-001")

    async def _boom(session: AsyncSession, case: Any, events: list, txn: str) -> int:
        raise RuntimeError("simulated audit insert failure")

    monkeypatch.setattr(persistence_module, "_persist_audit_events", _boom)
    with pytest.raises(RuntimeError, match="simulated audit insert failure"):
        await persist_investigation(test_engine, **_persist_kwargs(state))

    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        case = await session.scalar(
            select(InvestigationCase).where(
                InvestigationCase.external_id == state["investigation_id"]
            )
        )
        assert case is None  # rolled back


async def test_evidence_failure_rolls_back_case_and_audit(
    test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, seeded_db: None
) -> None:
    state = await run_investigation_async("TXN-001")

    async def _boom(session: AsyncSession, case: Any, evidence: list, txn: str) -> int:
        raise RuntimeError("simulated evidence failure after audit")

    # Evidence insert fails after audit inserts would have run.
    monkeypatch.setattr(
        persistence_module,
        "_persist_evidence_rows",
        _boom,
    )
    with pytest.raises(RuntimeError, match="simulated evidence failure"):
        await persist_investigation(test_engine, **_persist_kwargs(state))

    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        case = await session.scalar(
            select(InvestigationCase).where(
                InvestigationCase.external_id == state["investigation_id"]
            )
        )
        assert case is None


def test_full_pipeline_persists_all_three_artifact_kinds(pipeline_env) -> None:
    async def _flow() -> dict[str, Any]:
        state = await run_investigation_async("TXN-001")
        return state, await persist_investigation(pipeline_env, **_persist_kwargs(state))

    state, result = asyncio.run(_flow())
    assert result["evidence_rows"] == len(state["evidence"])
    assert result["audit_events"] == len(state["audit_events"])
    assert result["audit_events"] >= 10


# --------------------------------------------------------------------------- #
# Database constraints
# --------------------------------------------------------------------------- #


def test_evidence_unique_constraint_prevents_duplicate_ids(pipeline_env) -> None:
    """(case_id, evidence_id) uniqueness is enforced by the database."""
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    async def _flow() -> None:
        state = await run_investigation_async("TXN-001")
        await persist_investigation(pipeline_env, **_persist_kwargs(state))
        case = await _case_id(pipeline_env, state["investigation_id"])
        async with AsyncSession(pipeline_env, expire_on_commit=False) as session:
            session.add(
                Evidence(
                    case_id=case,
                    evidence_id="EV-001",  # duplicate within the same case
                    evidence_type="TRANSACTION",
                    source="TRANSACTION",
                    source_reference="dup#EV-001",
                    description="dup",
                    data={},
                    investigation_id=state["investigation_id"],
                    tier="FACT",
                    producer="x",
                    producer_version="",
                    content_hash="0" * 64,
                )
            )
            await session.commit()

    with pytest.raises(SAIntegrityError):
        asyncio.run(_flow())


async def _case_id(engine: AsyncEngine, investigation_id: str) -> int:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        case = await session.scalar(
            select(InvestigationCase.id).where(InvestigationCase.external_id == investigation_id)
        )
        return case


def test_audit_event_idempotency_constraint(pipeline_env) -> None:
    """(case_id, event_id) uniqueness backs the append-only audit trail."""
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    async def _flow() -> None:
        state = await run_investigation_async("TXN-001")
        await persist_investigation(pipeline_env, **_persist_kwargs(state))
        case = await _case_id(pipeline_env, state["investigation_id"])
        async with AsyncSession(pipeline_env, expire_on_commit=False) as session:
            existing = (
                await session.scalars(select(AuditEvent).where(AuditEvent.case_id == case).limit(1))
            ).first()
            session.add(
                AuditEvent(
                    case_id=case,
                    investigation_id=state["investigation_id"],
                    transaction_id=state["transaction_id"],
                    event_type=existing.event_type,
                    actor_type=existing.actor_type,
                    source=existing.source,
                    metadata_=existing.metadata_,
                    event_id=existing.event_id,  # duplicate key
                )
            )
            await session.commit()

    with pytest.raises(SAIntegrityError):
        asyncio.run(_flow())


def test_indexes_exist_on_phase11_columns() -> None:
    """Evidence/audit indexes and unique constraints are present."""

    async def _check() -> tuple[set[str], set[str]]:
        from infrastructure.database.session import create_engine

        engine = create_engine(use_null_pool=True)
        try:
            async with engine.connect() as conn:
                evidence_idx = (
                    (
                        await conn.execute(
                            text("SELECT indexname FROM pg_indexes WHERE tablename = 'evidence'")
                        )
                    )
                    .scalars()
                    .all()
                )
                audit_idx = (
                    (
                        await conn.execute(
                            text(
                                "SELECT indexname FROM pg_indexes WHERE tablename = 'audit_events'"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                constraints = (
                    (
                        await conn.execute(
                            text(
                                "SELECT conname FROM pg_constraint "
                                "WHERE conrelid = 'evidence'::regclass AND contype = 'u'"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                return set(evidence_idx) | set(audit_idx), set(constraints)
        finally:
            await engine.dispose()

    indexes, unique_constraints = asyncio.run(_check())
    assert "ix_evidence_investigation_id" in indexes
    assert "ix_evidence_content_hash" in indexes
    assert "ix_audit_events_case_seq" in indexes
    assert "uq_evidence_case_evidence_id" in unique_constraints
    assert "uq_evidence_case_source_ref" in unique_constraints


# --------------------------------------------------------------------------- #
# Migration safety (upgrade / downgrade / upgrade) on an isolated database
# --------------------------------------------------------------------------- #


def test_migration_upgrade_downgrade_upgrade_cycle() -> None:
    """The Phase 11 migration is reversible from a fresh database."""
    settings = get_settings()
    base = settings.test_database_url.rsplit("?", 1)[0]
    scratch = f"{base.rsplit('/', 1)[0]}/omerta_migration_cycle"

    import asyncpg

    async def _create() -> None:
        conn = await asyncpg.connect(
            host="127.0.0.1",
            port=15432,
            user="omerta",
            password="omerta_dev_password",
            database="postgres",
        )
        try:
            await conn.execute("DROP DATABASE IF EXISTS omerta_migration_cycle")
            await conn.execute("CREATE DATABASE omerta_migration_cycle OWNER omerta")
        finally:
            await conn.close()

    asyncio.run(_create())
    try:
        for args in (
            ["upgrade", "head"],
            ["downgrade", "da9200ff25a4"],
            ["upgrade", "head"],
        ):
            subprocess.run(
                [sys.executable, "-m", "alembic", "-x", f"db_url={scratch}", *args],
                check=True,
                capture_output=True,
            )
    finally:

        async def _drop() -> None:
            conn = await asyncpg.connect(
                host="127.0.0.1",
                port=15432,
                user="omerta",
                password="omerta_dev_password",
                database="postgres",
            )
            try:
                await conn.execute("DROP DATABASE IF EXISTS omerta_migration_cycle")
            finally:
                await conn.close()

        asyncio.run(_drop())
