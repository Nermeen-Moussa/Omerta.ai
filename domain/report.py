"""Investigation report schemas (Phase 9).

The Investigator Agent's reasoning output: findings and typologies that MUST
reference evidence ids collected by the Phase 8 orchestrator, a recommended
action, and explicit provenance. Pydantic validation enforces evidence
referential integrity, so an unsupported claim cannot be serialized.

The recommended action is a bounded enum; the agent can only *recommend*.
Executing high-impact actions (freeze, SAR) remains behind deterministic
application logic and human approval.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, model_validator


class ReportRiskLevel(StrEnum):
    """Controlled risk levels for the final report."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Typology(StrEnum):
    """AML/fraud typologies the agent may hypothesize (evidence-backed only)."""

    MULE_ACCOUNT = "MULE_ACCOUNT"
    FRAUD_RING = "FRAUD_RING"
    LAYERING = "LAYERING"
    SMURFING = "SMURFING"
    ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER"
    NEW_DEVICE_ABUSE = "NEW_DEVICE_ABUSE"


class RecommendedAction(StrEnum):
    """Bounded recommendations. The agent cannot execute any of them."""

    HUMAN_REVIEW = "HUMAN_REVIEW"
    ESCALATE_TO_FIU = "ESCALATE_TO_FIU"
    REQUEST_CUSTOMER_INFO = "REQUEST_CUSTOMER_INFO"
    MONITOR = "MONITOR"
    CLOSE_NO_ACTION = "CLOSE_NO_ACTION"


class Finding(BaseModel):
    """One investigation finding backed by evidence ids from the state."""

    finding: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    category: str | None = None  # EvidenceCategory value when known

    @model_validator(mode="after")
    def _evidence_ids_must_exist(self, info: ValidationInfo) -> "Finding":
        """Referential integrity via validation context (valid id set).

        The agent node passes ``context={"valid_evidence_ids": {...}}``;
        direct construction without context skips the check (used by tests).
        """
        context = info.context or {}
        valid = context.get("valid_evidence_ids")
        if valid is not None:
            unknown = sorted(set(self.evidence_ids) - set(valid))
            if unknown:
                raise ValueError(f"finding references unknown evidence ids: {unknown}")
        return self


class InvestigationReport(BaseModel):
    """Structured investigation report produced by the agent node."""

    investigation_id: str
    transaction_id: str
    risk_level: ReportRiskLevel
    summary: str = Field(min_length=1, max_length=4000)
    typologies: list[Typology] = Field(default_factory=list)
    findings: list[Finding] = Field(min_length=1)
    recommended_action: RecommendedAction
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime | None = None


class AgentOutcome(BaseModel):
    """Result of the agent node: report plus integrity diagnostics."""

    report: InvestigationReport
    evidence_count: int
    invalid_references: list[str] = Field(default_factory=list)
