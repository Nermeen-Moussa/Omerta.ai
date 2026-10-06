"""Phase 14 - real ML risk engine tests.

Covers dataset determinism, leakage-prevention checks, reproducible training,
the MLRiskProvider contract (same interface as mock), provenance fields,
scenario behavior, and the full RiskService -> ML path with the default
factory remapped. The model artifact is committed and reproducible via
``scripts/train_risk_model.py``; all performance numbers describe the
SYNTHETIC demo dataset only.
"""

from pathlib import Path

import numpy as np
import pytest
from domain import schemas
from infrastructure.config import get_settings
from infrastructure.risk import dataset as dataset_module
from infrastructure.risk.features import (
    FEATURE_NAMES,
    FEATURE_VERSION,
    feature_row,
    features_from_row,
)
from infrastructure.risk.ml_provider import (
    METRICS_FILE,
    MODEL_FILE,
    MODEL_VERSION,
    MLRiskProvider,
    get_ml_provider,
)
from infrastructure.risk.mock_provider import MockRiskProvider, get_provider
from sqlalchemy.ext.asyncio import AsyncSession

# --------------------------------------------------------------------------- #
# Dataset (synthetic, honestly labeled)
# --------------------------------------------------------------------------- #


def test_dataset_is_deterministic() -> None:
    X1, y1 = dataset_module.generate_dataset(n_rows=500, n_fraud=80)
    X2, y2 = dataset_module.generate_dataset(n_rows=500, n_fraud=80)
    assert np.array_equal(X1, X2)
    assert np.array_equal(y1, y2)


def test_dataset_shape_and_balance() -> None:
    X, y = dataset_module.generate_dataset()
    assert X.shape == (20000, 13)
    assert len(FEATURE_NAMES) == 13
    assert int(y.sum()) == 3500  # documented positive rate


def test_no_duplicate_rows_across_classes_leakage_guard() -> None:
    """Identical feature vectors must not carry conflicting labels."""
    X, y = dataset_module.generate_dataset(n_rows=4000, n_fraud=600)
    seen: dict[tuple, int] = {}
    for row, label in zip(X, y, strict=True):
        key = tuple(row)
        if key in seen and seen[key] != label:
            pytest.fail("label leakage: identical features with conflicting labels")
        seen[key] = label


def test_feature_row_order_matches_contract() -> None:
    features = schemas.RiskFeatures(
        transaction_id="T",
        transaction_amount=1000,
        currency="USD",
        transaction_velocity_7d=3,
        account_age_days=100,
        recipient_age_days=200,
        originator_risk_level="HIGH",
        recipient_risk_level="LOW",
        previous_alert_count=1,
        previous_suspicious_activity=True,
        is_new_device=True,
        is_new_ip=False,
    )
    vector = feature_row(features)
    assert len(vector) == len(FEATURE_NAMES)
    assert vector[0] == pytest.approx(np.log1p(1000.0))
    assert vector[FEATURE_NAMES.index("is_new_device")] == 1.0
    assert vector[FEATURE_NAMES.index("is_new_ip")] == 0.0
    assert vector[FEATURE_NAMES.index("originator_risk_high")] == 1.0


def test_feature_roundtrip_between_paths() -> None:
    """features_from_row -> feature_row must preserve values (train == serve)."""
    row = {
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
    }
    features = features_from_row(row)
    vector = feature_row(features)
    assert vector[FEATURE_NAMES.index("transaction_amount_log1p")] == pytest.approx(
        np.log1p(8400.0)
    )
    assert vector[FEATURE_NAMES.index("previous_alert_count")] == 2.0
    assert vector[FEATURE_NAMES.index("is_new_device")] == 1.0


# --------------------------------------------------------------------------- #
# Training + metrics (committed artifact must reproduce these properties)
# --------------------------------------------------------------------------- #


def test_metrics_artifact_documents_required_metrics() -> None:
    import json

    assert METRICS_FILE.exists(), "run scripts/train_risk_model.py"
    metrics = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    for key in (
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "pr_auc",
        "false_positive_rate",
        "false_negative_rate",
        "confusion_matrix",
        "model_version",
        "feature_version",
    ):
        assert key in metrics
    # SYNTHETIC demo performance floor (honest scope: simulation only).
    assert metrics["roc_auc"] >= 0.95
    assert metrics["pr_auc"] >= 0.90
    assert metrics["feature_version"] == FEATURE_VERSION


@pytest.mark.asyncio
async def test_training_is_reproducible() -> None:
    from infrastructure.risk.ml_provider import train_model
    from sklearn.model_selection import train_test_split

    X, y = dataset_module.generate_dataset()
    X_tr, X_va, y_tr, y_va = train_test_split(
        X, y, test_size=0.25, random_state=20260928, stratify=y
    )
    model_a, metrics_a = train_model(X_tr, y_tr, X_va, y_va)
    model_b, metrics_b = train_model(X_tr, y_tr, X_va, y_va)
    assert metrics_a["roc_auc"] == metrics_b["roc_auc"]
    proba_a = model_a.predict_proba(X_va)[:, 1]
    proba_b = model_b.predict_proba(X_va)[:, 1]
    assert np.allclose(proba_a, proba_b)


