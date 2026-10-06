"""Risk service: business layer between Risk MCP tools and the provider.

Responsibilities:
- validate inputs (same rules as Phases 5/6),
- extract features **strictly from PostgreSQL facts** (nothing fabricated),
- delegate scoring to the configured :class:`RiskProvider`,
- attach the seeded alert row as a separate provenance field when present,
- return typed, JSON-serializable schemas.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from infrastructure.database import repository as db_repository
from infrastructure.database.models import Transaction
from infrastructure.risk.mock_provider import get_provider
from sqlalchemy.ext.asyncio import AsyncSession

from domain import schemas
from domain.errors import NotFoundError
from domain.services.transaction_service import validate_external_id

VELOCITY_WINDOW_DAYS = 7


def _days_between(earlier: datetime, later: datetime) -> int:
    return max(0, (later - earlier).days)


async def _extract_features(session: AsyncSession, txn: Transaction) -> schemas.RiskFeatures:
    """Derive every feature from existing database facts (no fabrication)."""
    originator = txn.account
    recipient = txn.recipient_account

    velocity = await db_repository.count_transactions_in_window(
        session,
        originator.id,
        txn.timestamp - timedelta(days=VELOCITY_WINDOW_DAYS),
        txn.timestamp,
    )
    previous_alert_count = await db_repository.count_alerts_for_originator(session, originator.id)

    return schemas.RiskFeatures(
        transaction_id=txn.external_id,
        transaction_amount=txn.amount,
        currency=txn.currency,
        is_new_device=txn.is_new_device,
        is_new_ip=txn.is_new_ip,
        transaction_velocity_7d=velocity,
        account_age_days=_days_between(originator.created_at, txn.timestamp),
        recipient_age_days=_days_between(recipient.created_at, txn.timestamp),
        originator_risk_level=originator.risk_level,
        recipient_risk_level=recipient.risk_level,
        previous_alert_count=previous_alert_count,
        previous_suspicious_activity=previous_alert_count > 0,
    )


class RiskService:
    """Risk information retrieval (read-only) over the mock provider."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._provider = get_provider()

    # ------------------------------------------------------------------ #
    # get_risk_score
    # ------------------------------------------------------------------ #
    async def get_risk_score(self, transaction_id: str) -> schemas.RiskScoreOut:
        """Deterministic mock score + provenance; seeded alert attached."""
        txn_id = validate_external_id(transaction_id, field="transaction_id")
        txn = await db_repository.get_transaction_by_external_id(self.session, txn_id)
        if txn is None:
            raise NotFoundError("transaction", txn_id)

        features = await _extract_features(self.session, txn)
        result = await self._provider.score(features)

        # The seeded ALERT-001 row (if any) is a stored database fact - shown
        # separately, never merged into the mock calculation or overwritten.
        alert_rows = await db_repository.alerts_for_originator(
            self.session, txn.account_id, limit=50
        )
        seeded_alert = next(
            (
                schemas.SeededAlertRef(
                    alert_id=row["external_id"],
                    risk_score=str(Decimal(str(row["risk_score"])).quantize(Decimal("0.01"))),
                    risk_level=row["risk_level"],
                )
                for row in alert_rows
                if row["txn_external_id"] == txn.external_id
            ),
            None,
        )
        result.seeded_alert = seeded_alert
        result.generated_at = datetime.now(UTC)
        return result

    # ------------------------------------------------------------------ #
    # get_risk_features
    # ------------------------------------------------------------------ #
    async def get_risk_features(self, transaction_id: str) -> schemas.RiskFeaturesOut:
        """Feature view derived only from seeded PostgreSQL facts."""
        txn_id = validate_external_id(transaction_id, field="transaction_id")
        txn = await db_repository.get_transaction_by_external_id(self.session, txn_id)
        if txn is None:
            raise NotFoundError("transaction", txn_id)
        features = await _extract_features(self.session, txn)
        return schemas.RiskFeaturesOut(transaction_id=txn.external_id, features=features)

    # ------------------------------------------------------------------ #
    # get_feature_importance
    # ------------------------------------------------------------------ #
    async def get_feature_importance(self, transaction_id: str) -> schemas.FeatureImportanceOut:
        """Mock contributions (sorted desc) - labeled as non-ML by schema."""
        txn_id = validate_external_id(transaction_id, field="transaction_id")
        txn = await db_repository.get_transaction_by_external_id(self.session, txn_id)
        if txn is None:
            raise NotFoundError("transaction", txn_id)

        features = await _extract_features(self.session, txn)
        score_result = await self._provider.score(features)
        contributions = score_result.contributions
        ordered = sorted(contributions.items(), key=lambda kv: (-kv[1], kv[0]))
        return schemas.FeatureImportanceOut(
            transaction_id=txn.external_id,
            source=self._provider.source,
            model_version=self._provider.model_version,
            top_features=[
                schemas.FeatureContribution(feature=name, importance=value)
                for name, value in ordered
            ],
        )

    # ------------------------------------------------------------------ #
    # get_previous_risk_events
    # ------------------------------------------------------------------ #
    async def get_previous_risk_events(self, account_id: str) -> schemas.RiskEventsOut:
        """Stored alert facts for an account; empty result when none exist.

        The account must exist (structured NOT_FOUND otherwise), but having no
        prior alerts is a valid, explicitly-reported outcome.
        """
        acct_id = validate_external_id(account_id, field="account_id")
        account = await db_repository.get_account_by_external_id(self.session, acct_id)
        if account is None:
            raise NotFoundError("account", acct_id)

        rows = await db_repository.alerts_for_originator(self.session, account.id, limit=50)
        events = [
            schemas.RiskEvent(
                transaction_id=row["txn_external_id"],
                alert_id=row["external_id"],
                alert_type=row["alert_type"],
                risk_score=str(Decimal(str(row["risk_score"])).quantize(Decimal("0.01"))),
                risk_level=row["risk_level"],
                source="MOCK",
                origin="seeded_alert_row",
            )
            for row in rows
        ]
        return schemas.RiskEventsOut(account_id=acct_id, events=events, count=len(events))
