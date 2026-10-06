"""Train + evaluate the Phase 14 risk model (deterministic, reproducible).

    uv run python scripts/train_risk_model.py

Generates the SYNTHETIC demo dataset (honestly labeled), performs a stratified
train/validation split, trains LightGBM, reports the full metric set, saves
the model artifact + metrics under models/, and runs the three seeded
scenarios through the resulting MLRiskProvider.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.risk.dataset import generate_dataset
from infrastructure.risk.features import FEATURE_VERSION, features_from_row
from infrastructure.risk.ml_provider import (
    MODEL_VERSION,
    MLRiskProvider,
    save_model,
    train_model,
)
from sklearn.model_selection import train_test_split


def main() -> int:
    print(f"training risk model: version={MODEL_VERSION} features={FEATURE_VERSION}")
    X, y = generate_dataset()
    print(f"dataset: n={len(y)} fraud={int(y.sum())} ({y.mean():.1%} positive)")

    X_train, X_valid, y_train, y_valid = train_test_split(
        X, y, test_size=0.25, random_state=20260928, stratify=y
    )
    print(f"split: train={len(y_train)} valid={len(y_valid)} (stratified)")

    model, metrics = train_model(X_train, y_train, X_valid, y_valid)
    save_model(model, metrics)

    print("metrics:")
    for key in (
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "pr_auc",
        "false_positive_rate",
        "false_negative_rate",
        "best_iteration",
    ):
        print(f"  {key}: {metrics[key]}")
    print(f"  confusion_matrix: {metrics['confusion_matrix']}")

    # Precision@K on the validation set (K = 100 highest scores).
    proba = model.predict_proba(X_valid)[:, 1]
    order = np.argsort(-proba)
    k = min(100, len(order))
    precision_at_k = float(y_valid[order[:k]].mean())
    print(f"  precision_at_{k}: {precision_at_k:.4f}")

    # Scenario smoke through the provider seam (features reconstructed from
    # the seeded DB would require the app engine; here we use representative
    # feature rows matching each scenario's documented profile).
    scenarios = {
        "TXN-001-like": {
            "transaction_amount": 8400.0,
            "is_usd": 1,
            "transaction_velocity_7d": 2,
            "account_age_days": 400,
            "recipient_age_days": 30,
            "originator_risk_high": 1,
            "originator_risk_medium": 0,
            "recipient_risk_high": 0,
            "recipient_risk_medium": 0,
            "previous_alert_count": 2,
            "previous_suspicious_activity": 1,
            "is_new_device": 1,
            "is_new_ip": 1,
        },
        "TXN-1006-like": {
            "transaction_amount": 4250.0,
            "is_usd": 1,
            "transaction_velocity_7d": 1,
            "account_age_days": 900,
            "recipient_age_days": 800,
            "originator_risk_high": 0,
            "originator_risk_medium": 1,
            "recipient_risk_high": 0,
            "recipient_risk_medium": 0,
            "previous_alert_count": 0,
            "previous_suspicious_activity": 0,
            "is_new_device": 0,
            "is_new_ip": 0,
        },
        "TXN-1001-like": {
            "transaction_amount": 125.0,
            "is_usd": 1,
            "transaction_velocity_7d": 1,
            "account_age_days": 1500,
            "recipient_age_days": 1400,
            "originator_risk_high": 0,
            "originator_risk_medium": 0,
            "recipient_risk_high": 0,
            "recipient_risk_medium": 0,
            "previous_alert_count": 0,
            "previous_suspicious_activity": 0,
            "is_new_device": 0,
            "is_new_ip": 0,
        },
    }
    print("scenario scoring (provider seam):")
    import asyncio

    provider = MLRiskProvider()
    for name, row in scenarios.items():
        features = features_from_row(row)
        result = asyncio.run(provider.score(features))
        print(
            f"  {name}: score={result.risk_score} level={result.risk_level} "
            f"top={sorted(result.contributions.items(), key=lambda kv: -kv[1])[:3]}"
        )

    print("MODEL TRAINING COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
