"""phase 11 evidence/audit hardening

Revision ID: b41c7e5d9f02
Revises: da9200ff25a4
Create Date: 2026-09-27 12:00:00.000000

Adds evidence provenance + integrity columns, case report storage, and the
append-only audit_events table. Non-destructive: existing columns keep their
names and semantics (evidence_type stays the category; source stays the
producing capability, now stored uppercased by the application layer).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b41c7e5d9f02"
down_revision: str | None = "da9200ff25a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- investigation_cases: durable report snapshot ---
    op.add_column(
        "investigation_cases",
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # --- evidence: provenance + integrity (backfilled for existing rows) ---
    op.add_column("evidence", sa.Column("evidence_id", sa.String(length=64), nullable=True))
    op.add_column(
        "evidence", sa.Column("investigation_id", sa.String(length=64), nullable=True)
    )
    op.add_column("evidence", sa.Column("transaction_id", sa.String(length=64), nullable=True))
    op.add_column(
        "evidence", sa.Column("tier", sa.String(length=32), nullable=False, server_default="FACT")
    )
    op.add_column(
        "evidence", sa.Column("producer", sa.String(length=64), nullable=False, server_default="")
    )
    op.add_column(
        "evidence",
        sa.Column("producer_version", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column("evidence", sa.Column("content_hash", sa.String(length=64), nullable=True))

    # Backfill evidence_id from source_reference ("REF#EV-001" convention);
    # legacy rows without the convention get a stable per-row id.
    op.execute(
        "UPDATE evidence SET evidence_id = CASE "
        "WHEN position('#' in source_reference) > 0 "
        "THEN split_part(source_reference, '#', 2) "
        "ELSE 'LEGACY-' || id END WHERE evidence_id IS NULL"
    )
    # Derive investigation_id from the owning case.
    op.execute(
        "UPDATE evidence SET investigation_id = investigation_cases.external_id "
        "FROM investigation_cases WHERE evidence.case_id = investigation_cases.id "
        "AND evidence.investigation_id IS NULL"
    )
    # Initial integrity hash computed in Python (no pgcrypto dependency), over
    # the legacy columns, using the application's canonicalization.
    import hashlib
    import json

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, evidence_id, investigation_id, transaction_id, evidence_type, "
            "source, tier, producer, producer_version, source_reference, description, data "
            "FROM evidence WHERE content_hash IS NULL"
        )
    ).fetchall()
    for row in rows:
        payload = {
            "evidence_id": row.evidence_id,
            "investigation_id": row.investigation_id,
            "transaction_id": row.transaction_id,
            "category": row.evidence_type,
            "source": row.source,
            "tier": row.tier,
            "producer": row.producer,
            "producer_version": row.producer_version,
            "reference": row.source_reference,
            "description": row.description,
            "data": row.data if isinstance(row.data, dict) else {"payload": row.data},
        }
        canonical = json.dumps(
            {field: payload.get(field) for field in (
                "evidence_id", "investigation_id", "transaction_id", "category",
                "source", "tier", "producer", "producer_version",
                "reference", "description", "data",
            )},
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        digest_hex = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        conn.execute(
            sa.text("UPDATE evidence SET content_hash = :h WHERE id = :i"),
            {"h": digest_hex, "i": row.id},
        )

    op.alter_column("evidence", "evidence_id", nullable=False)
    op.alter_column("evidence", "investigation_id", nullable=False)
    op.alter_column("evidence", "content_hash", nullable=False)

    op.create_index(op.f("ix_evidence_evidence_id"), "evidence", ["evidence_id"], unique=False)
    op.create_index(
        op.f("ix_evidence_investigation_id"), "evidence", ["investigation_id"], unique=False
    )
    op.create_index(
        op.f("ix_evidence_transaction_id"), "evidence", ["transaction_id"], unique=False
    )
    op.create_index(op.f("ix_evidence_content_hash"), "evidence", ["content_hash"], unique=False)
    op.create_unique_constraint("uq_evidence_case_evidence_id", "evidence", ["case_id", "evidence_id"])

    # --- audit_events: durable business events ---
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("investigation_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("investigation_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False, server_default="SYSTEM"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("event_id", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "event_id", name="uq_audit_case_event_id"),
    )
    op.create_index(op.f("ix_audit_events_case_id"), "audit_events", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_audit_events_investigation_id"), "audit_events", ["investigation_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_events_transaction_id"), "audit_events", ["transaction_id"], unique=False
    )
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_audit_events_event_id"), "audit_events", ["event_id"], unique=False)
    op.create_index("ix_audit_events_case_seq", "audit_events", ["case_id", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_events_case_seq", table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_event_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_event_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_transaction_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_investigation_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_case_id"), table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_constraint("uq_evidence_case_evidence_id", "evidence", type_="unique")
    op.drop_index(op.f("ix_evidence_content_hash"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_transaction_id"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_investigation_id"), table_name="evidence")
    op.drop_index(op.f("ix_evidence_evidence_id"), table_name="evidence")
    op.drop_column("evidence", "content_hash")
    op.drop_column("evidence", "producer_version")
    op.drop_column("evidence", "producer")
    op.drop_column("evidence", "tier")
    op.drop_column("evidence", "transaction_id")
    op.drop_column("evidence", "investigation_id")
    op.drop_column("evidence", "evidence_id")

    op.drop_column("investigation_cases", "report")
