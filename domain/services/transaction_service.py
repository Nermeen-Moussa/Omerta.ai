"""Transaction investigation service: the business layer behind MCP tools.

Responsibilities:
- validate and clamp tool inputs (ids, limits),
- orchestrate repository calls,
- map ORM rows to JSON-serializable Pydantic schemas,
- translate "missing row" into structured :class:`NotFoundError`s.

The service never leaks ORM objects, SQL, or connection details.
"""

from infrastructure.database import repository
from infrastructure.database.models import Account, Transaction
from sqlalchemy.ext.asyncio import AsyncSession

from domain import schemas
from domain.errors import NotFoundError, ValidationError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MIN_LIMIT = 1


def validate_external_id(value: str, *, field: str) -> str:
    """Validate an external business identifier (non-empty, bounded)."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    cleaned = value.strip()
    if not cleaned:
        raise ValidationError(f"{field} must not be empty", field=field)
    if len(cleaned) > 64:
        raise ValidationError(f"{field} exceeds 64 characters", field=field)
    return cleaned


def validate_limit(value: int | None, *, default: int = DEFAULT_LIMIT) -> int:
    """Validate a result-limit parameter; reject invalid types/ranges cleanly."""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("limit must be an integer", field="limit")
    if value < MIN_LIMIT:
        raise ValidationError(f"limit must be >= {MIN_LIMIT}", field="limit", limit=value)
    if value > MAX_LIMIT:
        raise ValidationError(f"limit must be <= {MAX_LIMIT}", field="limit", limit=value)
    return value


def _account_ref(account: Account) -> schemas.AccountRef:
    return schemas.AccountRef(
        external_id=account.external_id,
        customer_name=account.customer_name,
        country=account.country,
        risk_level=account.risk_level,
    )


def _device_summary(device) -> schemas.DeviceSummary:
    return schemas.DeviceSummary(
        external_id=device.external_id,
        device_type=device.device_type,
        risk_level=device.risk_level,
    )


def _ip_summary(ip) -> schemas.IPSummary:
    return schemas.IPSummary(
        address=ip.address,
        country=ip.country,
        risk_level=ip.risk_level,
    )


def _txn_summary(txn: Transaction) -> schemas.TransactionSummary:
    return schemas.TransactionSummary(
        transaction_id=txn.external_id,
        amount=txn.amount,
        currency=txn.currency,
        sender_account_id=txn.account.external_id,
        recipient_account_id=txn.recipient_account.external_id,
        transaction_type=txn.transaction_type,
        status=txn.status,
        timestamp=txn.timestamp,
        is_new_device=txn.is_new_device,
        is_new_ip=txn.is_new_ip,
    )


def _split_page(rows: list[Transaction], limit: int) -> tuple[list[Transaction], bool]:
    """Split a limit+1 fetch into (page, truncated)."""
    return rows[:limit], len(rows) > limit


class TransactionService:
    """Application service used by the MCP transaction server tools."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # get_transaction
    # ------------------------------------------------------------------ #
    async def get_transaction(self, transaction_id: str) -> schemas.TransactionOut:
        """Full transaction view with sender, recipient, device, and IP."""
        txn_id = validate_external_id(transaction_id, field="transaction_id")
        txn = await repository.get_transaction_by_external_id(self.session, txn_id)
        if txn is None:
            raise NotFoundError("transaction", txn_id)
        return schemas.TransactionOut(
            transaction_id=txn.external_id,
            sender=_account_ref(txn.account),
            recipient=_account_ref(txn.recipient_account),
            amount=txn.amount,
            currency=txn.currency,
            transaction_type=txn.transaction_type,
            status=txn.status,
            timestamp=txn.timestamp,
            device=_device_summary(txn.device) if txn.device else None,
            ip=_ip_summary(txn.ip_address) if txn.ip_address else None,
            is_new_device=txn.is_new_device,
            is_new_ip=txn.is_new_ip,
            metadata=txn.txn_metadata,
        )

    # ------------------------------------------------------------------ #
    # get_account
    # ------------------------------------------------------------------ #
    async def get_account(self, account_id: str) -> schemas.AccountOut:
        """Account facts by external id."""
        acct_id = validate_external_id(account_id, field="account_id")
        account = await repository.get_account_by_external_id(self.session, acct_id)
        if account is None:
            raise NotFoundError("account", acct_id)
        return schemas.AccountOut(
            account_id=account.external_id,
            customer_name=account.customer_name,
            account_type=account.account_type,
            country=account.country,
            created_at=account.created_at,
            status=account.status,
            risk_level=account.risk_level,
        )

    # ------------------------------------------------------------------ #
    # get_account_transactions
    # ------------------------------------------------------------------ #
    async def get_account_transactions(
        self, account_id: str, limit: int | None = None
    ) -> schemas.TransactionHistory:
        """History where the account is sender OR recipient, newest first."""
        acct_id = validate_external_id(account_id, field="account_id")
        validated_limit = validate_limit(limit)
        account = await repository.get_account_by_external_id(self.session, acct_id)
        if account is None:
            raise NotFoundError("account", acct_id)
        rows = await repository.list_transactions_for_account(
            self.session, account.id, validated_limit
        )
        page, truncated = _split_page(rows, validated_limit)
        return schemas.TransactionHistory(
            items=[_txn_summary(row) for row in page],
            count=len(page),
            limit=validated_limit,
            truncated=truncated,
        )

    # ------------------------------------------------------------------ #
    # get_recipient_history
    # ------------------------------------------------------------------ #
    async def get_recipient_history(
        self, recipient_account_id: str, limit: int | None = None
    ) -> schemas.TransactionHistory:
        """History where the account is the recipient, newest first."""
        acct_id = validate_external_id(recipient_account_id, field="recipient_account_id")
        validated_limit = validate_limit(limit)
        account = await repository.get_account_by_external_id(self.session, acct_id)
        if account is None:
            raise NotFoundError("account", acct_id)
        rows = await repository.list_transactions_as_recipient(
            self.session, account.id, validated_limit
        )
        page, truncated = _split_page(rows, validated_limit)
        return schemas.TransactionHistory(
            items=[_txn_summary(row) for row in page],
            count=len(page),
            limit=validated_limit,
            truncated=truncated,
        )

    # ------------------------------------------------------------------ #
    # get_device_history
    # ------------------------------------------------------------------ #
    async def get_device_history(
        self, device_id: str, limit: int | None = None
    ) -> schemas.DeviceActivity:
        """Transactions performed from a device (shared-device patterns)."""
        dev_id = validate_external_id(device_id, field="device_id")
        validated_limit = validate_limit(limit)
        device = await repository.get_device_by_external_id(self.session, dev_id)
        if device is None:
            raise NotFoundError("device", dev_id)
        rows = await repository.list_transactions_by_device(
            self.session, device.id, validated_limit
        )
        page, truncated = _split_page(rows, validated_limit)
        return schemas.DeviceActivity(
            device=_device_summary(device),
            items=[_txn_summary(row) for row in page],
            count=len(page),
            limit=validated_limit,
            truncated=truncated,
        )

    # ------------------------------------------------------------------ #
    # get_ip_history
    # ------------------------------------------------------------------ #
    async def get_ip_history(self, ip_address: str, limit: int | None = None) -> schemas.IPActivity:
        """Transactions performed from an IP address (shared infrastructure)."""
        addr = validate_external_id(ip_address, field="ip_address")
        validated_limit = validate_limit(limit)
        ip = await repository.get_ip_by_address(self.session, addr)
        if ip is None:
            raise NotFoundError("ip", addr)
        rows = await repository.list_transactions_by_ip(self.session, ip.id, validated_limit)
        page, truncated = _split_page(rows, validated_limit)
        return schemas.IPActivity(
            ip=_ip_summary(ip),
            items=[_txn_summary(row) for row in page],
            count=len(page),
            limit=validated_limit,
            truncated=truncated,
        )
