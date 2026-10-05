"""Mock Risk Assessment Workflow & Parallel Analyzer Architecture Interfaces.

Implements the multi-stage risk evaluation pipeline:
1. Validates and evaluates transaction features.
2. Runs mock analyzers in parallel (Transaction, Device, IP, Graph).
3. Computes deterministic aggregated score on 0-100 scale.
4. Enforces the strict HUMAN_REVIEW rule: REQUIRES_REVIEW = score > 40.00.
5. Emits granular risk signals with severity, confidence, and evidence refs.
6. Automatically creates Alert and InvestigationCase for flagged transactions.
"""

from abc import ABC, abstractmethod
import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import logging
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import (
    Account,
    Alert,
    AuditEvent,
    Device,
    InvestigationCase,
    IPAddress,
    RiskAssessment,
    RiskSignal,
    Transaction,
)

logger = logging.getLogger(__name__)

# Configurable global review threshold
DEFAULT_HUMAN_REVIEW_THRESHOLD = 40.00


# --------------------------------------------------------------------------- #
# Future Parallel Risk Analyzer Interfaces
# --------------------------------------------------------------------------- #

class BaseRiskAnalyzer(ABC):
    """Abstract interface for parallel risk analysis modules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the analysis capability."""
        pass

    @abstractmethod
    async def analyze(self, transaction: Transaction, context: dict[str, Any]) -> list[dict[str, Any]]:
        """Run analysis and return list of detected risk signals."""
        pass


class TransactionRuleAnalyzer(BaseRiskAnalyzer):
    """Rule-based transactional anomaly detection."""

    @property
    def name(self) -> str:
        return "TRANSACTION_RULE"

    async def analyze(self, transaction: Transaction, context: dict[str, Any]) -> list[dict[str, Any]]:
        signals = []
        amt = float(transaction.amount)
        if amt >= 100000:
            signals.append({
                "signal_name": "Critical High-Value Wire",
                "severity": "CRITICAL",
                "description": f"Transfer amount of {amt:,.2f} {transaction.currency} exceeds 100k threshold.",
                "source": self.name,
                "confidence": Decimal("0.990"),
                "evidence_reference": f"amount:{transaction.amount}",
                "score_impact": 40.0,
            })
        elif amt >= 30000:
            signals.append({
                "signal_name": "Elevated Transaction Amount",
                "severity": "HIGH",
                "description": f"Transfer amount of {amt:,.2f} {transaction.currency} is significantly above typical account activity.",
                "source": self.name,
                "confidence": Decimal("0.950"),
                "evidence_reference": f"amount:{transaction.amount}",
                "score_impact": 25.0,
            })
        return signals


class DeviceIntelligenceAnalyzer(BaseRiskAnalyzer):
    """Device integrity and emulator detection."""

    @property
    def name(self) -> str:
        return "DEVICE_INTELLIGENCE"

    async def analyze(self, transaction: Transaction, context: dict[str, Any]) -> list[dict[str, Any]]:
        signals = []
        device: Device | None = context.get("device")
        if transaction.is_new_device:
            signals.append({
                "signal_name": "New Device for Account",
                "severity": "MEDIUM",
                "description": f"Transaction originated from an unrecognized device hardware identifier.",
                "source": self.name,
                "confidence": Decimal("0.920"),
                "evidence_reference": f"device:{transaction.device_id}",
                "score_impact": 18.0,
            })
        if device and (device.is_emulator or device.is_rooted):
            signals.append({
                "signal_name": "Virtualized / Rooted Device Environment",
                "severity": "HIGH",
                "description": f"Hardware telemetry indicates active emulator environment or root bypass tools.",
                "source": self.name,
                "confidence": Decimal("0.970"),
                "evidence_reference": f"device:{device.external_id}",
                "score_impact": 30.0,
            })
        return signals


class IPIntelligenceAnalyzer(BaseRiskAnalyzer):
    """Network, VPN, and Geolocation risk evaluation."""

    @property
    def name(self) -> str:
        return "IP_ANALYSIS"

    async def analyze(self, transaction: Transaction, context: dict[str, Any]) -> list[dict[str, Any]]:
        signals = []
        ip: IPAddress | None = context.get("ip_address")
        if transaction.is_new_ip:
            signals.append({
                "signal_name": "Unverified IP Observation",
                "severity": "LOW",
                "description": "Session connected through an IP address not previously associated with this customer.",
                "source": self.name,
                "confidence": Decimal("0.850"),
                "evidence_reference": f"ip:{ip.address if ip else 'unknown'}",
                "score_impact": 10.0,
            })
        if ip and ip.is_vpn:
            signals.append({
                "signal_name": "Suspected Commercial VPN / Proxy Endpoint",
                "severity": "HIGH",
                "description": f"Connection routed through known VPN or datacenter exit node in {ip.country}.",
                "source": self.name,
                "confidence": Decimal("0.960"),
                "evidence_reference": f"ip:{ip.address}",
                "score_impact": 25.0,
            })
        return signals


# --------------------------------------------------------------------------- #
# Mock Risk Assessment Engine
# --------------------------------------------------------------------------- #

