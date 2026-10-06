"""Investigation state tests: typed fields, statuses, serialization."""

import json

from apps.investigator.state import (
    EvidenceCategory,
    EvidenceItem,
    InvestigationRunRequest,
    InvestigationState,
    InvestigationStatus,
)
from domain.schemas import ToolErrorOut


def test_initial_state_defaults() -> None:
    state = InvestigationState(transaction_id="TXN-001")

    assert state.investigation_id == ""
    assert state.status == InvestigationStatus.PENDING
    assert state.errors == []
    assert state.warnings == []
    assert state.evidence == []
    assert state.transaction is None
    assert state.risk_score is None


def test_status_transitions_via_updates() -> None:
    """Nodes update the status field; model_copy simulates state updates."""
    state = InvestigationState(transaction_id="TXN-001")

    running = state.model_copy(update={"status": InvestigationStatus.RUNNING})
    completed = running.model_copy(update={"status": InvestigationStatus.COMPLETED})
    failed = running.model_copy(update={"status": InvestigationStatus.FAILED})

    assert running.status == InvestigationStatus.RUNNING
    assert completed.status == InvestigationStatus.COMPLETED
    assert failed.status == InvestigationStatus.FAILED


def test_status_values_are_controlled() -> None:
    assert {s.value for s in InvestigationStatus} == {
        "PENDING",
        "RUNNING",
        "COMPLETED",
        "FAILED",
    }


def test_evidence_item_structure_and_provenance() -> None:
    item = EvidenceItem(
        evidence_id="EV-001",
        category=EvidenceCategory.TRANSACTION,
        source="transaction",
        reference="TXN-001",
        description="Transaction facts",
        data={"amount": "8400.00"},
    )

    assert item.evidence_id == "EV-001"
    assert item.category == EvidenceCategory.TRANSACTION
    assert item.source == "transaction"
    assert item.reference == "TXN-001"


def test_state_is_serializable() -> None:
    state = InvestigationState(
        transaction_id="TXN-001",
        status=InvestigationStatus.COMPLETED,
        evidence=[
            EvidenceItem(
                evidence_id="EV-001",
                category=EvidenceCategory.RISK,
                source="risk",
                reference="TXN-001",
                description="Mock score",
                data={"risk_score": 0.9},
            )
        ],
        errors=[ToolErrorOut(error="NOT_FOUND", resource="transaction", id="X")],
    )

    dumped = state.model_dump(mode="json")
    json.dumps(dumped)  # must not raise
    assert dumped["status"] == "COMPLETED"
    assert dumped["evidence"][0]["category"] == "RISK"


def test_reducers_append_without_clobbering() -> None:
    """Simulates LangGraph reducer semantics for evidence/errors lists."""
    import operator

    base = InvestigationState(transaction_id="TXN-001")
    first = EvidenceItem(
        evidence_id="EV-001",
        category=EvidenceCategory.GRAPH,
        source="graph",
        reference="ACC-1001",
        description="signal",
    )
    second = EvidenceItem(
        evidence_id="EV-002",
        category=EvidenceCategory.RISK,
        source="risk",
        reference="TXN-001",
        description="score",
    )

    merged = operator.add(base.evidence, [first])
    merged = operator.add(merged, [second])
    assert len(merged) == 2
    assert {item.evidence_id for item in merged} == {"EV-001", "EV-002"}


def test_run_request_rejects_empty_transaction_id() -> None:
    import pytest
    from pydantic import ValidationError

    # Truly empty ids are rejected by the schema; whitespace-only ids are
    # normalized/rejected downstream by the service-layer validation.
    with pytest.raises(ValidationError):
        InvestigationRunRequest(transaction_id="")
