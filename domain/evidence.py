"""Evidence & audit domain model (Phase 11).

Evidence is a durable, immutable, traceable audit artifact. This module owns
the *canonicalization + integrity hashing* rules shared by persistence and the
reconstruction service, so the same content always produces the same hash:

- hashes cover semantic content only (never DB-generated timestamps);
- evidence tiers keep provenance explicit: a stored database fact, a
  graph-derived structural signal, a mock risk output, and an agent finding
  are never collapsed into one generic type;
- audit events are durable business events - distinct from operational logs.
"""

import hashlib
import json
from enum import StrEnum
from typing import Any

# Fields covered by the integrity hash: semantic evidence content. Database
# timestamps are deliberately excluded (they change independently of content).
HASHED_FIELDS: tuple[str, ...] = (
    "evidence_id",
    "investigation_id",
    "transaction_id",
    "category",
    "source",
    "tier",
    "producer",
    "producer_version",
    "reference",
    "description",
    "data",
)


class EvidenceTier(StrEnum):
    """Provenance tier: what *kind* of claim this evidence represents."""

    FACT = "FACT"  # PostgreSQL-backed transaction/account/device/IP facts
    STRUCTURAL_SIGNAL = "STRUCTURAL_SIGNAL"  # Neo4j graph relationships
    MODEL_OUTPUT = "MODEL_OUTPUT"  # risk provider output (currently MOCK)
    AGENT_FINDING = "AGENT_FINDING"  # LLM interpretation - never a raw fact
    KNOWLEDGE = "KNOWLEDGE"  # reserved for future RAG/policy evidence


class ActorType(StrEnum):
    """Who caused an audit event."""

    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    HUMAN = "HUMAN"


class AuditEventType(StrEnum):
    """Durable business/audit events (not operational logs)."""

    INVESTIGATION_STARTED = "INVESTIGATION_STARTED"
    TRANSACTION_LOADED = "TRANSACTION_LOADED"
    ACCOUNT_CONTEXT_LOADED = "ACCOUNT_CONTEXT_LOADED"
    GRAPH_CONTEXT_LOADED = "GRAPH_CONTEXT_LOADED"
    RISK_CONTEXT_LOADED = "RISK_CONTEXT_LOADED"
    KNOWLEDGE_CONTEXT_LOADED = "KNOWLEDGE_CONTEXT_LOADED"
    AGENT_STARTED = "AGENT_STARTED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    EVIDENCE_VALIDATED = "EVIDENCE_VALIDATED"
    REPORT_CREATED = "REPORT_CREATED"
    REPORT_VALIDATED = "REPORT_VALIDATED"
    PERSISTENCE_STARTED = "PERSISTENCE_STARTED"
    PERSISTENCE_COMPLETED = "PERSISTENCE_COMPLETED"
    INVESTIGATION_COMPLETED = "INVESTIGATION_COMPLETED"
    INVESTIGATION_FAILED = "INVESTIGATION_FAILED"


def canonicalize(payload: dict[str, Any], fields: tuple[str, ...] = HASHED_FIELDS) -> str:
    """Deterministic JSON for the given fields, in field order.

    ``sort_keys=True`` makes the form key-order-insensitive: PostgreSQL JSONB
    does not preserve object key order, so canonical forms must survive a
    database round-trip unchanged.
    """
    return json.dumps(
        {field: payload.get(field) for field in fields},
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )


def content_hash(payload: dict[str, Any]) -> str:
    """SHA-256 over canonicalized evidence content (integrity mechanism).

    Detects content modification; it is not a cryptographic proof of external
    provenance.
    """
    return hashlib.sha256(canonicalize(payload).encode("utf-8")).hexdigest()
