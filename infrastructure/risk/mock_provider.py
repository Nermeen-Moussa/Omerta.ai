"""Risk providers: the seam where the future ML engine will plug in.

``RiskProvider`` is the stable interface (Protocol). ``MockRiskProvider`` is
the Phase 7 implementation: deterministic rule-based contributions over
PostgreSQL facts, explicitly labeled ``source = MOCK`` and
``model_version = mock-risk-v1``. A future ``MLModelRiskProvider`` returns the
same schema with different values - no MCP or agent changes required.

This is NOT a trained fraud model. No ML library is used anywhere here.
"""

from typing import Protocol

from domain import schemas

# --- Deterministic mock contributions (documented in one place) -------------
# Weights are illustrative interface values, NOT learned model parameters.
MOCK_WEIGHTS: dict[str, float] = {
    "is_new_device": 0.20,
    "is_new_ip": 0.15,
    "transaction_amount": 0.25,
    "previous_suspicious_activity": 0.20,
    "transaction_velocity_7d": 0.10,
    "recipient_risk_level": 0.10,
}

MOCK_SOURCE = "MOCK"
MOCK_MODEL_VERSION = "mock-risk-v1"

# Risk-level thresholds (single source of truth, documented in README).
HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.40

# Amount threshold for the mock "high amount" contribution.
HIGH_AMOUNT_USD = 5000.0
# Velocity considered elevated by the mock rules.
ELEVATED_VELOCITY_7D = 5


def risk_level_for_score(score: float) -> str:
    """Map a score to the controlled LOW/MEDIUM/HIGH set."""
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


class RiskProvider(Protocol):
    """Stable contract for risk scoring - mock now, ML later."""

    source: str
    model_version: str

    async def score(self, features: schemas.RiskFeatures) -> schemas.RiskScoreOut:
        """Score one transaction from its extracted features."""
        ...  # pragma: no cover - interface definition


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class MockRiskProvider:
    """Deterministic rule-based provider over PostgreSQL-derived features.

    Every output is labeled ``source = MOCK`` / ``model_version =
    mock-risk-v1``. Same input features always produce the same score.
    """

    source = MOCK_SOURCE
    model_version = MOCK_MODEL_VERSION

    async def score(self, features: schemas.RiskFeatures) -> schemas.RiskScoreOut:
        contributions: dict[str, float] = {}

        if features.is_new_device:
            contributions["is_new_device"] = MOCK_WEIGHTS["is_new_device"]
        if features.is_new_ip:
            contributions["is_new_ip"] = MOCK_WEIGHTS["is_new_ip"]

        if features.currency == "USD" and float(features.transaction_amount) >= HIGH_AMOUNT_USD:
            contributions["transaction_amount"] = MOCK_WEIGHTS["transaction_amount"]

        if features.previous_suspicious_activity:
            contributions["previous_suspicious_activity"] = MOCK_WEIGHTS[
                "previous_suspicious_activity"
            ]

        if features.transaction_velocity_7d >= ELEVATED_VELOCITY_7D:
            contributions["transaction_velocity_7d"] = MOCK_WEIGHTS["transaction_velocity_7d"]

        if features.recipient_risk_level == "HIGH":
            contributions["recipient_risk_level"] = MOCK_WEIGHTS["recipient_risk_level"]

        raw_score = sum(contributions.values())
        score = round(_clamp01(raw_score), 4)

        return schemas.RiskScoreOut(
            transaction_id=features.transaction_id,
            risk_score=score,
            risk_level=risk_level_for_score(score),
            source=self.source,
            model_version=self.model_version,
            contributions=contributions,
        )


def get_provider() -> RiskProvider:
    """Return the configured provider (``RISK_PROVIDER=mock|ml``).

    ``mock`` (default) keeps every test and demo deterministic. ``ml`` loads
    the trained LightGBM artifact (Phase 14) through the same contract - the
    Risk MCP, agent, API, and evidence pipeline cannot tell the difference
    apart from the explicit source/model_version provenance.
    """
    from infrastructure.config import get_settings

    provider_name = (get_settings().risk_provider or "mock").lower()
    if provider_name == "ml":
        from infrastructure.risk.ml_provider import MLRiskProvider

        return MLRiskProvider()
    if provider_name != "mock":
        raise ValueError(f"Unknown RISK_PROVIDER '{provider_name}'; expected 'mock' or 'ml'.")
    return MockRiskProvider()
