"""LangGraph nodes for the deterministic investigation workflow.

Each node receives the typed state and returns a partial state update. Nodes
delegate all data access to the capability wrappers (existing domain services)
and never touch infrastructure directly. The agent node (Phase 9) reasons over
the snapshot; everything else is deterministic orchestration.

Phase 10 hardening in this module:
- every node records its duration (``node_timings_ms``) for latency analysis;
- lifecycle logs: transaction_loaded / account_loaded / graph_loaded /
  risk_loaded / agent_started / agent_completed / evidence_validated;
- ``assemble_evidence`` enforces the lifecycle (no FAILED -> COMPLETED
  transition), validates evidence-id uniqueness, report integrity
  (transaction-id match, bounds, enums, evidence references), and refuses to
  emit COMPLETED when any error or validation failure is present.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from domain.evidence import ActorType, AuditEventType
from domain.report import InvestigationReport, RecommendedAction, ReportRiskLevel
from domain.schemas import ToolErrorOut

from apps.investigator.capabilities import (
    GraphCapability,
    KnowledgeCapability,
    RiskCapability,
    TransactionCapability,
)
from apps.investigator.state import (
    AuditEventItem,
    EvidenceCategory,
    EvidenceItem,
    InvestigationState,
    InvestigationStatus,
)

logger = logging.getLogger(__name__)

# Existing service limits (single source of truth stays in the services).
CONTEXT_LIMIT = 20
MAX_DEPTH = 3
KNOWLEDGE_TOP_K = 3  # Phase 12: retrieved knowledge sections per investigation

_investigations = 0


def _audit(
    event_type: AuditEventType,
    node: str,
    *,
    actor: ActorType = ActorType.SYSTEM,
    **metadata: Any,
) -> AuditEventItem:
    """Durable audit event emitted by a node (metadata = small scalars only)."""
    return AuditEventItem(
        event_type=event_type, actor_type=actor, source=node, metadata=dict(metadata)
    )


def _make_investigation_id() -> str:
    """Globally-unique investigation id (audit requirement: a genuinely new
    run must never collide with a historical investigation - including runs
    from other processes on the same day, hence the random suffix)."""
    global _investigations
    _investigations += 1
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"INV-{stamp}-{uuid4().hex[:6]}-{_investigations:04d}"


def _not_found(resource: str, resource_id: str) -> ToolErrorOut:
    return ToolErrorOut(error="NOT_FOUND", resource=resource, id=resource_id)


def _dependency_error(context: str, detail: str) -> ToolErrorOut:
    return ToolErrorOut(error="DEPENDENCY_ERROR", detail=f"{context}: {detail}")


def _validation_error(field: str, message: str) -> ToolErrorOut:
    return ToolErrorOut(error="VALIDATION_ERROR", field=field, detail=message)


def _log_event(
    event: str,
    state: InvestigationState,
    node: str,
    *,
    status: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """Structured lifecycle log - never includes payloads or secrets."""
    extra: dict[str, Any] = {
        "investigation_id": state.investigation_id,
        "transaction_id": state.transaction_id,
        "node": node,
    }
    if status is not None:
        extra["status"] = status
    if duration_ms is not None:
        extra["duration_ms"] = round(duration_ms, 2)
    logger.info(event, extra=extra)


def _evidence_batch(
    state: InvestigationState,
    specs: list[tuple[EvidenceCategory, str, str, str, dict[str, Any]]],
) -> list[EvidenceItem]:
    """Build evidence items continuing the state's numbering sequentially.

    Each spec is ``(category, source, reference, description, data)``.
    """
    base = len(state.evidence)
    return [
        EvidenceItem(
            evidence_id=f"EV-{base + index + 1:03d}",
            category=category,
            source=source,
            reference=reference,
            description=description,
            data=data,
        )
        for index, (category, source, reference, description, data) in enumerate(specs)
    ]


# --------------------------------------------------------------------------- #
# Node 1: initialize_investigation
# --------------------------------------------------------------------------- #
async def initialize_investigation(state: InvestigationState) -> dict[str, Any]:
    _log_event("investigation_started", state, "initialize_investigation", status="RUNNING")
    started = time.perf_counter()
    updates: dict[str, Any] = {"status": InvestigationStatus.RUNNING}
    if not state.investigation_id:
        updates["investigation_id"] = _make_investigation_id()
    updates["node_timings_ms"] = {
        "initialize_investigation": (time.perf_counter() - started) * 1000
    }
    updates["audit_events"] = [
        _audit(AuditEventType.INVESTIGATION_STARTED, "initialize_investigation")
    ]
    return updates


# --------------------------------------------------------------------------- #
# Node 2: load_transaction
# --------------------------------------------------------------------------- #
async def load_transaction(
    state: InvestigationState, *, transactions: TransactionCapability | None = None
) -> dict[str, Any]:
    cap = transactions or TransactionCapability()
    started = time.perf_counter()
    txn = await cap.get_transaction(state.transaction_id)
    duration_ms = (time.perf_counter() - started) * 1000
    if txn is None:
        logger.warning(
            "node_failed",
            extra={
                "investigation_id": state.investigation_id,
                "transaction_id": state.transaction_id,
                "node": "load_transaction",
                "duration_ms": round(duration_ms, 2),
            },
        )
        return {
            "status": InvestigationStatus.FAILED,
            "errors": [_not_found("transaction", state.transaction_id)],
            "node_timings_ms": {"load_transaction": duration_ms},
            "audit_events": [
                _audit(
                    AuditEventType.INVESTIGATION_FAILED,
                    "load_transaction",
                    reason="transaction_not_found",
                )
            ],
        }
    evidence = _evidence_batch(
        state,
        [
            (
                EvidenceCategory.TRANSACTION,
                "transaction",
                state.transaction_id,
                "Transaction facts: amount, currency, type, status, device, IP",
                {"transaction": txn},
            )
        ],
    )
    _log_event("transaction_loaded", state, "load_transaction", duration_ms=duration_ms)
    return {
        "transaction": txn,
        "evidence": evidence,
        "node_timings_ms": {"load_transaction": duration_ms},
        "audit_events": [
            _audit(
                AuditEventType.TRANSACTION_LOADED,
                "load_transaction",
                transaction_id=state.transaction_id,
            )
        ],
    }


# --------------------------------------------------------------------------- #
# Node 3: load_account_context
# --------------------------------------------------------------------------- #
async def load_account_context(
    state: InvestigationState, *, transactions: TransactionCapability | None = None
) -> dict[str, Any]:
    cap = transactions or TransactionCapability()
    started = time.perf_counter()
    txn = state.transaction
    if txn is None:
        return {
            "warnings": [
                _validation_error("transaction", "account context skipped: no transaction loaded")
            ],
            "node_timings_ms": {"load_account_context": (time.perf_counter() - started) * 1000},
        }

    sender_id = txn["sender"]["external_id"]
    recipient_id = txn["recipient"]["external_id"]
    device_id = (txn.get("device") or {}).get("external_id")
    ip_address = (txn.get("ip") or {}).get("address")

    account = await cap.get_account(sender_id)
    account_history = await cap.get_account_transactions(sender_id, CONTEXT_LIMIT)
    recipient_history = await cap.get_recipient_history(recipient_id, CONTEXT_LIMIT)
    device_history = await cap.get_device_history(device_id, CONTEXT_LIMIT) if device_id else None
    ip_history = await cap.get_ip_history(ip_address, CONTEXT_LIMIT) if ip_address else None

    sections = {
        "account_history": account_history,
        "recipient_history": recipient_history,
        "device_history": device_history,
        "ip_history": ip_history,
    }
    missing = sorted(key for key, value in sections.items() if value is None)

    specs: list[tuple[EvidenceCategory, str, str, str, dict[str, Any]]] = []
    if account is not None:
        specs.append(
            (
                EvidenceCategory.ACCOUNT,
                "transaction",
                sender_id,
                "Originator account facts",
                {"account": account},
            )
        )
    if account_history is not None:
        specs.append(
            (
                EvidenceCategory.HISTORY,
                "transaction",
                sender_id,
                "Originator transaction history (newest first)",
                {"count": account_history.get("count", 0)},
            )
        )
    if recipient_history is not None:
        specs.append(
            (
                EvidenceCategory.HISTORY,
                "transaction",
                recipient_id,
                "Recipient transaction history (newest first)",
                {"count": recipient_history.get("count", 0)},
            )
        )
    if device_id and device_history is not None:
        specs.append(
            (
                EvidenceCategory.DEVICE,
                "transaction",
                device_id,
                "Device usage history",
                {"count": device_history.get("count", 0)},
            )
        )
    if ip_address and ip_history is not None:
        specs.append(
            (
                EvidenceCategory.IP,
                "transaction",
                ip_address,
                "IP usage history",
                {"count": ip_history.get("count", 0)},
            )
        )

    updates: dict[str, Any] = {"account": account, **sections}
    if specs:
        updates["evidence"] = _evidence_batch(state, specs)

    if account is None:
        updates["errors"] = [_not_found("account", sender_id)]
    if missing:
        updates["warnings"] = [
            _dependency_error("transaction-history", f"sections unavailable: {', '.join(missing)}")
        ]
    duration_ms = (time.perf_counter() - started) * 1000
    _log_event("account_loaded", state, "load_account_context", duration_ms=duration_ms)
    updates["node_timings_ms"] = {"load_account_context": duration_ms}
    updates["audit_events"] = [
        _audit(
            AuditEventType.ACCOUNT_CONTEXT_LOADED,
            "load_account_context",
            account_id=sender_id,
            missing_sections=len(missing),
        )
    ]
    return updates


# --------------------------------------------------------------------------- #
# Node 4: load_graph_context
# --------------------------------------------------------------------------- #
async def load_graph_context(
    state: InvestigationState, *, graphs: GraphCapability | None = None
) -> dict[str, Any]:
    cap = graphs or GraphCapability()
    started = time.perf_counter()
    txn = state.transaction
    if txn is None:
        return {
            "warnings": [
                _validation_error("transaction", "graph context skipped: no transaction loaded")
            ],
            "node_timings_ms": {"load_graph_context": (time.perf_counter() - started) * 1000},
        }

    sender_id = txn["sender"]["external_id"]
    recipient_id = txn["recipient"]["external_id"]

    results = {
        "graph_neighbors": await cap.get_account_neighbors(sender_id, CONTEXT_LIMIT),
        "connected_accounts": await cap.find_connected_accounts(sender_id, CONTEXT_LIMIT),
        "shared_devices": await cap.find_shared_devices(sender_id, CONTEXT_LIMIT),
        "shared_ips": await cap.find_shared_ips(sender_id, CONTEXT_LIMIT),
        "transaction_paths": await cap.find_transaction_paths(sender_id, recipient_id, MAX_DEPTH),
        "fraud_ring_signals": await cap.find_fraud_ring(sender_id, MAX_DEPTH, CONTEXT_LIMIT),
    }
    missing = sorted(key for key, value in results.items() if value is None)

    descriptions = {
        "graph_neighbors": "Direct graph neighbors of the originator",
        "connected_accounts": (
            "Accounts connected via direct transaction, shared device, or shared IP"
        ),
        "shared_devices": "Devices shared with other accounts (structural signal)",
        "shared_ips": "IP addresses shared with other accounts (structural signal)",
        "transaction_paths": "Bounded transaction paths originator -> recipient",
        "fraud_ring_signals": (
            "Structural signals around the originator (evidence, not a verdict)"
        ),
    }
    specs = [
        (
            EvidenceCategory.GRAPH,
            "graph",
            sender_id,
            descriptions[key],
            {"section": key, "payload": results[key]},
        )
        for key in descriptions
        if results[key] is not None
    ]

    updates: dict[str, Any] = dict(results)
    if specs:
        updates["evidence"] = _evidence_batch(state, specs)
    if missing:
        updates["warnings"] = [
            _dependency_error("graph", f"sections unavailable: {', '.join(missing)}")
        ]
    duration_ms = (time.perf_counter() - started) * 1000
    _log_event("graph_loaded", state, "load_graph_context", duration_ms=duration_ms)
    updates["node_timings_ms"] = {"load_graph_context": duration_ms}
    updates["audit_events"] = [
        _audit(
            AuditEventType.GRAPH_CONTEXT_LOADED,
            "load_graph_context",
            sections_retrieved=len(results) - len(missing),
        )
    ]
    return updates


# --------------------------------------------------------------------------- #
# Node 5: load_risk_context
# --------------------------------------------------------------------------- #
async def load_risk_context(
    state: InvestigationState, *, risks: RiskCapability | None = None
) -> dict[str, Any]:
    cap = risks or RiskCapability()
    started = time.perf_counter()
    txn = state.transaction
    if txn is None:
        return {
            "warnings": [
                _validation_error("transaction", "risk context skipped: no transaction loaded")
            ],
            "node_timings_ms": {"load_risk_context": (time.perf_counter() - started) * 1000},
        }

    sender_id = txn["sender"]["external_id"]
    txn_id = state.transaction_id

    results = {
        "risk_score": await cap.get_risk_score(txn_id),
        "risk_features": await cap.get_risk_features(txn_id),
        "risk_feature_importance": await cap.get_feature_importance(txn_id),
        "previous_risk_events": await cap.get_previous_risk_events(sender_id),
    }
    missing = sorted(key for key, value in results.items() if value is None)

    descriptions = {
        "risk_score": "Mock risk score with provenance (source=MOCK)",
        "risk_features": "Risk features derived from database facts",
        "risk_feature_importance": "Mock feature contributions (not SHAP, not ML)",
        "previous_risk_events": "Stored alert facts for the originator",
    }
    specs = [
        (
            EvidenceCategory.RISK,
            "risk",
            txn_id,
            descriptions[key],
            {"section": key, "payload": results[key]},
        )
        for key in descriptions
        if results[key] is not None
    ]

    updates: dict[str, Any] = dict(results)
    if specs:
        updates["evidence"] = _evidence_batch(state, specs)
    if missing:
        updates["warnings"] = [
            _dependency_error("risk", f"sections unavailable: {', '.join(missing)}")
        ]
    duration_ms = (time.perf_counter() - started) * 1000
    _log_event("risk_loaded", state, "load_risk_context", duration_ms=duration_ms)
    updates["node_timings_ms"] = {"load_risk_context": duration_ms}
    updates["audit_events"] = [
        _audit(
            AuditEventType.RISK_CONTEXT_LOADED,
            "load_risk_context",
            sections_retrieved=len(results) - len(missing),
        )
    ]
    return updates


# --------------------------------------------------------------------------- #
# Node 5b: load_knowledge_context (Phase 12 RAG)
# --------------------------------------------------------------------------- #
async def load_knowledge_context(
    state: InvestigationState, *, knowledge: KnowledgeCapability | None = None
) -> dict[str, Any]:
    """Retrieve stored policy/typology knowledge for the signals in this run.

    Deterministic TF-IDF retrieval over the curated corpus (Knowledge MCP
    service). The query derives from the structural/risk signals observed in
    this investigation. Retrieval is supporting context: any failure yields a
    warning and an empty result - it never fails the investigation.
    """
    cap = knowledge or KnowledgeCapability()
    started = time.perf_counter()
    if state.transaction is None:
        return {
            "warnings": [
                _validation_error("transaction", "knowledge context skipped: no transaction loaded")
            ],
            "node_timings_ms": {"load_knowledge_context": (time.perf_counter() - started) * 1000},
        }

    # Query derives from observed signals (deterministic; short keyword set).
    query_parts = ["money laundering"]
    graph_signals = (state.fraud_ring_signals or {}).get("signals", [])
    if graph_signals:
        query_parts.append("shared device fraud ring")
    if (state.shared_devices or {}).get("shared_devices"):
        query_parts.append("shared device")
    if (state.shared_ips or {}).get("shared_ips"):
        query_parts.append("shared ip")
    risk = state.risk_score or {}
    if risk.get("risk_level") == "HIGH":
        query_parts.append("new device account takeover threshold")
    txn = state.transaction or {}
    try:
        amount = float(txn.get("amount") or 0)
        if amount >= 10000:
            query_parts.append("large transaction review threshold")
        elif amount >= 4000:
            query_parts.append("escalation rule")
    except (TypeError, ValueError):
        pass
    query = " ".join(query_parts)

    results = await cap.search_knowledge(query, KNOWLEDGE_TOP_K)
    missing = results is None
    chunks: list[dict[str, Any]] = results.get("results", []) if results else []

    specs: list[tuple[EvidenceCategory, str, str, str, dict[str, Any]]] = []
    if chunks:
        specs.append(
            (
                EvidenceCategory.KNOWLEDGE,
                "knowledge",
                state.transaction_id,
                "Retrieved policy/typology knowledge (cited sections)",
                {"query": query, "chunks": chunks},
            )
        )

    updates: dict[str, Any] = {"knowledge_query": query}
    if results is not None:
        updates["knowledge_results"] = results
    if specs:
        updates["evidence"] = _evidence_batch(state, specs)
    if missing:
        updates["warnings"] = [_dependency_error("knowledge", "knowledge retrieval unavailable")]
    duration_ms = (time.perf_counter() - started) * 1000
    _log_event("knowledge_loaded", state, "load_knowledge_context", duration_ms=duration_ms)
    updates["node_timings_ms"] = {"load_knowledge_context": duration_ms}
    updates["audit_events"] = [
        _audit(
            AuditEventType.KNOWLEDGE_CONTEXT_LOADED,
            "load_knowledge_context",
            query_terms=len(query.split()),
            chunks=len(chunks),
        )
    ]
    return updates


# --------------------------------------------------------------------------- #
# Node 6: analyze_with_agent (Phase 9)
# --------------------------------------------------------------------------- #
async def analyze_with_agent(state: InvestigationState) -> dict[str, Any]:
    """Reason over the snapshot and attach a validated, evidence-referenced
    report. Deterministic with the fake provider; LLM-backed otherwise."""
    from apps.investigator.agent import run_agent

    _log_event("agent_started", state, "analyze_with_agent")
    started = time.perf_counter()
    try:
        outcome = await run_agent(state.model_dump(mode="json"))
    except Exception as exc:
        logger.error(
            "node_failed",
            extra={
                "investigation_id": state.investigation_id,
                "transaction_id": state.transaction_id,
                "node": "analyze_with_agent",
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return {
            "errors": [
                ToolErrorOut(
                    error="DEPENDENCY_ERROR",
                    detail=f"agent analysis failed: {type(exc).__name__}",
                )
            ],
            "node_timings_ms": {"analyze_with_agent": (time.perf_counter() - started) * 1000},
            "audit_events": [
                _audit(AuditEventType.AGENT_STARTED, "analyze_with_agent", actor=ActorType.AGENT)
            ],
        }
    report = outcome.report.model_dump(mode="json")
    duration_ms = (time.perf_counter() - started) * 1000
    _log_event("agent_completed", state, "analyze_with_agent", duration_ms=duration_ms)
    return {
        "report": report,
        "node_timings_ms": {"analyze_with_agent": duration_ms},
        "audit_events": [
            _audit(AuditEventType.AGENT_STARTED, "analyze_with_agent", actor=ActorType.AGENT),
            _audit(
                AuditEventType.AGENT_COMPLETED,
                "analyze_with_agent",
                actor=ActorType.AGENT,
                findings=len(report["findings"]),
            ),
            _audit(
                AuditEventType.REPORT_CREATED,
                "analyze_with_agent",
                actor=ActorType.AGENT,
                recommended_action=report["recommended_action"],
            ),
        ],
    }


# --------------------------------------------------------------------------- #
# Node 7: assemble_evidence
# --------------------------------------------------------------------------- #
def _report_integrity_issues(state: InvestigationState) -> list[str]:
    """Defense-in-depth validation of the agent report (Phase 10).

    The agent already validates its own output; this guard means malformed
    reports can never reach persistence even via a hand-crafted state.
    """
    issues: list[str] = []
    report = state.report
    if report is None:
        return issues

    # Evidence references must exist; evidence ids must be unique.
    valid_ids = {item.evidence_id for item in state.evidence}
    if len(valid_ids) != len(state.evidence):
        issues.append("duplicate evidence ids in state")
    for finding in report.get("findings", []):
        unknown = sorted(set(finding.get("evidence_ids", [])) - valid_ids)
        if unknown:
            issues.append(f"finding references unknown evidence ids: {unknown}")

    try:
        validated = InvestigationReport.model_validate(report)
    except Exception as exc:  # noqa: BLE001 - any failure is a hard stop
        issues.append(f"report schema validation failed: {type(exc).__name__}")
        return issues

    if validated.transaction_id != state.transaction_id:
        issues.append(
            f"report transaction_id {validated.transaction_id!r} does not match "
            f"investigation {state.transaction_id!r}"
        )
    try:
        ReportRiskLevel(validated.risk_level)
        RecommendedAction(validated.recommended_action)
    except ValueError:
        issues.append("report contains invalid enum values")
    return issues


async def assemble_evidence(state: InvestigationState) -> dict[str, Any]:
    """Finalize the run: COMPLETED only when everything validates.

    Lifecycle rule: a run that already FAILED (or carries errors) can never
    become COMPLETED. Report/evidence integrity failures are hard failures -
    no malformed result reaches persistence.
    """
    issues = _report_integrity_issues(state)
    if issues:
        _log_event(
            "evidence_validated",
            state,
            "assemble_evidence",
            status="VALIDATION_FAILED",
        )
        return {
            "status": InvestigationStatus.FAILED,
            "errors": [_validation_error("report", "; ".join(issues))],
            "node_timings_ms": {"assemble_evidence": 0.0},
            "audit_events": [
                _audit(
                    AuditEventType.REPORT_VALIDATED,
                    "assemble_evidence",
                    outcome="VALIDATION_FAILED",
                )
            ],
        }

    _log_event("evidence_validated", state, "assemble_evidence", status="OK")

    if state.errors or state.status == InvestigationStatus.FAILED:
        # FAILED -> COMPLETED is forbidden; errors keep the run FAILED.
        logger.warning(
            "investigation_failed",
            extra={
                "investigation_id": state.investigation_id,
                "transaction_id": state.transaction_id,
                "node": "assemble_evidence",
                "status": InvestigationStatus.FAILED.value,
            },
        )
        return {
            "status": InvestigationStatus.FAILED,
            "node_timings_ms": {"assemble_evidence": 0.0},
            "audit_events": [
                _audit(
                    AuditEventType.EVIDENCE_VALIDATED, "assemble_evidence", outcome="WITH_ERRORS"
                ),
                _audit(
                    AuditEventType.INVESTIGATION_FAILED,
                    "assemble_evidence",
                    reason="errors_present",
                ),
            ],
        }
    logger.info(
        "investigation_completed",
        extra={
            "investigation_id": state.investigation_id,
            "transaction_id": state.transaction_id,
            "node": "assemble_evidence",
            "status": InvestigationStatus.COMPLETED.value,
        },
    )
    return {
        "status": InvestigationStatus.COMPLETED,
        "node_timings_ms": {"assemble_evidence": 0.0},
        "audit_events": [
            _audit(
                AuditEventType.EVIDENCE_VALIDATED,
                "assemble_evidence",
                outcome="OK",
                evidence_count=len(state.evidence),
            ),
            _audit(AuditEventType.REPORT_VALIDATED, "assemble_evidence", outcome="OK"),
            _audit(AuditEventType.INVESTIGATION_COMPLETED, "assemble_evidence"),
        ],
    }
