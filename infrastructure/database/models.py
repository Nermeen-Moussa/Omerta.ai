"""SQLAlchemy 2.x ORM models for Omerta.ai transactional data.

The database stores FACTS (transactions, devices, IPs, alerts, cases,
evidence). LLM-generated conclusions are never stored here as facts; AI
findings live in investigation artifacts with explicit provenance instead.

Schema notes:
- Every business entity carries a stable ``external_id`` (e.g. "TXN-001") used
  across the API, MCP tools, and seed data; integer PKs are internal.
- Status/type/risk columns are plain strings (validated at the Pydantic layer
  in later phases) to keep the schema simple and migration-friendly.
- Risk scores are explicitly marked as seeded/mock values in data; the future
  ML risk engine will replace them, and these columns already support feature
  extraction (amount, timestamps, new-device/new-ip flags, risk levels).
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from infrastructure.database.session import Base


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp for Python-side defaults."""
    return datetime.now(UTC)


class TimestampMixin:
    """Common audit timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=_utcnow,
    )


class Account(Base):
    """Customer account."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(255))
    account_type: Mapped[str] = mapped_column(String(32), index=True)
    country: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", foreign_keys="Transaction.account_id"
    )
    recipient_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="recipient_account",
        foreign_keys="Transaction.recipient_account_id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Account(external_id={self.external_id!r}, risk_level={self.risk_level!r})"


class Device(Base):
    """Device used for transactions."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_type: Mapped[str] = mapped_column(String(32))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)


class IPAddress(Base):
    """IP address seen during transactions."""

    __tablename__ = "ip_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    address: Mapped[str] = mapped_column(String(45), unique=True, index=True)  # IPv4/IPv6
    country: Mapped[str] = mapped_column(String(2))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)


class Transaction(TimestampMixin, Base):
    """Financial transaction between two accounts."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    recipient_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3))
    transaction_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    ip_address_id: Mapped[int | None] = mapped_column(
        ForeignKey("ip_addresses.id", ondelete="SET NULL"), index=True
    )
    is_new_device: Mapped[bool] = mapped_column(Boolean, default=False)
    is_new_ip: Mapped[bool] = mapped_column(Boolean, default=False)
    # Free-form factual attributes (channel, reference codes). Never used for
    # AI conclusions; structured findings go to investigation artifacts.
    # Named txn_metadata to avoid the reserved Base.metadata attribute.
    txn_metadata: Mapped[dict | None] = mapped_column(JSONB, default=None)

    account: Mapped[Account] = relationship(
        back_populates="transactions", foreign_keys=[account_id]
    )
    recipient_account: Mapped[Account] = relationship(
        back_populates="recipient_transactions", foreign_keys=[recipient_account_id]
    )
    device: Mapped[Device | None] = relationship()
    ip_address: Mapped[IPAddress | None] = relationship()
    alerts: Mapped[list["Alert"]] = relationship(back_populates="transaction")

    __table_args__ = (
        # Velocity/feature queries: all transactions for an account over time.
        Index("ix_transactions_account_timestamp", "account_id", "timestamp"),
        Index("ix_transactions_recipient_timestamp", "recipient_account_id", "timestamp"),
    )


class Alert(Base):
    """Risk alert raised on a transaction (risk_score is seeded/mock for now)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    transaction: Mapped[Transaction] = relationship(back_populates="alerts")
    cases: Mapped[list["InvestigationCase"]] = relationship(back_populates="alert")

    __table_args__ = (Index("ix_alerts_status_level", "status", "risk_level"),)


class InvestigationCase(TimestampMixin, Base):
    """Compliance investigation case opened from an alert."""

    __tablename__ = "investigation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(255), default=None)
    # Phase 11: the agent's validated report snapshot lives on the case so an
    # investigation can be reconstructed without external state.
    report: Mapped[dict | None] = mapped_column(JSONB, default=None)

    alert: Mapped[Alert] = relationship(back_populates="cases")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="case")


class Evidence(TimestampMixin, Base):
    """Durable, append-only evidence artifact (Phase 11).

    ``content_hash`` (SHA-256 over canonical content) detects modification;
    persistence verifies it and refuses silent content changes.
    """

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("investigation_cases.id", ondelete="CASCADE"), index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(64), index=True)  # category
    source: Mapped[str] = mapped_column(String(64))  # e.g. TRANSACTION, GRAPH, RISK
    source_reference: Mapped[str] = mapped_column(String(255))  # reference#evidence_id
    description: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB, default=None)  # structured JSON payload

    # --- Phase 11 provenance / integrity ---
    evidence_id: Mapped[str] = mapped_column(String(64), index=True)  # EV-001 (per investigation)
    investigation_id: Mapped[str] = mapped_column(String(64), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    tier: Mapped[str] = mapped_column(String(32), default="FACT")  # EvidenceTier
    producer: Mapped[str] = mapped_column(String(64), default="")  # capability name
    producer_version: Mapped[str] = mapped_column(String(64), default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256 hex

    case: Mapped[InvestigationCase] = relationship(back_populates="evidence")

    __table_args__ = (
        UniqueConstraint(
            "case_id", "source", "source_reference", name="uq_evidence_case_source_ref"
        ),
        UniqueConstraint("case_id", "evidence_id", name="uq_evidence_case_evidence_id"),
    )


class AuditEvent(Base):
    """Durable audit event (Phase 11) - business history, not operational logs.

    Append-only: rows are inserted once per (case, event_type, idempotency
    key); updates are rejected at the persistence layer.
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("investigation_cases.id", ondelete="CASCADE"), index=True
    )
    investigation_id: Mapped[str] = mapped_column(String(64), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    event_type: Mapped[str] = mapped_column(String(64), index=True)  # AuditEventType value
    actor_type: Mapped[str] = mapped_column(String(16), default="SYSTEM")  # ActorType
    source: Mapped[str] = mapped_column(String(64), default="")  # node/capability
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)
    event_id: Mapped[str] = mapped_column(String(80), index=True)  # idempotency key
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    case: Mapped[InvestigationCase] = relationship(back_populates="audit_events")

    __table_args__ = (
        UniqueConstraint("case_id", "event_id", name="uq_audit_case_event_id"),
        Index("ix_audit_events_case_seq", "case_id", "id"),
    )


class KnowledgeDocument(TimestampMixin, Base):
    """Stored knowledge document (Phase 12 RAG): policy/regulation/typology.

    Content is curated data, never LLM-generated. ``version`` +
    ``effective_date`` let retrieval reason about document currency.
    """

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # POLICY | REGULATION | TYPOLOGY | PROCEDURE
    document_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    jurisdiction: Mapped[str] = mapped_column(String(16), default="GLOBAL", index=True)
    effective_date: Mapped[str] = mapped_column(String(10))  # ISO date string
    version: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(255))
    sections: Mapped[list[dict]] = mapped_column(JSONB)  # [{section, content}, ...]


class KnowledgeChunk(TimestampMixin, Base):
    """Indexed chunk of a knowledge document (Phase 12 RAG).

    One row per document section (stable chunking). ``content_hash`` detects
    corpus changes; ``term_freq`` stores the embedding vector so retrieval is
    a pure read + score computation (no re-embedding at query time).
    """

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.document_id", ondelete="CASCADE"), index=True
    )
    section: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    term_freq: Mapped[dict] = mapped_column(JSONB)  # sparse TF vector
    content_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("document_id", "section", name="uq_knowledge_doc_section"),)
