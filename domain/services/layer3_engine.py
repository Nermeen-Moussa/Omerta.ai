"""Layer 3 - Real-time ML scoring engine (from the system design notes).

Pipeline:  transfer context -> 19 FraudGuard features -> composite risk score
(Rules 0.30 + XGBoost 0.45 + Isolation Forest 0.25) -> fraud typology
(SCAM / THIRD_PARTY / FIRST_PARTY) -> tier -> action:

    LOW    0-30   -> ALLOW
    MEDIUM 31-70  -> STEP_UP   (2FA / biometric friction; pass = allow, fail = block + escalate)
    HIGH   71-100 -> BLOCK_ESCALATE (investigation queue / Layer 4)

Pure logic, no DB or web imports, so it is unit-testable in isolation. The model
produces a risk SIGNAL; enforcement of BLOCK is a policy decision made here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from infrastructure.risk.fraudguard import NEUTRAL_DEFAULTS

logger = logging.getLogger(__name__)

LOW_MAX = 30.0
MEDIUM_MAX = 70.0

ALLOW = "ALLOW"
STEP_UP = "STEP_UP"
BLOCK_ESCALATE = "BLOCK_ESCALATE"

SCAM = "SCAM"
THIRD_PARTY = "THIRD_PARTY_FRAUD"
FIRST_PARTY = "FIRST_PARTY_FRIENDLY_FRAUD"
UNCLASSIFIED = "UNCLASSIFIED"


@dataclass
class TransferRiskContext:
    """Everything known about one transfer at decision time (best-effort)."""

    amount: float
    currency: str = "EGP"
    hist_count: int = 0
    hist_avg: float | None = None
    hist_max: float | None = None
    hist_std: float | None = None
    txn_count_5min: int = 0
    txn_count_1hour: int = 0
    is_new_device: bool = False
    is_new_country: bool = False
    is_unusual_hour: bool = False
    device_customer_count: int = 1
    is_vpn: bool = False
    impossible_travel: bool = False
    is_new_beneficiary: bool = False
    recipient_account_age_days: float = 999.0  # proxy for FraudGuard "merchant_age_days"
    # FraudGuard was trained on MERCHANT age. A young P2P recipient account is not the same thing
    # (in demo/test data every account is days old), so by default the age is used for typology
    # only and NOT fed to the model. Enable via settings.layer3_use_recipient_age.
    use_recipient_age_feature: bool = False
    recipient_flagged: bool = False
    min_since_device_registered: float = 100000.0
    min_since_password_change: float = 100000.0
    previous_alert_count: int = 0


@dataclass
class Layer3Decision:
    score: float
    tier: str
    action: str
    typology: str
    typology_reasons: list[str] = field(default_factory=list)
    reasons: list[dict[str, Any]] = field(default_factory=list)
    components: dict[str, Any] = field(default_factory=dict)
    source: str = "FRAUDGUARD"  # or RULES_ONLY when the ML artifacts were unavailable

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score, "tier": self.tier, "action": self.action,
            "typology": self.typology, "typology_reasons": self.typology_reasons,
            "reasons": self.reasons, "components": self.components, "source": self.source,
        }


class Scorer(Protocol):
    def score(self, features: dict[str, float]) -> dict[str, Any]: ...


def tier_for(score: float) -> str:
    if score <= LOW_MAX:
        return "LOW"
    if score <= MEDIUM_MAX:
        return "MEDIUM"
    return "HIGH"


def action_for(tier: str) -> str:
    return {"LOW": ALLOW, "MEDIUM": STEP_UP}.get(tier, BLOCK_ESCALATE)


def build_features(ctx: TransferRiskContext) -> dict[str, float]:
    """Map the transfer context onto FraudGuard's 19 features."""
    d = dict(NEUTRAL_DEFAULTS)
    avg = ctx.hist_avg if ctx.hist_avg and ctx.hist_avg > 0 else None
    mx = ctx.hist_max if ctx.hist_max and ctx.hist_max > 0 else None
    if avg:
        d["amount_to_avg_ratio"] = ctx.amount / avg
    if mx:
        d["amount_to_max_ratio"] = ctx.amount / mx
    if avg and ctx.hist_std and ctx.hist_std > 0:
        d["amount_zscore"] = max(-20.0, min(20.0, (ctx.amount - avg) / ctx.hist_std))
    d.update(
        amount=ctx.amount,
        is_new_device=int(ctx.is_new_device),
        is_new_country=int(ctx.is_new_country or ctx.impossible_travel),
        txn_count_5min=ctx.txn_count_5min,
        txn_count_1hour=ctx.txn_count_1hour,
        is_unusual_hour=int(ctx.is_unusual_hour),
        device_customer_count=ctx.device_customer_count,
        is_flagged=int(ctx.recipient_flagged),
        merchant_age_days=(
            ctx.recipient_account_age_days if ctx.use_recipient_age_feature else NEUTRAL_DEFAULTS["merchant_age_days"]
        ),
        min_since_password_change=ctx.min_since_password_change,
        min_since_beneficiary_added=0.0 if ctx.is_new_beneficiary else 100000.0,
        min_since_device_registered=ctx.min_since_device_registered,
        is_vpn=int(ctx.is_vpn),
        hist_count=ctx.hist_count,
    )
    return d


