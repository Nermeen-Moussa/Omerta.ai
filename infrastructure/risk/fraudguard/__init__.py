"""FraudGuard AI (Rules + XGBoost + Isolation Forest) vendored from The_Final_ML.

Scores a transaction 0-100 from 19 engineered features. Artifacts live in
``models/fraudguard/``; retrain with ``scripts/fraudguard/train_models.py``.
"""

FEATURE_COLUMNS: list[str] = [
    "amount", "amount_to_avg_ratio", "amount_to_max_ratio", "amount_zscore",
    "is_new_device", "is_new_country", "txn_count_5min", "txn_count_1hour",
    "is_unusual_hour", "device_customer_count", "chargeback_rate", "refund_rate",
    "is_flagged", "merchant_age_days", "min_since_password_change",
    "min_since_beneficiary_added", "min_since_device_registered", "is_vpn",
    "hist_count",
]

# Neutral "nothing suspicious known" defaults (same as the FraudGuard API schema).
NEUTRAL_DEFAULTS: dict[str, float] = {
    "amount_to_avg_ratio": 1.0, "amount_to_max_ratio": 1.0, "amount_zscore": 0.0,
    "is_new_device": 0, "is_new_country": 0, "txn_count_5min": 0, "txn_count_1hour": 0,
    "is_unusual_hour": 0, "device_customer_count": 1, "chargeback_rate": 0.0,
    "refund_rate": 0.0, "is_flagged": 0, "merchant_age_days": 999,
    "min_since_password_change": 100000, "min_since_beneficiary_added": 100000,
    "min_since_device_registered": 100000, "is_vpn": 0, "hist_count": 0,
}
