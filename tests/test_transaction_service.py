"""Service-layer tests for the transaction investigation service.

Runs against the isolated omerta_test database via the ``db_session`` fixture
(fresh seed per test, writes rolled back).
"""

from decimal import Decimal

import pytest
from domain.errors import NotFoundError, ValidationError
from domain.services.transaction_service import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    TransactionService,
)
from infrastructure.database.seed import SAFE_DOC_IP, SAFE_DOC_IP_2
from sqlalchemy.ext.asyncio import AsyncSession

EXPECTED_TXN_IDS = {"TXN-001", "TXN-1001", "TXN-1002", "TXN-1003", "TXN-1004", "TXN-1005"}


async def test_get_transaction_success(db_session: AsyncSession) -> None:
    """get_transaction returns full TXN-001 facts from PostgreSQL."""
    result = await TransactionService(db_session).get_transaction("TXN-001")

    assert result.transaction_id == "TXN-001"
    assert result.amount == Decimal("8400.00")
    assert result.currency == "USD"
    assert result.transaction_type == "WIRE"
    assert result.status == "COMPLETED"
    assert result.is_new_device is True
    assert result.is_new_ip is True
    assert result.sender.external_id == "ACC-1001"
    assert result.recipient.external_id == "ACC-9001"
    assert result.device is not None and result.device.external_id == "DEV-123"
    assert result.ip is not None and result.ip.address == SAFE_DOC_IP
    assert result.data_source == "POSTGRES"


async def test_get_transaction_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        await TransactionService(db_session).get_transaction("TXN-999")
    assert exc_info.value.payload == {
        "error": "NOT_FOUND",
        "resource": "transaction",
        "id": "TXN-999",
    }


async def test_get_transaction_invalid_id(db_session: AsyncSession) -> None:
    for bad in ("", "   "):
        with pytest.raises(ValidationError):
            await TransactionService(db_session).get_transaction(bad)


async def test_get_account_success(db_session: AsyncSession) -> None:
    result = await TransactionService(db_session).get_account("ACC-1001")

    assert result.account_id == "ACC-1001"
    assert result.customer_name == "John Anderson"
    assert result.account_type == "CHECKING"
    assert result.country == "US"
    assert result.status == "ACTIVE"
    assert result.risk_level == "HIGH"


async def test_get_account_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        await TransactionService(db_session).get_account("ACC-999")
    assert exc_info.value.payload["resource"] == "account"
    assert exc_info.value.payload["id"] == "ACC-999"


async def test_get_account_transactions_includes_both_roles(
    db_session: AsyncSession,
) -> None:
    """ACC-4001 is sender of TXN-1004 and recipient of TXN-1005; both appear."""
    result = await TransactionService(db_session).get_account_transactions("ACC-4001")

    ids = {item.transaction_id for item in result.items}
    assert {"TXN-1004", "TXN-1005"}.issubset(ids)
    assert result.count == len(result.items)
    assert result.limit == DEFAULT_LIMIT
    assert result.truncated is False


async def test_get_account_transactions_newest_first(db_session: AsyncSession) -> None:
    """Ordering is deterministic: newest first, ties broken by id."""
    result = await TransactionService(db_session).get_account_transactions("ACC-1001")

    ids = [item.transaction_id for item in result.items]
    assert set(ids) == {"TXN-001", "TXN-1001", "TXN-1002", "TXN-1003"}
    timestamps = [item.timestamp for item in result.items]
    assert timestamps == sorted(timestamps, reverse=True)
    assert ids[0] == "TXN-001"


async def test_get_account_transactions_limit_and_truncation(
    db_session: AsyncSession,
) -> None:
    full = await TransactionService(db_session).get_account_transactions("ACC-1001")
    limited = await TransactionService(db_session).get_account_transactions("ACC-1001", limit=2)

    assert limited.count == 2
    assert limited.limit == 2
    assert limited.truncated is True
    # Newest-first must be preserved under limiting.
    assert [item.transaction_id for item in limited.items] == [
        item.transaction_id for item in full.items[:2]
    ]


async def test_get_account_transactions_limit_bounds(db_session: AsyncSession) -> None:
    service = TransactionService(db_session)
    for bad in (0, -1, MAX_LIMIT + 1):
        with pytest.raises(ValidationError):
            await service.get_account_transactions("ACC-1001", limit=bad)


async def test_get_account_transactions_nonexistent_account(
    db_session: AsyncSession,
) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        await TransactionService(db_session).get_account_transactions("ACC-999")
    assert exc_info.value.payload["resource"] == "account"


async def test_get_recipient_history_filters_correctly(db_session: AsyncSession) -> None:
    """ACC-9001 is recipient of TXN-001 and TXN-1004 (and sender of TXN-1005)."""
    result = await TransactionService(db_session).get_recipient_history("ACC-9001")

    ids = {item.transaction_id for item in result.items}
    assert ids == {"TXN-001", "TXN-1004", "TXN-1006"}
    for item in result.items:
        assert item.recipient_account_id == "ACC-9001"


async def test_get_recipient_history_limit(db_session: AsyncSession) -> None:
    result = await TransactionService(db_session).get_recipient_history("ACC-9001", limit=1)

    assert result.count == 1
    assert result.truncated is True
    assert result.items[0].transaction_id == "TXN-001"  # newest first


async def test_get_recipient_history_nonexistent(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await TransactionService(db_session).get_recipient_history("ACC-999")


async def test_get_device_history_shared_device(db_session: AsyncSession) -> None:
    """DEV-123 links ACC-1001 activity across two suspicious transactions."""
    result = await TransactionService(db_session).get_device_history("DEV-123")

    ids = {item.transaction_id for item in result.items}
    assert ids == {"TXN-001", "TXN-1003", "TXN-1006"}
    assert result.device.external_id == "DEV-123"
    assert result.device.risk_level == "HIGH"


async def test_get_device_history_nonexistent(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError) as exc_info:
        await TransactionService(db_session).get_device_history("DEV-999")
    assert exc_info.value.payload["resource"] == "device"


async def test_get_ip_history_filters_correctly(db_session: AsyncSession) -> None:
    """SAFE_DOC_IP was used by TXN-001 and TXN-1003 (new device + new IP)."""
    result = await TransactionService(db_session).get_ip_history(SAFE_DOC_IP)

    ids = {item.transaction_id for item in result.items}
    assert ids == {"TXN-001", "TXN-1003", "TXN-1006"}
    assert result.ip.address == SAFE_DOC_IP


async def test_get_ip_history_limit_nonexistent(db_session: AsyncSession) -> None:
    service = TransactionService(db_session)
    limited = await service.get_ip_history(SAFE_DOC_IP_2, limit=2)
    assert limited.count == 2
    assert limited.truncated is True

    with pytest.raises(NotFoundError) as exc_info:
        await service.get_ip_history("203.0.113.1")  # TEST-NET-3, never seeded
    assert exc_info.value.payload["resource"] == "ip"