class MockRiskAssessmentEngine:
    """Orchestrates parallel analysis and saves assessments."""

    def __init__(self, session: AsyncSession, threshold: float = DEFAULT_HUMAN_REVIEW_THRESHOLD):
        self.session = session
        self.threshold = threshold
        self.analyzers: list[BaseRiskAnalyzer] = [
            TransactionRuleAnalyzer(),
            DeviceIntelligenceAnalyzer(),
            IPIntelligenceAnalyzer(),
        ]

    async def evaluate_transaction(self, transaction_id: int) -> RiskAssessment:
        """Run parallel analysis and persist risk assessment with score and signals."""
        txn = await self.session.get(Transaction, transaction_id)
        if not txn:
            raise ValueError(f"Transaction id {transaction_id} not found")

        # Load context
        device = await self.session.get(Device, txn.device_id) if txn.device_id else None
        ip = await self.session.get(IPAddress, txn.ip_address_id) if txn.ip_address_id else None
        context = {"device": device, "ip_address": ip}

        # Run analyzers concurrently
        analyzer_tasks = [analyzer.analyze(txn, context) for analyzer in self.analyzers]
        analyzer_results = await asyncio.gather(*analyzer_tasks)

        all_signals: list[dict[str, Any]] = []
        base_score = 5.0
        for signal_list in analyzer_results:
            for sig in signal_list:
                all_signals.append(sig)
                base_score += sig.get("score_impact", 5.0)

        # Bound score between 1.00 and 99.00
        final_score = Decimal(str(round(max(1.0, min(99.0, base_score)), 2)))
        requires_review = float(final_score) > self.threshold

        if final_score < 20:
            risk_lvl = "LOW"
            rev_status = "NOT_REQUIRED"
        elif final_score < 40:
            risk_lvl = "MODERATE"
            rev_status = "NOT_REQUIRED"
        elif final_score < 70:
            risk_lvl = "REQUIRES_REVIEW"
            rev_status = "REQUIRES_REVIEW"
        elif final_score < 90:
            risk_lvl = "HIGH"
            rev_status = "REQUIRES_REVIEW"
        else:
            risk_lvl = "CRITICAL"
            rev_status = "REQUIRES_REVIEW"

        # Update transaction record
        txn.risk_score = final_score
        txn.risk_level = risk_lvl
        txn.review_status = rev_status

        # Create Risk Assessment
        assess_ext_id = f"ASSESS-{txn.external_id}-{uuid.uuid4().hex[:6]}"
        corr_id = f"CORR-{uuid.uuid4().hex[:12]}"
        assessment = RiskAssessment(
            external_id=assess_ext_id,
            transaction_id=txn.id,
            risk_score=final_score,
            risk_level=risk_lvl,
            requires_human_review=requires_review,
            status="COMPLETED",
            version="v1.0-engine",
            correlation_id=corr_id,
            summary=(
                f"Multi-signal assessment: overall score {final_score:.1f}% ({risk_lvl}). "
                f"Requires review: {requires_review} (threshold > {self.threshold}%)."
            ),
            assessed_at=datetime.now(UTC),
        )
        self.session.add(assessment)
        await self.session.flush()

        # Add signals
        for sig in all_signals:
            self.session.add(RiskSignal(
                assessment_id=assessment.id,
                signal_name=sig["signal_name"],
                severity=sig["severity"],
                description=sig["description"],
                source=sig["source"],
                confidence=sig["confidence"],
                evidence_reference=sig.get("evidence_reference"),
                detected_at=datetime.now(UTC),
            ))

        # If review required (score > 40%), create Alert & InvestigationCase
        if requires_review:
            alert_ext_id = f"ALERT-{uuid.uuid4().hex[:8].upper()}"
            alert = Alert(
                external_id=alert_ext_id,
                transaction_id=txn.id,
                alert_type="ELEVATED_RISK_TRIGGER",
                risk_score=final_score,
                risk_level=risk_lvl,
                status="OPEN",
            )
            self.session.add(alert)
            await self.session.flush()

            case_ext_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
            case = InvestigationCase(
                external_id=case_ext_id,
                alert_id=alert.id,
                transaction_id=txn.id,
                title=f"Review of {txn.external_id} ({risk_lvl} Risk)",
                status="NEW",
                severity=risk_lvl,
                report={
                    "summary": f"Transaction {txn.external_id} triggered human review queue with score {final_score:.1f}%.",
                    "risk_level": risk_lvl,
                    "confidence": 0.88,
                    "recommended_action": "HUMAN_REVIEW" if float(final_score) >= 70 else "REQUEST_CUSTOMER_INFO",
                },
            )
            self.session.add(case)
            await self.session.flush()

            self.session.add(AuditEvent(
                case_id=case.id,
                investigation_id=case.external_id,
                transaction_id=txn.external_id,
                event_type="AUTO_ALERT_TRIGGERED",
                actor_type="SYSTEM",
                actor_id="risk_engine",
                source="mock_risk_engine",
                metadata_={"risk_score": float(final_score), "threshold": self.threshold},
                event_id=f"EVT-{uuid.uuid4().hex[:12]}",
            ))

        await self.session.flush()
        return assessment
