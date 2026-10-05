"""SQLAlchemy 2.x ORM models for Omerta.ai banking intelligence platform.

The database stores FACTS (transactions, customers, accounts, devices, sessions,
IPs, alerts, risk assessments, signals, cases, evidence, dispositions, audit events,
ledger entries, transfers).
LLM-generated conclusions are never stored here as facts; AI findings live in
investigation artifacts with explicit provenance.

Schema notes:
- Every business entity carries a stable ``external_id`` (e.g. "TXN-001", "CUST-101")
  used across the API, MCP tools, and seed data; integer PKs are internal.
- Status/type/risk columns are plain strings (validated at the Pydantic layer).
- Multi-tier risk workflow stores granular signals in ``risk_signals`` and aggregated
  assessments in ``risk_assessments``.
- Ledger entries provide immutable auditability for demo account balances.
- Customers have a unique, non-sensitive ``omerta_user_number`` for simulated transfers.
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
from sqlalchemy.ext.asyncio import AsyncEngine
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


class User(TimestampMixin, Base):
    """System user: customer, compliance analyst, or administrator."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # CUSTOMER | ADMINISTRATOR | FRAUD_ANALYST | SENIOR_INVESTIGATOR | AUDITOR
    role: Mapped[str] = mapped_column(String(32), default="CUSTOMER", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    customer: Mapped["Customer | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")


class Customer(TimestampMixin, Base):
    """Banking customer profile (individual or corporate)."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Unique non-sensitive identifier shareable between users for simulated transfers (e.g. OMR-8492-3011)
    omerta_user_number: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    # INDIVIDUAL | BUSINESS | CORPORATE
    customer_type: Mapped[str] = mapped_column(String(32), default="INDIVIDUAL", index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    phone: Mapped[str] = mapped_column(String(64), nullable=True)
    country: Mapped[str] = mapped_column(String(2), default="EG", index=True)
    declared_country: Mapped[str] = mapped_column(String(2), default="EG", index=True)
    observed_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    preferred_currency: Mapped[str] = mapped_column(String(3), default="EGP", index=True)
    device_consent: Mapped[bool] = mapped_column(Boolean, default=True)
    device_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)
    registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="customer")
    accounts: Mapped[list["Account"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="customer")
    transfers_sent: Mapped[list["Transfer"]] = relationship(
        foreign_keys="Transfer.sender_customer_id", back_populates="sender_customer"
    )
    transfers_received: Mapped[list["Transfer"]] = relationship(
        foreign_keys="Transfer.recipient_customer_id", back_populates="recipient_customer"
    )


class Account(Base):
    """Customer bank account."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=True
    )
    customer_name: Mapped[str] = mapped_column(String(255))
    # CHECKING | SAVINGS | BUSINESS | WIRE_CLEARING | DEMO
    account_type: Mapped[str] = mapped_column(String(32), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="EGP", index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"))
    country: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    customer: Mapped[Customer | None] = relationship(back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", foreign_keys="Transaction.account_id"
    )
    recipient_transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="recipient_account",
        foreign_keys="Transaction.recipient_account_id",
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="account")
    ledger_entries: Mapped[list["AccountLedgerEntry"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", order_by="AccountLedgerEntry.id.desc()"
    )

    def __repr__(self) -> str:
        return f"Account(external_id={self.external_id!r}, balance={self.balance}, currency={self.currency})"


class Device(Base):
    """Device used for transactions and login sessions."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_type: Mapped[str] = mapped_column(String(32))  # MOBILE | DESKTOP | TABLET
    platform: Mapped[str] = mapped_column(String(32), default="Android")
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pseudonym_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    is_emulator: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rooted: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="device")


class IPAddress(Base):
    """IP address seen during transactions."""

    __tablename__ = "ip_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    address: Mapped[str] = mapped_column(String(45), unique=True, index=True)  # IPv4/IPv6
    country: Mapped[str] = mapped_column(String(2))
    is_vpn: Mapped[bool] = mapped_column(Boolean, default=False)
    is_proxy: Mapped[bool] = mapped_column(Boolean, default=False)
    is_datacenter: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)

    sessions: Mapped[list["Session"]] = relationship(back_populates="ip_address")


class Session(Base):
    """Customer login session record."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True, nullable=True
    )
    ip_address_id: Mapped[int | None] = mapped_column(
        ForeignKey("ip_addresses.id", ondelete="SET NULL"), index=True, nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_vpn: Mapped[bool] = mapped_column(Boolean, default=False)
    is_emulator: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(back_populates="sessions")
    customer: Mapped[Customer | None] = relationship(back_populates="sessions")
    account: Mapped[Account | None] = relationship(back_populates="sessions")
    device: Mapped[Device | None] = relationship(back_populates="sessions")
    ip_address: Mapped[IPAddress | None] = relationship(back_populates="sessions")


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
    currency: Mapped[str] = mapped_column(String(3), index=True)
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
    # Cached assessment overview (0 to 100)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(String(16), default="LOW", index=True)
    # NOT_REQUIRED | REQUIRES_REVIEW | IN_REVIEW | COMPLETED | DISMISSED
    review_status: Mapped[str] = mapped_column(String(32), default="NOT_REQUIRED", index=True)
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
    risk_assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_transactions_account_timestamp", "account_id", "timestamp"),
        Index("ix_transactions_recipient_timestamp", "recipient_account_id", "timestamp"),
        Index("ix_transactions_risk_review", "risk_score", "review_status"),
    )


