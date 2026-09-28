"""Feature engineering for the risk engine (Phase 14).

Single source of truth for the feature space: the same mapping turns a
``RiskFeatures`` snapshot (risk MCP / mock path) and a dataset row (training)
into the model's numeric vector. ``FEATURE_VERSION`` is bumped whenever the
mapping changes; every prediction records it.

Only features actually available on ``RiskFeatures`` are used - nothing is
fabricated. Missing/unknown categoricals map to explicit sentinel values.
"""

import math

from domain import schemas

FEATURE_VERSION = "features-v1"

# Ordered feature names (the model's contract; order must never change
# without retraining and bumping FEATURE_VERSION).
FEATURE_NAMES: tuple[str, ...] = (
    "transaction_amount_log1p",
    "is_usd",
    "transaction_velocity_7d",
    "account_age_days",
    "recipient_age_days",
    "originator_risk_high",
    "originator_risk_medium",
    "recipient_risk_high",
    "recipient_risk_medium",
    "previous_alert_count",
    "previous_suspicious_activity",
    "is_new_device",
    "is_new_ip",
)


def feature_row(features: schemas.RiskFeatures) -> list[float]:
    """Numeric feature vector in FEATURE_NAMES order (deterministic)."""
    amount = float(features.transaction_amount)
    return [
        math.log1p(max(amount, 0.0)),
        1.0 if features.currency == "USD" else 0.0,
        float(features.transaction_velocity_7d),
        float(features.account_age_days),
        float(features.recipient_age_days),
        1.0 if features.originator_risk_level == "HIGH" else 0.0,
        1.0 if features.originator_risk_level == "MEDIUM" else 0.0,
        1.0 if features.recipient_risk_level == "HIGH" else 0.0,
        1.0 if features.recipient_risk_level == "MEDIUM" else 0.0,
        float(features.previous_alert_count),
        1.0 if features.previous_suspicious_activity else 0.0,
        1.0 if features.is_new_device else 0.0,
        1.0 if features.is_new_ip else 0.0,
    ]


def features_from_row(row: dict[str, float]) -> schemas.RiskFeatures:
    """Rebuild a RiskFeatures from a raw dataset row dict (training path)."""
    amount = float(row["transaction_amount"])
    originator = (
        "HIGH"
        if row.get("originator_risk_high")
        else ("MEDIUM" if row.get("originator_risk_medium") else "LOW")
    )
    recipient = (
        "HIGH"
        if row.get("recipient_risk_high")
        else ("MEDIUM" if row.get("recipient_risk_medium") else "LOW")
    )
    return schemas.RiskFeatures(
        transaction_id=str(row.get("transaction_id", "TRAIN")),
        transaction_amount=amount,
        currency="USD" if row.get("is_usd") else "EUR",
        transaction_velocity_7d=int(row["transaction_velocity_7d"]),
        account_age_days=int(row["account_age_days"]),
        recipient_age_days=int(row["recipient_age_days"]),
        originator_risk_level=originator,
        recipient_risk_level=recipient,
        previous_alert_count=int(row.get("previous_alert_count", 0)),
        previous_suspicious_activity=bool(row.get("previous_suspicious_activity")),
        is_new_device=bool(row.get("is_new_device")),
        is_new_ip=bool(row.get("is_new_ip")),
    )
