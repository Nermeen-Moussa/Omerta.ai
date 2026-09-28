"""Typed LangGraph investigation state (Phase 8).

The state is a **serializable investigation snapshot** - never a container for
sessions, engines, drivers, MCP connections, or secrets. Nodes write plain
JSON-safe payloads (dicts produced by ``model_dump(mode="json")`` from the
existing domain schemas) so the state can be checkpointed or logged safely.

List fields use ``operator.add`` reducers so nodes append without clobbering.
Scalar fields are plain Pydantic fields; each node returns only its updates.
"""

import operator
from enum import StrEnum
from typing import Annotated, Any

from domain.evidence import ActorType, AuditEventType
from domain.schemas import ToolErrorOut
from pydantic import BaseModel, Field, field_validator


def _merge_dicts(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    """Reducer merging per-node timing dicts (later entries win)."""
    return {**left, **right}


class InvestigationStatus(StrEnum):
    """Explicit investigation lifecycle statuses."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class EvidenceCategory(StrEnum):
    """Evidence categories preserving provenance (fact vs signal)."""

    TRANSACTION = "TRANSACTION"
    ACCOUNT = "ACCOUNT"
    HISTORY = "HISTORY"
    DEVICE = "DEVICE"
    IP = "IP"
    GRAPH = "GRAPH"
    RISK = "RISK"


class EvidenceItem(BaseModel):
    """Orchestration-level evidence with explicit provenance.

    ``category`` + ``source`` make it possible to answer "where did this
    information come from?". This is NOT the final Phase 11 evidence system.
    """

    evidence_id: str
    category: EvidenceCategory
    source: str  # transaction | graph | risk (capability that produced it)
    reference: str  # business key, e.g. TXN-001, DEV-123, ACC-1001
    description: str
    data: dict[str, Any] = Field(default_factory=dict)


class InvestigationRunRequest(BaseModel):
    """Request body for running one investigation via the API."""

    transaction_id: str = Field(min_length=1, max_length=64)
    alert_id: str | None = None
    persist: bool = Field(
        default=False,
        description="Persist case + evidence after a COMPLETED run (explicit opt-in).",
    )

    @field_validator("transaction_id", "alert_id")
    @classmethod
    def _ids_not_blank(cls, value: str | None) -> str | None:
        """Reject whitespace-only identifiers cleanly (HTTP 422)."""
        if value is None:
            return None
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class AuditEventItem(BaseModel):
    """Durable business/audit event collected during a run (Phase 11).

    Deliberately distinct from operational logs: these become persisted rows
    in ``audit_events`` inside the persistence transaction.
    """

    event_type: AuditEventType
    actor_type: ActorType = ActorType.SYSTEM
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class InvestigationState(BaseModel):
    """Serializable snapshot of one investigation run.

    Context payloads are JSON-safe dicts (already ``model_dump``ed by the
    capability layer). No sessions, engines, drivers, or secrets ever enter
    this state.
    """

    # --- Identification ---
    investigation_id: str = ""
    transaction_id: str
    alert_id: str | None = None

    # --- Lifecycle ---
    status: InvestigationStatus = InvestigationStatus.PENDING

    # --- Transaction capability context ---
    transaction: dict[str, Any] | None = None
    account: dict[str, Any] | None = None
    account_history: dict[str, Any] | None = None
    recipient_history: dict[str, Any] | None = None
    device_history: dict[str, Any] | None = None
    ip_history: dict[str, Any] | None = None

    # --- Graph capability context (structural signals, never verdicts) ---
    graph_neighbors: dict[str, Any] | None = None
    connected_accounts: dict[str, Any] | None = None
    shared_devices: dict[str, Any] | None = None
    shared_ips: dict[str, Any] | None = None
    transaction_paths: dict[str, Any] | None = None
    fraud_ring_signals: dict[str, Any] | None = None

    # --- Risk capability context (provenance preserved: source=MOCK) ---
    risk_score: dict[str, Any] | None = None
    risk_features: dict[str, Any] | None = None
    risk_feature_importance: dict[str, Any] | None = None
    previous_risk_events: dict[str, Any] | None = None

    # --- Collected evidence ---
    evidence: Annotated[list[EvidenceItem], operator.add] = []

    # --- Agent report (Phase 9; None until analyze_with_agent runs) ---
    report: dict[str, Any] | None = None

    # --- Durable audit events (Phase 11) ---
    audit_events: Annotated[list[AuditEventItem], operator.add] = []

    # --- Diagnostics ---
    errors: Annotated[list[ToolErrorOut], operator.add] = []
    warnings: Annotated[list[ToolErrorOut], operator.add] = []

    # --- Observability: per-node durations in milliseconds (Phase 10) ---
    # Merged as dict-unions so each node contributes its own timing entry.
    node_timings_ms: Annotated[dict[str, float], _merge_dicts] = {}