# --------------------------------------------------------------------------- #
# MLRiskProvider contract
# --------------------------------------------------------------------------- #


def _features_001() -> schemas.RiskFeatures:
    return schemas.RiskFeatures(
        transaction_id="TXN-001",
        transaction_amount=8400,
        currency="USD",
        transaction_velocity_7d=2,
        account_age_days=400,
        recipient_age_days=30,
        originator_risk_level="HIGH",
        recipient_risk_level="HIGH",
        previous_alert_count=2,
        previous_suspicious_activity=True,
        is_new_device=True,
        is_new_ip=True,
    )


def _features_clean() -> schemas.RiskFeatures:
    return schemas.RiskFeatures(
        transaction_id="TXN-1001",
        transaction_amount=125,
        currency="USD",
        transaction_velocity_7d=1,
        account_age_days=1500,
        recipient_age_days=1400,
        originator_risk_level="LOW",
        recipient_risk_level="LOW",
        previous_alert_count=0,
        previous_suspicious_activity=False,
        is_new_device=False,
        is_new_ip=False,
    )


@pytest.mark.asyncio
async def test_ml_provider_high_risk_scenario() -> None:
    provider = get_ml_provider()
    result = await provider.score(_features_001())
    assert 0.0 <= result.risk_score <= 1.0
    assert result.risk_level == "HIGH"
    assert result.source == "ML"
    assert result.model_version == MODEL_VERSION
    assert result.contributions  # feature provenance present
    assert set(result.contributions) <= set(FEATURE_NAMES)


@pytest.mark.asyncio
async def test_ml_provider_clean_scenario_low() -> None:
    provider = get_ml_provider()
    result = await provider.score(_features_clean())
    assert result.risk_level == "LOW"
    assert result.risk_score < 0.30


@pytest.mark.asyncio
async def test_ml_provider_deterministic_for_fixed_artifact() -> None:
    provider = get_ml_provider()
    first = await provider.score(_features_001())
    second = await provider.score(_features_001())
    assert first == second


def test_ml_provider_artifact_exists_and_loads() -> None:
    assert MODEL_FILE.exists()
    provider = MLRiskProvider()
    assert provider.source == "ML"
    # Textual "feature_importance" mis-parse guard: names must match contract.
    assert all(isinstance(v, float) for v in provider._importance.values())


@pytest.mark.asyncio
async def test_ml_provider_missing_artifact_fails_clearly() -> None:
    with pytest.raises(FileNotFoundError, match="train_risk_model"):
        MLRiskProvider(model_path=Path("models/does_not_exist.json"))


def test_factory_maps_ml_and_rejects_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "risk_provider", "ml")
    assert isinstance(get_provider(), MLRiskProvider)
    monkeypatch.setattr(settings, "risk_provider", "bogus")
    with pytest.raises(ValueError, match="RISK_PROVIDER"):
        get_provider()
    monkeypatch.setattr(settings, "risk_provider", "mock")
    assert isinstance(get_provider(), MockRiskProvider)


# --------------------------------------------------------------------------- #
# Full service path: RiskService -> features -> ML (contract unchanged)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_risk_service_uses_ml_provider_end_to_end(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RISK_PROVIDER=ml flows through RiskService (the Risk MCP seam)."""
    from domain.services.risk_service import RiskService

    settings = get_settings()
    monkeypatch.setattr(settings, "risk_provider", "ml")
    service = RiskService(db_session)
    result = await service.get_risk_score("TXN-001")

    assert result.source == "ML"
    assert result.model_version == MODEL_VERSION
    assert 0.0 <= result.risk_score <= 1.0
    assert result.risk_level in {"LOW", "MEDIUM", "HIGH"}
    # Seeded alert stays a separate fact, untouched by the ML provider.
    assert result.seeded_alert is not None
    assert result.seeded_alert.alert_id == "ALERT-001"
    assert result.seeded_alert.risk_score == "0.87"


@pytest.mark.asyncio
async def test_mock_provider_still_default_and_deterministic() -> None:
    provider = get_provider()
    assert isinstance(provider, MockRiskProvider)
    base = {
        "transaction_id": "T",
        "transaction_amount": 8400,
        "currency": "USD",
        "transaction_velocity_7d": 2,
        "account_age_days": 400,
        "recipient_age_days": 30,
        "originator_risk_level": "HIGH",
        "recipient_risk_level": "HIGH",
        "previous_alert_count": 2,
        "previous_suspicious_activity": True,
        "is_new_device": True,
        "is_new_ip": True,
    }
    result = await provider.score(schemas.RiskFeatures(**base))
    assert result.source == "MOCK"
    assert result.model_version == "mock-risk-v1"
    assert result.risk_score == 0.9  # documented deterministic mock value