def classify_typology(ctx: TransferRiskContext, f: dict[str, float]) -> tuple[str, list[str]]:
    """Heuristic typology (explainable, not a learned classifier).

    THIRD_PARTY  account takeover: the session itself looks wrong (new device /
                 country / VPN / impossible travel / just-registered device).
    SCAM         authorised-push-payment: session looks like the customer, but a new
                 beneficiary + out-of-pattern amount or a new/flagged recipient.
    FIRST_PARTY  "friendly fraud": familiar session and beneficiary but a history of
                 prior alerts/disputes.
    """
    takeover = []
    if ctx.is_new_device:
        takeover.append("new device")
    if ctx.is_new_country:
        takeover.append("new country")
    if ctx.is_vpn:
        takeover.append("VPN/proxy session")
    if ctx.impossible_travel:
        takeover.append("impossible travel")
    if ctx.min_since_device_registered <= 30:
        takeover.append("device registered <30 min ago")
    if ctx.min_since_password_change <= 30:
        takeover.append("password changed <30 min ago")
    if len(takeover) >= 2 or ctx.impossible_travel:
        return THIRD_PARTY, takeover

    scam = []
    if ctx.is_new_beneficiary:
        scam.append("first transfer to this beneficiary")
    if f["amount_to_avg_ratio"] >= 8:
        scam.append(f"amount {f['amount_to_avg_ratio']:.0f}x the customer's average")
    if ctx.recipient_account_age_days <= 7:
        scam.append("recipient account is under 7 days old")
    if ctx.recipient_flagged:
        scam.append("recipient already flagged high-risk")
    if ctx.is_new_beneficiary and len(scam) >= 2:
        return SCAM, scam
    if ctx.recipient_flagged and len(scam) >= 2:
        return SCAM, scam

    if ctx.previous_alert_count >= 2 and not takeover:
        return FIRST_PARTY, [f"{ctx.previous_alert_count} prior alerts on a familiar session"]

    return UNCLASSIFIED, takeover or scam


def _rules_only(features: dict[str, float]) -> dict[str, Any]:
    import pandas as pd

    from infrastructure.risk.fraudguard.rule_engine import score_row

    rule_score, reasons = score_row(pd.Series(features))
    return {
        "final_score": float(rule_score), "rule_score": int(rule_score),
        "reasons": [{"points": p, "reason": r} for p, r in sorted(reasons, reverse=True)],
    }


def assess(ctx: TransferRiskContext, scorer: Scorer | None = None) -> Layer3Decision:
    """Run Layer 3 for one transfer. Never raises: falls back to rules-only scoring."""
    features = build_features(ctx)
    source = "FRAUDGUARD"
    try:
        if scorer is None:
            from infrastructure.risk.fraudguard.scorer import get_scorer

            scorer = get_scorer()
        result = scorer.score(features)
    except Exception as exc:  # artifacts missing / xgboost absent / pickle mismatch
        logger.warning("layer3_fallback_rules_only: %s", exc)
        result = _rules_only(features)
        source = "RULES_ONLY"

    score = float(result["final_score"])
    reasons = list(result.get("reasons", []))
    typology, typ_reasons = classify_typology(ctx, features)

    if ctx.impossible_travel and score <= MEDIUM_MAX:
        score = MEDIUM_MAX + 1  # hard policy floor: impossible travel is always HIGH
        reasons.append({"points": 0, "reason": "Policy floor: impossible travel forces HIGH tier"})

    tier = tier_for(score)
    components = {k: result[k] for k in
                  ("rule_score", "ml_score", "fraud_probability", "anomaly_score", "isolation_forest_flag")
                  if k in result}
    return Layer3Decision(
        score=round(score, 2), tier=tier, action=action_for(tier), typology=typology,
        typology_reasons=typ_reasons, reasons=reasons, components=components, source=source,
    )
