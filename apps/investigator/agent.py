"""Investigator Agent (Phase 9): reasoning over the orchestrated evidence.

The agent node feeds the Phase 8 investigation snapshot to the configured
LLM provider and parses the reply into a validated, evidence-referenced
report. Hard guarantees, independent of the LLM:

- output must satisfy ``InvestigationReport`` (findings, typologies, action);
- every finding must reference evidence ids that exist in the state
  (one deterministic repair pass; failure is explicit, never fabricated);
- recommended actions are bounded enum values - the agent cannot execute
  anything, only recommend;
- deterministic fallback: when no LLM is configured (LLM_PROVIDER=fake or
  unset), a transparent rule-based report is produced from the evidence.
"""

import json
import logging
from typing import Any

from domain.report import (
    AgentOutcome,
    Finding,
    InvestigationReport,
    RecommendedAction,
    ReportRiskLevel,
    Typology,
)
from infrastructure.llm.base import LLMProvider
from infrastructure.llm.factory import get_llm_provider
from pydantic import ValidationError

logger = logging.getLogger(__name__)

AGENT_VERSION = "agent-v1"
MAX_REPAIR_ATTEMPTS = 1


def build_system_prompt() -> str:
    """System prompt: investigator role, hard output rules."""
    return (
        "You are an AML/fraud investigation analyst. You receive a JSON "
        "investigation snapshot (transaction facts, history, graph signals, "
        "risk signals) collected by a deterministic orchestrator.\n"
        "Rules:\n"
        "1. Use ONLY the provided snapshot. Do not invent facts.\n"
        "2. Every finding MUST reference at least one evidence_id from the "
        "snapshot's evidence list.\n"
        "3. Describe graph entries (SHARED_DEVICE, SHARED_IP, PASS_THROUGH) as "
        "structural signals; never state that fraud is confirmed.\n"
        "4. risk_score values with source=MOCK are rule-based mock signals, "
        "not model predictions - preserve that labeling.\n"
        "5. Respond with a single JSON object only, matching exactly:\n"
        '{"risk_level": "LOW|MEDIUM|HIGH", "summary": str, '
        '"typologies": [str], "findings": [{"finding": str, '
        '"evidence_ids": [str], "confidence": 0..1}], '
        '"recommended_action": "HUMAN_REVIEW|ESCALATE_TO_FIU|'
        'REQUEST_CUSTOMER_INFO|MONITOR|CLOSE_NO_ACTION", "confidence": 0..1}\n'
        "No prose outside the JSON."
    )


def build_user_prompt(state_dict: dict[str, Any]) -> str:
    """Compact user prompt embedding the evidence and key context."""
    evidence = [
        {
            "evidence_id": item["evidence_id"],
            "category": item["category"],
            "reference": item["reference"],
            "description": item["description"],
        }
        for item in state_dict.get("evidence", [])
    ]
    risk = state_dict.get("risk_score") or {}
    txn = state_dict.get("transaction") or {}
    graph = state_dict.get("fraud_ring_signals") or {}
    payload = {
        "transaction_id": state_dict.get("transaction_id"),
        "transaction": {
            "amount": txn.get("amount"),
            "currency": txn.get("currency"),
            "transaction_type": txn.get("transaction_type"),
            "is_new_device": txn.get("is_new_device"),
            "is_new_ip": txn.get("is_new_ip"),
        },
        "risk_score": {
            "risk_score": risk.get("risk_score"),
            "risk_level": risk.get("risk_level"),
            "source": risk.get("source"),
            "seeded_alert": risk.get("seeded_alert"),
        },
        "fraud_ring_signals": graph.get("signals", []),
        "shared_devices": (state_dict.get("shared_devices") or {}).get("shared_devices", []),
        "shared_ips": (state_dict.get("shared_ips") or {}).get("shared_ips", []),
        "evidence": evidence,
    }
    return json.dumps(payload, default=str)