class Transfer(TimestampMixin, Base):
    """Simulated customer-to-customer transfer record."""

    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    sender_customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    sender_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    recipient_customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    recipient_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # COMPLETED | PENDING_REVIEW | REJECTED
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", index=True)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True, nullable=True
    )

    sender_customer: Mapped[Customer] = relationship(
        foreign_keys=[sender_customer_id], back_populates="transfers_sent"
    )
    recipient_customer: Mapped[Customer] = relationship(
        foreign_keys=[recipient_customer_id], back_populates="transfers_received"
    )
    sender_account: Mapped[Account] = relationship(foreign_keys=[sender_account_id])
    recipient_account: Mapped[Account] = relationship(foreign_keys=[recipient_account_id])
    transaction: Mapped[Transaction | None] = relationship()
    ledger_entries: Mapped[list["AccountLedgerEntry"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan"
    )


class AccountLedgerEntry(TimestampMixin, Base):
    """Immutable double-entry ledger record for account balance movements."""

    __tablename__ = "account_ledger_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    transfer_id: Mapped[int | None] = mapped_column(
        ForeignKey("transfers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # OPENING_BALANCE | DEBIT | CREDIT | ADMIN_ADJUSTMENT
    entry_type: Mapped[str] = mapped_column(String(32), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )

    account: Mapped[Account] = relationship(back_populates="ledger_entries")
    transfer: Mapped[Transfer | None] = relationship(back_populates="ledger_entries")


class RiskAssessment(TimestampMixin, Base):
    """Multi-signal risk assessment for a transaction."""

    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))  # 0.00 to 100.00
    # LOW | MODERATE | REQUIRES_REVIEW | HIGH | CRITICAL
    risk_level: Mapped[str] = mapped_column(String(24), index=True)
    # Strictly True when risk_score > 40.00
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", index=True)
    version: Mapped[str] = mapped_column(String(16), default="v1.0")
    correlation_id: Mapped[str] = mapped_column(String(80), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    transaction: Mapped[Transaction] = relationship(back_populates="risk_assessments")
    signals: Mapped[list["RiskSignal"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class RiskSignal(Base):
    """Individual contributing risk factor or behavioral signal."""

    __tablename__ = "risk_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("risk_assessments.id", ondelete="CASCADE"), index=True
    )
    signal_name: Mapped[str] = mapped_column(String(128), index=True)
    # LOW | MEDIUM | HIGH | CRITICAL
    severity: Mapped[str] = mapped_column(String(16), index=True)
    description: Mapped[str] = mapped_column(Text)
    # TRANSACTION_RULE | DEVICE_INTELLIGENCE | IP_ANALYSIS | GRAPH_PATTERN | ML_MODEL
    source: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("1.000"))
    evidence_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    assessment: Mapped[RiskAssessment] = relationship(back_populates="signals")


class Alert(Base):
    """Risk alert raised on a transaction."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), index=True
    )
    alert_type: Mapped[str] = mapped_column(String(64), index=True)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    transaction: Mapped[Transaction] = relationship(back_populates="alerts")
    cases: Mapped[list["InvestigationCase"]] = relationship(back_populates="alert")

    __table_args__ = (Index("ix_alerts_status_level", "status", "risk_level"),)


class InvestigationCase(TimestampMixin, Base):
    """Compliance investigation case opened from an alert or transaction."""

    __tablename__ = "investigation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    alert_id: Mapped[int | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), default="Financial Crime Investigation")
    # NEW | PENDING_REVIEW | UNDER_INVESTIGATION | ESCALATED | RESOLVED | CLOSED
    status: Mapped[str] = mapped_column(String(32), default="NEW", index=True)
    # LOW | MEDIUM | HIGH | CRITICAL
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(255), default=None)
    report: Mapped[dict | None] = mapped_column(JSONB, default=None)

    alert: Mapped[Alert | None] = relationship(back_populates="cases")
    transaction: Mapped[Transaction | None] = relationship()
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="case")
    notes: Mapped[list["CaseNote"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    dispositions: Mapped[list["CaseDisposition"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class CaseNote(TimestampMixin, Base):
    """Analyst note attached to an investigation case."""

    __tablename__ = "case_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("investigation_cases.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[str] = mapped_column(String(255))
    note_text: Mapped[str] = mapped_column(Text)

    case: Mapped[InvestigationCase] = relationship(back_populates="notes")


class CaseDisposition(Base):
    """Formal compliance review disposition and rationale recorded by an analyst."""

    __tablename__ = "case_dispositions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("investigation_cases.id", ondelete="CASCADE"), index=True
    )
    analyst_id: Mapped[str] = mapped_column(String(255), index=True)
    # SUSPICIOUS_FURTHER_INVESTIGATION | NO_SUSPICIOUS_ACTIVITY | LEGITIMATE_ACTIVITY | INSUFFICIENT_EVIDENCE | ESCALATED_SPECIALIST
    disposition: Mapped[str] = mapped_column(String(64), index=True)
    rationale: Mapped[str] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    case: Mapped[InvestigationCase] = relationship(back_populates="dispositions")


class Evidence(TimestampMixin, Base):
    """Durable, append-only evidence artifact."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(
        ForeignKey("investigation_cases.id", ondelete="CASCADE"), index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(64))
    source_reference: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    data: Mapped[dict | None] = mapped_column(JSONB, default=None)

    evidence_id: Mapped[str] = mapped_column(String(64), index=True)
    investigation_id: Mapped[str] = mapped_column(String(64), index=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    tier: Mapped[str] = mapped_column(String(32), default="FACT")
    producer: Mapped[str] = mapped_column(String(64), default="")
    producer_version: Mapped[str] = mapped_column(String(64), default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)

    case: Mapped[InvestigationCase] = relationship(back_populates="evidence")

    __table_args__ = (
        UniqueConstraint(
            "case_id", "source", "source_reference", name="uq_evidence_case_source_ref"
        ),
        UniqueConstraint("case_id", "evidence_id", name="uq_evidence_case_evidence_id"),
    )


class AuditEvent(Base):
    """Durable audit event - business history and compliance timeline."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("investigation_cases.id", ondelete="CASCADE"), index=True, nullable=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(64), index=True, default=None)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    # SYSTEM | ANALYST | ADMIN | CUSTOMER | SENIOR_INVESTIGATOR | COMPLIANCE_AUDITOR
    actor_type: Mapped[str] = mapped_column(String(64), default="SYSTEM")
    actor_id: Mapped[str | None] = mapped_column(String(255), default=None, index=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)
    event_id: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    case: Mapped[InvestigationCase | None] = relationship(back_populates="audit_events")

    __table_args__ = (Index("ix_audit_events_created", "created_at"),)


class KnowledgeDocument(TimestampMixin, Base):
    """Stored knowledge document (RAG): policy/regulation/typology."""

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    document_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    jurisdiction: Mapped[str] = mapped_column(String(16), default="GLOBAL", index=True)
    effective_date: Mapped[str] = mapped_column(String(10))
    version: Mapped[int] = mapped_column(Integer, default=1)
    source: Mapped[str] = mapped_column(String(255))
    sections: Mapped[list[dict]] = mapped_column(JSONB)


class KnowledgeChunk(TimestampMixin, Base):
    """Indexed chunk of a knowledge document (RAG)."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_documents.document_id", ondelete="CASCADE"), index=True
    )
    section: Mapped[str] = mapped_column(String(255))
    content: Mapped[Text] = mapped_column(Text)
    term_freq: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("document_id", "section", name="uq_knowledge_doc_section"),)


async def init_db(engine: AsyncEngine) -> None:
    """Create all database tables asynchronously if they don't already exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
