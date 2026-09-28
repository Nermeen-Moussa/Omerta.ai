"""Database tests (Phase 4).

Deterministic tests against the isolated ``omerta_test`` PostgreSQL database.
No external or production database is ever required.
"""

from decimal import Decimal

import pytest
from infrastructure.database.models import (
    Account,
    Alert,
    Base,
    Device,
    Evidence,
    InvestigationCase,
    Transaction,
)
from infrastructure.database.seed import EVIDENCE, seed
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_database_connection(db_session: AsyncSession) -> None:
    """The isolated test database accepts connections and selects."""
    result = await db_session.execute(select(1))
    assert result.scalar_one() == 1


async def test_all_expected_tables_exist(db_session: AsyncSession) -> None:
    """The migration created every Phase 4 table."""
    rows = await db_session.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname='public' AND tablename NOT LIKE 'alembic%'"
        )
    )
    tables = {row[0] for row in rows}
    expected = set(Base.metadata.tables)
    assert expected.issubset(tables), f"missing tables: {expected - tables}"


async def test_seed_data_exists(db_session: AsyncSession) -> None:
    """Seeded accounts and devices match the deterministic definitions."""
    accounts = await db_session.scalar(select(func.count()).select_from(Account))
    devices = await db_session.scalar(select(func.count()).select_from(Device))
    transactions = await db_session.scalar(select(func.count()).select_from(Transaction))
    assert accounts == 5
    assert devices == 3
    assert transactions == 7


async def test_txn_001_exists(db_session: AsyncSession) -> None:
    """TXN-001 matches the documented suspicious-transaction facts."""
    txn = await db_session.scalar(select(Transaction).where(Transaction.external_id == "TXN-001"))
    assert txn is not None
    assert txn.amount == Decimal("8400.00")
    assert txn.currency == "USD"
    assert txn.transaction_type == "WIRE"
    assert txn.is_new_device is True
    assert txn.is_new_ip is True


async def test_alert_001_exists(db_session: AsyncSession) -> None:
    """ALERT-001 carries the seeded mock risk score and HIGH severity."""
    alert = await db_session.scalar(select(Alert).where(Alert.external_id == "ALERT-001"))
    assert alert is not None
    assert alert.risk_score == Decimal("0.87")
    assert alert.risk_level == "HIGH"
    assert alert.status == "OPEN"


async def test_txn_001_connected_to_acc_1001(db_session: AsyncSession) -> None:
    """TXN-001's originator is ACC-1001 and its recipient is ACC-9001."""
    txn = await db_session.scalar(select(Transaction).where(Transaction.external_id == "TXN-001"))
    account = await db_session.scalar(select(Account).where(Account.id == txn.account_id))
    recipient = await db_session.scalar(
        select(Account).where(Account.id == txn.recipient_account_id)
    )
    assert account.external_id == "ACC-1001"
    assert recipient.external_id == "ACC-9001"


async def test_alert_001_references_txn_001(db_session: AsyncSession) -> None:
    """The alert -> transaction -> account chain is fully navigable."""
    alert = await db_session.scalar(select(Alert).where(Alert.external_id == "ALERT-001"))
    txn = await db_session.scalar(select(Transaction).where(Transaction.id == alert.transaction_id))
    assert txn.external_id == "TXN-001"
    account = await db_session.scalar(select(Account).where(Account.id == txn.account_id))
    assert account.external_id == "ACC-1001"


async def test_case_and_evidence_relationships(db_session: AsyncSession) -> None:
    """CASE-001 -> ALERT-001 and case -> evidence are navigable and complete."""
    case = await db_session.scalar(
        select(InvestigationCase).where(InvestigationCase.external_id == "CASE-001")
    )
    assert case is not None
    alert = await db_session.scalar(select(Alert).where(Alert.id == case.alert_id))
    assert alert.external_id == "ALERT-001"

    evidence_rows = (
        await db_session.scalars(select(Evidence).where(Evidence.case_id == case.id))
    ).all()
    assert len(evidence_rows) == len(EVIDENCE)
    assert {e.source for e in evidence_rows} == {"POSTGRES"}
    assert all(e.source_reference for e in evidence_rows)
    assert all(e.description for e in evidence_rows)


async def test_evidence_upsert_is_idempotent(db_session: AsyncSession) -> None:
    """Re-running the seed upserts instead of duplicating evidence rows."""
    case = await db_session.scalar(
        select(InvestigationCase).where(InvestigationCase.external_id == "CASE-001")
    )
    evidence_query = select(Evidence).where(Evidence.case_id == case.id)
    before = len((await db_session.scalars(evidence_query)).all())

    await seed(db_session.bind)

    after = len((await db_session.scalars(evidence_query)).all())
    assert after == before


async def test_risk_scores_are_marked_as_mock(db_session: AsyncSession) -> None:
    """Seeded risk data stays clearly labeled as mock, never an ML prediction."""
    evidence_rows = (
        await db_session.scalars(
            select(Evidence).where(Evidence.source_reference == "alerts.external_id=ALERT-001")
        )
    ).all()
    assert len(evidence_rows) == 1
    payload = evidence_rows[0].data
    assert payload["origin"] == "seed/mock, not an ML prediction"


@pytest.mark.parametrize(
    ("external_id", "new_device", "new_ip"),
    [
        ("TXN-001", True, True),
        ("TXN-1001", False, False),
        ("TXN-1003", True, True),
        ("TXN-1004", False, False),
    ],
)
async def test_new_device_ip_flags(
    db_session: AsyncSession, external_id: str, new_device: bool, new_ip: bool
) -> None:
    """Velocity-feature flags are consistent with the seeded scenario."""
    txn = await db_session.scalar(select(Transaction).where(Transaction.external_id == external_id))
    assert txn is not None
    assert txn.is_new_device is new_device
    assert txn.is_new_ip is new_ip
