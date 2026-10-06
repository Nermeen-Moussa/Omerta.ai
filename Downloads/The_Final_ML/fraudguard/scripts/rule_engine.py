"""
FraudGuard AI — Rule Engine
============================
Deterministic, explainable rule-based scorer. This is Layer 1 of the Risk
Engine (Rules + ML + Anomaly). Each rule adds points (0-100 scale) and
carries a human-readable reason string, mirroring the "explainability"
output shown in the system design doc (e.g. "+32 unusual amount").

This module has NO dependency on the ML models — it works purely off the
engineered features, so it stays auditable and fast (used as a first-pass
filter before the heavier ML/anomaly scoring runs).
"""

import pandas as pd


RULES = [
    # (condition_fn, points, reason)
    (lambda r: r["amount_to_avg_ratio"] >= 20, 30, "Amount is 20x+ the customer's historical average"),
    (lambda r: 8 <= r["amount_to_avg_ratio"] < 20, 18, "Amount is significantly above customer's historical average"),
    (lambda r: r["amount_zscore"] >= 5, 15, "Extreme statistical deviation from customer's spending pattern"),
    (lambda r: r["is_new_device"] == 1, 18, "Transaction from a device never seen for this customer"),
    (lambda r: r["is_new_country"] == 1, 15, "Transaction from a country not previously associated with the customer"),
    (lambda r: r["txn_count_1hour"] >= 8, 20, "Abnormal transaction velocity (8+ transactions in the last hour)"),
    (lambda r: r["txn_count_5min"] >= 3, 12, "Multiple transactions within a 5-minute window"),
    (lambda r: r["is_unusual_hour"] == 1, 8, "Transaction occurred outside the customer's usual active hours"),
    (lambda r: r["min_since_password_change"] <= 30, 25, "Password was changed within 30 minutes of this transaction"),
    (lambda r: r["min_since_beneficiary_added"] <= 30, 22, "A new beneficiary/recipient was added within 30 minutes"),
    (lambda r: r["min_since_device_registered"] <= 30, 15, "A new device was registered within 30 minutes"),
    (lambda r: r["device_customer_count"] >= 5, 20, "This device is linked to 5+ different customer accounts"),
    (lambda r: r["merchant_age_days"] <= 7, 12, "Merchant account was created less than 7 days ago"),
    (lambda r: r["chargeback_rate"] >= 0.10, 10, "Merchant has an abnormally high chargeback rate"),
    (lambda r: r["is_flagged"] == 1, 15, "Merchant is already flagged as high-risk"),
    (lambda r: r["is_vpn"] == 1, 6, "Transaction originated through a VPN/proxy"),
]


def score_row(row):
    total = 0
    reasons = []
    for cond, points, reason in RULES:
        try:
            if cond(row):
                total += points
                reasons.append((points, reason))
        except (KeyError, TypeError):
            continue
    return min(total, 100), reasons


def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    scores, reason_lists = [], []
    for _, row in df.iterrows():
        s, reasons = score_row(row)
        scores.append(s)
        reason_lists.append("; ".join(f"+{p} {r}" for p, r in sorted(reasons, reverse=True)))
    df = df.copy()
    df["rule_score"] = scores
    df["rule_reasons"] = reason_lists
    return df


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "../data"
    feats = pd.read_csv(f"{data_dir}/features.csv")
    scored = score_dataframe(feats)
    print(scored[["transaction_id", "is_fraud", "rule_score", "rule_reasons"]].sort_values(
        "rule_score", ascending=False).head(10).to_string(index=False))
