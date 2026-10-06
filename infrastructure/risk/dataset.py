"""Synthetic demo dataset for the risk engine (Phase 14).

HONESTY NOTE (binding): the Omerta.ai seed contains ~7 transactions - far too
few for training. This module therefore generates a clearly-labeled SYNTHETIC
demo dataset from documented rules with a seeded PRNG, so the ML pipeline is
reproducible and the model has something real to learn from *within the
simulation*. Scores/labels describe the synthetic world only; they are NOT
real-world fraud statistics and must never be presented as such.
"""

import numpy as np

# Feature ranges mirror the RiskFeatures space (documented assumptions):
# - amounts log-normal around ~$2k, long tail to ~$50k;
# - velocities 0..30 per 7d; account ages 30..3600d;
# - ~25% of rows have prior alerts (correlates with fraud); etc.
N_ROWS = 20000
N_FRAUD = 3500  # ~17.5% positive class: hard but learnable
RANDOM_SEED = 20260928

FEATURES_FROM_AMOUNT = ("transaction_amount",)
FEATURE_COLUMNS: tuple[str, ...] = (
    "transaction_id",
    "transaction_amount",
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
    "label",
)


def _sample_features(rng: np.random.Generator, n: int) -> dict[str, np.ndarray]:
    return {
        "transaction_amount": rng.lognormal(mean=7.6, sigma=1.1, size=n),
        "is_usd": (rng.random(n) < 0.6).astype(int),
        "transaction_velocity_7d": rng.integers(0, 31, size=n),
        "account_age_days": rng.integers(30, 3601, size=n),
        "recipient_age_days": rng.integers(30, 3601, size=n),
        "originator_risk_high": (rng.random(n) < 0.15).astype(int),
        "originator_risk_medium": ((rng.random(n) >= 0.15) & (rng.random(n) < 0.35)).astype(int),
        "recipient_risk_high": (rng.random(n) < 0.12).astype(int),
        "recipient_risk_medium": ((rng.random(n) >= 0.12) & (rng.random(n) < 0.32)).astype(int),
        "previous_alert_count": rng.choice(
            [0, 1, 2, 3, 5], size=n, p=[0.7, 0.15, 0.08, 0.04, 0.03]
        ),
        "previous_suspicious_activity": (rng.random(n) < 0.30).astype(int),
        "is_new_device": (rng.random(n) < 0.35).astype(int),
        "is_new_ip": (rng.random(n) < 0.35).astype(int),
    }


def _apply_fraud_correlations(data: dict[str, np.ndarray], idx: np.ndarray) -> None:
    """Push fraud rows toward the risky end of each feature (documented)."""
    n_fraud = len(idx)
    rng = np.random.default_rng(RANDOM_SEED + 1)
    data["transaction_amount"][idx] = rng.lognormal(8.9, 0.8, n_fraud)
    data["is_new_device"][idx] = (rng.random(n_fraud) < 0.85).astype(int)
    data["is_new_ip"][idx] = (rng.random(n_fraud) < 0.80).astype(int)
    data["previous_alert_count"][idx] = rng.choice(
        [1, 2, 3, 5], size=n_fraud, p=[0.3, 0.3, 0.25, 0.15]
    )
    data["previous_suspicious_activity"][idx] = (rng.random(n_fraud) < 0.75).astype(int)
    # Velocity deliberately carries NO fraud signal (fraud rows sample the
    # same 0..30 distribution as clean rows) so the model cannot lean on it;
    # young recipient accounts DO correlate with fraud (mule-style accounts),
    # matching the documented TXN-001 scenario facts.
    data["transaction_velocity_7d"][idx] = rng.integers(0, 31, size=n_fraud)
    data["recipient_age_days"][idx] = rng.integers(30, 400, size=n_fraud)
    data["originator_risk_high"][idx] = (rng.random(n_fraud) < 0.5).astype(int)
    data["recipient_risk_high"][idx] = (rng.random(n_fraud) < 0.45).astype(int)


def generate_dataset(
    n_rows: int = N_ROWS, n_fraud: int = N_FRAUD, seed: int = RANDOM_SEED
) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic synthetic dataset: (X, y).

    X columns follow FEATURE_COLUMNS minus id/label. Same seed -> same data.
    """
    rng = np.random.default_rng(seed)
    data = _sample_features(rng, n_rows)
    fraud_idx = rng.choice(n_rows, size=n_fraud, replace=False)
    _apply_fraud_correlations(data, fraud_idx)

    y = np.zeros(n_rows, dtype=int)
    y[fraud_idx] = 1

    X = np.column_stack(
        [
            np.log1p(np.clip(data["transaction_amount"], 0, None)),
            data["is_usd"],
            data["transaction_velocity_7d"],
            data["account_age_days"],
            data["recipient_age_days"],
            data["originator_risk_high"],
            data["originator_risk_medium"],
            data["recipient_risk_high"],
            data["recipient_risk_medium"],
            data["previous_alert_count"],
            data["previous_suspicious_activity"],
            data["is_new_device"],
            data["is_new_ip"],
        ]
    )
    return X, y
