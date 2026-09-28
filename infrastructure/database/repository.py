"""Pure data-access functions over the Phase 4 SQLAlchemy models.

Repositories know *how* to query PostgreSQL; services decide *what* it means.
No validation, no error translation, no Pydantic mapping here.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from infrastructure.database.models import Account, Device, IPAddress, Transaction


async def get_transaction_by_external_id(
    session: AsyncSession, external_id: str
) -> Transaction | None:
    """Fetch a transaction with sender, recipient, device, and IP loaded."""
    stmt = (
        select(Transaction)
        .where(Transaction.external_id == external_id)
        .options(
            joinedload(Transaction.account),
            joinedload(Transaction.recipient_account),
            joinedload(Transaction.device),
            joinedload(Transaction.ip_address),
        )
        .limit(1)
    )
    return await session.scalar(stmt)


async def get_account_by_external_id(session: AsyncSession, external_id: str) -> Account | None:
    return await session.scalar(select(Account).where(Account.external_id == external_id).limit(1))


async def get_device_by_external_id(session: AsyncSession, external_id: str) -> Device | None:
    return await session.scalar(select(Device).where(Device.external_id == external_id).limit(1))


async def get_ip_by_address(session: AsyncSession, address: str) -> IPAddress | None:
    return await session.scalar(select(IPAddress).where(IPAddress.address == address).limit(1))


async def _fetch_with_extra(session: AsyncSession, stmt, limit: int) -> list[Transaction]:
    """Execute a transaction query fetching ``limit + 1`` rows.

    The extra row lets callers report ``truncated`` without a second count
    query; callers must slice to ``limit`` before returning data.
    """
    stmt = stmt.limit(limit + 1)
    result = await session.scalars(
        stmt.options(
            joinedload(Transaction.account),
            joinedload(Transaction.recipient_account),
        )
    )
    return list(result.unique().all())


def _transactions_newest_first_for_account(account_id: int):
    return (
        select(Transaction)
        .where(
            (Transaction.account_id == account_id)
            | (Transaction.recipient_account_id == account_id)
        )
        .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
    )


def _transactions_newest_first_as_recipient(recipient_account_id: int):
    return (
        select(Transaction)
        .where(Transaction.recipient_account_id == recipient_account_id)
        .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
    )


def _transactions_newest_first_by_device(device_id: int):
    return (
        select(Transaction)
        .where(Transaction.device_id == device_id)
        .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
    )


def _transactions_newest_first_by_ip(ip_id: int):
    return (
        select(Transaction)
        .where(Transaction.ip_address_id == ip_id)
        .order_by(Transaction.timestamp.desc(), Transaction.id.desc())
    )


async def list_transactions_for_account(
    session: AsyncSession, account_id: int, limit: int
) -> list[Transaction]:
    """Transactions where the account is sender OR recipient (newest first)."""
    return await _fetch_with_extra(
        session, _transactions_newest_first_for_account(account_id), limit
    )


async def list_transactions_as_recipient(
    session: AsyncSession, recipient_account_id: int, limit: int
) -> list[Transaction]:
    """Transactions where the account is the recipient (newest first)."""
    return await _fetch_with_extra(
        session, _transactions_newest_first_as_recipient(recipient_account_id), limit
    )


async def list_transactions_by_device(
    session: AsyncSession, device_id: int, limit: int
) -> list[Transaction]:
    """Transactions performed from a device (newest first)."""
    return await _fetch_with_extra(session, _transactions_newest_first_by_device(device_id), limit)


async def list_transactions_by_ip(
    session: AsyncSession, ip_id: int, limit: int
) -> list[Transaction]:
    """Transactions performed from an IP address (newest first)."""
    return await _fetch_with_extra(session, _transactions_newest_first_by_ip(ip_id), limit)


# --- Risk feature queries (Phase 7) ---------------------------------------

_TRANSACTION_COUNT_IN_WINDOW = (
    "SELECT count(*) FROM transactions "
    "WHERE account_id = :account_id AND timestamp >= :window_start AND timestamp <= :window_end"
)

_ALERT_COUNT_FOR_ORIGINATOR = (
    "SELECT count(*) FROM alerts "
    "JOIN transactions ON transactions.id = alerts.transaction_id "
    "WHERE transactions.account_id = :account_id"
)

_ORIGINATOR_ALERTS = (
    "SELECT alerts.id, alerts.external_id, alerts.transaction_id, alerts.alert_type, "
    "alerts.risk_score, alerts.risk_level, transactions.external_id AS txn_external_id "
    "FROM alerts "
    "JOIN transactions ON transactions.id = alerts.transaction_id "
    "WHERE transactions.account_id = :account_id "
    "ORDER BY alerts.created_at DESC, alerts.id DESC "
    "LIMIT :limit"
)


async def count_transactions_in_window(
    session: AsyncSession, account_id: int, window_start: datetime, window_end: datetime
) -> int:
    """Count the originator's transactions within [window_start, window_end]."""
    from sqlalchemy import text

    result = await session.execute(
        text(_TRANSACTION_COUNT_IN_WINDOW),
        {"account_id": account_id, "window_start": window_start, "window_end": window_end},
    )
    return int(result.scalar_one())


async def count_alerts_for_originator(session: AsyncSession, account_id: int) -> int:
    """Count alerts on any transaction sent by this account (database fact)."""
    from sqlalchemy import text

    result = await session.execute(text(_ALERT_COUNT_FOR_ORIGINATOR), {"account_id": account_id})
    return int(result.scalar_one())


async def alerts_for_originator(
    session: AsyncSession, account_id: int, limit: int
) -> list[dict[str, Any]]:
    """Alert rows (structured dicts) on transactions sent by this account."""
    from sqlalchemy import text

    result = await session.execute(
        text(_ORIGINATOR_ALERTS), {"account_id": account_id, "limit": limit}
    )
    return [dict(row._mapping) for row in result]


__all__ = [
    "get_account_by_external_id",
    "get_device_by_external_id",
    "get_ip_by_address",
    "get_transaction_by_external_id",
    "alerts_for_originator",
    "count_alerts_for_originator",
    "count_transactions_in_window",
    "list_transactions_as_recipient",
    "list_transactions_by_device",
    "list_transactions_by_ip",
    "list_transactions_for_account",
]
