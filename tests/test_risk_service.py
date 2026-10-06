"""Risk service tests: deterministic MOCK outputs over PostgreSQL facts.

Runs against the isolated omerta_test database via the ``db_session`` fixture.
"""

from decimal import Decimal

import pytest
from domain.errors import NotFoundError
from domain.services.risk_service import RiskService
from infrastructure.risk.mock_provider import (
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    MOCK_MODEL_VERSION,
    MOCK_SOURCE,
    MockRiskProvider,
    risk_level_for_score,
)
from sqlalchemy.ext.asyncio import AsyncSession


async def test_get_risk_score_txn001_deterministic(db_session: AsyncSession) -> None:
    """Same input -> same output, with explicit MOCK provenance."""
    service = RiskService(db_session)
    first = await service.get_risk_score("TXN-001")
    second = await service.get_risk_score("TXN-001")

    assert first.risk_score == second.risk_score
    assert first.source == MOCK_SOURCE == "MOCK"
    assert first.model_version == MOCK_MODEL_VERSION == "mock-risk-v1"
    assert first.risk_level == "HIGH"
    # TXN-001 hits: new device, new IP, high amount, prior alert, HIGH recipient
    assert first.contributions == {
        "is_new_device": 0.20,
        "is_new_ip": 0.15,
        "transaction_amount": 0.25,
        "previous_suspicious_activity": 0.20,
        "recipient_risk_level": 0.10,
    }


async def test_get_risk_score_bounds(db_session: AsyncSession) -> None:
    service = RiskService(db_session)
    for external_id in ("TXN-001", "TXN-1001", "TXN-1004", "TXN-1006"):
        result = await service.get_risk_score(external_id)
        assert 0.0 <= result.risk_score <= 1.0


async def test_get_risk_score_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        await RiskService(db_session).get_risk_score("TXN-999")
    assert exc_info.value.payload == {
        "error": "NOT_FOUND",
        "resource": "transaction",
        "id": "TXN-999",
    }


async def test_seeded_alert_is_reported_separately(db_session: AsyncSession) -> None:
    """ALERT-001 (0.87) stays a stored fact, distinct from the mock score."""
    result = await RiskService(db_session).get_risk_score("TXN-001")

    assert result.seeded_alert is not None
    assert result.seeded_alert.alert_id == "ALERT-001"
    assert Decimal(result.seeded_alert.risk_score) == Decimal("0.87")
    assert result.seeded_alert.risk_level == "HIGH"
    assert "independent of the mock provider" in result.seeded_alert.note
    # The mock calculation itself is NOT presented as the alert value:
    assert result.risk_score != 0.87


async def test_get_risk_features_match_database_facts(db_session: AsyncSession) -> None:
    """Every feature traces to a seeded fact - no fabricated values."""
    result = await RiskService(db_session).get_risk_features("TXN-001")
    features = result.features

    assert result.source == "MOCK"
    assert features.transaction_amount == Decimal("8400.00")
    assert features.currency == "USD"
    assert features.is_new_device is True
    assert features.is_new_ip is True
    # Seed: ACC-1001 created 900 days ago, ACC-9001 created 30 days ago.
    assert features.account_age_days == 899
    assert features.recipient_age_days == 29
    # Velocity window [TXN-001 timestamp - 7d, timestamp] contains TXN-1003.
    assert features.transaction_velocity_7d == 2
    assert features.originator_risk_level == "HIGH"
    assert features.recipient_risk_level == "HIGH"
    assert features.previous_alert_count == 2  # ALERT-001 + ALERT-003 (on TXN-1001)
    assert features.previous_suspicious_activity is True


async def test_get_risk_features_clean_transaction(db_session: AsyncSession) -> None:
    """A small, old-device transaction produces low-risk mock features."""
    result = await RiskService(db_session).get_risk_features("TXN-1001")
    features = result.features

    assert features.is_new_device is False
    assert features.is_new_ip is False
    assert features.transaction_amount == Decimal("125.00")
    assert features.recipient_risk_level == "LOW"