def _rule_based_fallback(
    state_dict: dict[str, Any],
) -> dict[str, Any]:
    """Transparent rule-based report (no LLM) from the snapshot alone.

    Used when the provider is the no-network fake: the output remains a
    deterministic function of the collected evidence.
    """
    evidence = state_dict.get("evidence", [])
    ids = [item["evidence_id"] for item in evidence]
    by_category: dict[str, list[str]] = {}
    for item in evidence:
        by_category.setdefault(item["category"], []).append(item["evidence_id"])

    findings: list[dict[str, Any]] = []
    txn = state_dict.get("transaction") or {}
    if ids:
        findings.append(
            {
                "finding": (
                    f"Transaction {state_dict.get('transaction_id')} of "
                    f"{txn.get('amount')} {txn.get('currency')} "
                    f"({txn.get('transaction_type')}) reviewed against collected evidence."
                ),
                "evidence_ids": [ids[0]],
                "confidence": 0.99,
                "category": "TRANSACTION",
            }
        )
    graph_signals = (state_dict.get("fraud_ring_signals") or {}).get("signals", [])
    if graph_signals:
        signal = graph_signals[0]
        graph_evidence = by_category.get("GRAPH", ids)
        findings.append(
            {
                "finding": (
                    f"Structural signal observed: {signal['type']} involving "
                    f"{signal['entity_id']} (evidence, not a verdict)."
                ),
                "evidence_ids": [graph_evidence[0]],
                "confidence": 0.8,
                "category": "GRAPH",
            }
        )
    risk = state_dict.get("risk_score") or {}
    if risk.get("source") == "MOCK":
        risk_evidence = by_category.get("RISK", ids)
        findings.append(
            {
                "finding": (
                    f"Mock rule-based risk score {risk.get('risk_score')} "
                    f"({risk.get('risk_level')}); source=MOCK, not an ML model."
                ),
                "evidence_ids": [risk_evidence[0]],
                "confidence": 0.9,
                "category": "RISK",
            }
        )
    if not findings:
        findings.append(
            {
                "finding": "No evidence collected; insufficient basis for findings.",
                "evidence_ids": ["EV-000"],
                "confidence": 0.1,
                "category": None,
            }
        )

    recommended = (
        RecommendedAction.HUMAN_REVIEW
        if (risk or {}).get("risk_level") == "HIGH" or graph_signals
        else RecommendedAction.MONITOR
    )
    return {
        "risk_level": (risk or {}).get("risk_level", "MEDIUM"),
        "summary": (
            f"Deterministic rule-based report for {state_dict.get('transaction_id')} "
            f"from {len(evidence)} evidence items (LLM_PROVIDER=fake; no LLM call)."
        ),
        "typologies": (["MULE_ACCOUNT", "FRAUD_RING"] if graph_signals else []),
        "findings": findings,
        "recommended_action": recommended.value,
        "confidence": 0.75,
    }


def _extract_json(content: str) -> dict[str, Any]:
    """Parse the first JSON object found in the LLM reply."""
    text = content.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def _validate_report(
    raw: dict[str, Any],
    state_dict: dict[str, Any],
    provider: str,
    model: str,
) -> InvestigationReport:
    """Validate with evidence referential integrity enforced via context."""
    valid_ids = {item["evidence_id"] for item in state_dict.get("evidence", [])}
    findings = [
        Finding.model_validate(f, context={"valid_evidence_ids": valid_ids})
        for f in raw.get("findings", [])
    ]
    if not findings:
        raise ValueError("report contains no findings")
    report = InvestigationReport(
        investigation_id=state_dict.get("investigation_id", ""),
        transaction_id=state_dict.get("transaction_id", ""),
        risk_level=ReportRiskLevel(raw.get("risk_level", "MEDIUM")),
        summary=raw.get("summary", ""),
        typologies=[Typology(t) for t in raw.get("typologies", []) if t in Typology.__members__],
        findings=findings,
        recommended_action=RecommendedAction(raw.get("recommended_action", "HUMAN_REVIEW")),
        confidence=raw.get("confidence", 0.5),
        provenance={
            "llm_provider": provider,
            "llm_model": model,
            "agent_version": AGENT_VERSION,
            "risk_source": (state_dict.get("risk_score") or {}).get("source"),
            "risk_model_version": (state_dict.get("risk_score") or {}).get("model_version"),
        },
    )
    return report


async def run_agent(
    state_dict: dict[str, Any],
    *,
    provider: LLMProvider | None = None,
) -> AgentOutcome:
    """Produce a validated report from the investigation snapshot.

    With the fake provider (or unset LLM_PROVIDER) this path is fully
    deterministic. With a real provider, invalid or unsupported output is
    retried once via a repair prompt and otherwise surfaces as an explicit
    error - findings are never fabricated to satisfy the schema.
    """
    provider = provider or get_llm_provider()
    evidence = state_dict.get("evidence", [])

    if provider.name == "fake":
        raw = _rule_based_fallback(state_dict)
        report = _validate_report(raw, state_dict, provider.name, provider.model)
        return AgentOutcome(report=report, evidence_count=len(evidence), invalid_references=[])

    system = build_system_prompt()
    user = build_user_prompt(state_dict)
    response = await provider.complete(system, user)

    invalid: list[str] = []
    try:
        raw = _extract_json(response.content)
        report = _validate_report(raw, state_dict, response.provider, response.model)
        return AgentOutcome(report=report, evidence_count=len(evidence), invalid_references=invalid)
    except (ValueError, ValidationError, TypeError) as exc:
        logger.warning("agent output invalid (%s); repair pass", type(exc).__name__)
        invalid = [str(exc)]

    repair_user = (
        f"{user}\n\nYour previous reply was invalid: {invalid[0]}\n"
        "Return corrected JSON following the same rules. Reference ONLY "
        "evidence_ids from the snapshot."
    )
    response = await provider.complete(system, repair_user)
    try:
        raw = _extract_json(response.content)
        report = _validate_report(raw, state_dict, response.provider, response.model)
        return AgentOutcome(
            report=report,
            evidence_count=len(evidence),
            invalid_references=invalid,
        )
    except (ValueError, ValidationError, TypeError) as exc:
        raise RuntimeError(
            f"Agent could not produce a valid evidence-referenced report: {exc}"
        ) from exc
