"""Case Management API schemas (Phase 13).

Typed request/response models over the existing domain layer. ORM objects
never cross into HTTP responses; every payload is explicit and JSON-safe.
Read endpoints expose the Phase 11 evidence/audit artifacts and the Phase 12
knowledge provenance without leaking internals.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EvidenceOut(BaseModel):
    """One evidence artifact with full provenance (Phase 11 schema)."""

    evidence_id: str
    investigation_id: str
    transaction_id: str | None
    category: str
    source: str
    reference: str
    description: str
    data: dict[str, Any]
    tier: str
    producer: str
    producer_version: str
    content_hash: str
    created_at: datetime | None = None


class AuditEventOut(BaseModel):
    """One durable audit event (business history, not operational logs)."""

    event_id: str
    event_type: str
    actor_type: str
    source: str
    metadata: dict[str, Any]
    created_at: datetime | None = None


class FindingOut(BaseModel):
    """One agent finding with its evidence references."""

    finding: str
    evidence_ids: list[str]
    confidence: float
    category: str | None = None


class ReportOut(BaseModel):
    """The stored, validated investigation report snapshot."""

    investigation_id: str
    transaction_id: str
    risk_level: str
    summary: str
    typologies: list[str] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)
    recommended_action: str
    confidence: float
    provenance: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime | None = None


class CaseSummaryOut(BaseModel):
    """List-view row for a case/investigation."""

    case_id: str
    investigation_id: str
    alert_id: str | None
    transaction_id: str | None
    status: str
    severity: str
    assigned_to: str | None = None
    created_at: datetime | None = None
    evidence_count: int = 0
    audit_event_count: int = 0


class CaseListOut(BaseModel):
    """Paginated, filtered case list."""

    items: list[CaseSummaryOut]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class InvestigationDetailOut(BaseModel):
    """Full reconstruction of one investigation (fail-closed read)."""

    investigation: dict[str, Any]
    case: dict[str, Any]
    report: ReportOut | None
    findings: list[dict[str, Any]]
    evidence: list[EvidenceOut]
    audit_events: list[AuditEventOut]


class ErrorResponse(BaseModel):
    """Structured error payload (machine-readable, no internals)."""

    error: str
    detail: str | None = None
    resource: str | None = None
    id: str | None = None