async def test_get_risk_features_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await RiskService(db_session).get_risk_features("TXN-999")


async def test_get_feature_importance_schema_and_order(db_session: AsyncSession) -> None:
    result = await RiskService(db_session).get_feature_importance("TXN-001")

    assert result.source == "MOCK"
    assert result.model_version == "mock-risk-v1"
    assert "not produced by a trained model" in result.note
    assert result.top_features, "TXN-001 should have mock contributions"
    values = [f.importance for f in result.top_features]
    assert values == sorted(values, reverse=True)
    assert all(0.0 <= v <= 1.0 for v in values)
    # Highest mock contribution is the high amount for TXN-001.
    assert result.top_features[0].feature == "transaction_amount"


async def test_get_feature_importance_deterministic(db_session: AsyncSession) -> None:
    service = RiskService(db_session)
    first = await service.get_feature_importance("TXN-001")
    second = await service.get_feature_importance("TXN-001")
    assert first.top_features == second.top_features


async def test_get_feature_importance_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await RiskService(db_session).get_feature_importance("TXN-999")


async def test_get_previous_risk_events_for_acc1001(db_session: AsyncSession) -> None:
    """Stored alerts are returned as database facts (newest first)."""
    result = await RiskService(db_session).get_previous_risk_events("ACC-1001")

    assert result.account_id == "ACC-1001"
    assert result.count == 2
    event = result.events[0]  # ALERT-003 (recent baseline) sorts first
    assert event.transaction_id == "TXN-1001"
    assert event.alert_id == "ALERT-003"
    assert event.risk_score == "0.20"
    assert event.risk_level == "LOW"
    assert event.origin == "seeded_alert_row"
    alert_one = result.events[1]
    assert alert_one.alert_id == "ALERT-001"
    assert alert_one.risk_score == "0.87"


async def test_get_previous_risk_events_empty_is_valid(db_session: AsyncSession) -> None:
    """No fabricated history: ACC-9001 has no alerts -> empty structured result."""
    result = await RiskService(db_session).get_previous_risk_events("ACC-9001")

    assert result.count == 0
    assert result.events == []


async def test_get_previous_risk_events_nonexistent(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        await RiskService(db_session).get_previous_risk_events("ACC-999")
    assert exc_info.value.payload["resource"] == "account"


# --- Provider unit tests (no database) ------------------------------------- #


def test_risk_level_thresholds() -> None:
    assert risk_level_for_score(0.0) == "LOW"
    assert risk_level_for_score(MEDIUM_THRESHOLD) == "MEDIUM"
    assert risk_level_for_score(0.69) == "MEDIUM"
    assert risk_level_for_score(HIGH_THRESHOLD) == "HIGH"
    assert risk_level_for_score(1.0) == "HIGH"


@pytest.mark.parametrize(
    ("expected", "features_overrides"),
    [
        ("LOW", {}),
        (
            "HIGH",
            {
                "is_new_device": True,
                "is_new_ip": True,
                "previous_suspicious_activity": True,
                "transaction_amount": Decimal("6000.00"),
            },
        ),
    ],
)
def test_mock_provider_clamps_and_maps(expected: str, features_overrides: dict) -> None:
    """Baseline features without triggers map to LOW; adding ones raises it."""
    import asyncio

    from domain import schemas

    base = {
        "transaction_id": "TXN-TEST",
        "transaction_amount": Decimal("100.00"),
        "currency": "USD",
        "is_new_device": False,
        "is_new_ip": False,
        "transaction_velocity_7d": 1,
        "account_age_days": 365,
        "recipient_age_days": 365,
        "originator_risk_level": "LOW",
        "recipient_risk_level": "LOW",
        "previous_alert_count": 0,
        "previous_suspicious_activity": False,
    }
    base.update(features_overrides)
    features = schemas.RiskFeatures(**base)
    result = asyncio.run(MockRiskProvider().score(features))
    assert result.risk_level == expected
