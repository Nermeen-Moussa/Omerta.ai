"""Account Application Service for Omerta.ai.

Manages bank account queries, counterparties, balance ledgers, auditable demo adjustments, and transaction history.
"""

from datetime import UTC, datetime
from decimal import Decimal
import secrets
from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import (
    Account,
    AccountLedgerEntry,
    AuditEvent,
    Customer,
    Transaction,
)


class AccountService:
    """Service layer for bank accounts, ledger counterparties, and auditable adjustments."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_accounts(
        self,
        *,
        search: str | None = None,
        account_type: str | None = None,
        currency: str | None = None,
        risk_level: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """Paginated list of bank accounts."""
        query = select(Account).options(selectinload(Account.customer))

        conditions = []
        if search:
            clean = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Account.external_id.ilike(clean),
                    Account.customer_name.ilike(clean),
                )
            )
        if account_type:
            conditions.append(Account.account_type == account_type.upper())
        if currency:
            conditions.append(Account.currency == currency.upper())
        if risk_level:
            conditions.append(Account.risk_level == risk_level.upper())
        if status:
            conditions.append(Account.status == status.upper())

        if conditions:
            query = query.where(*conditions)

        count_q = select(func.count(Account.id))
        if conditions:
            count_q = count_q.where(*conditions)
        total = await self.session.scalar(count_q) or 0

        offset = (max(1, page) - 1) * page_size
        query = query.order_by(Account.id.asc()).offset(offset).limit(page_size)

        accounts = (await self.session.scalars(query)).all()

        items = []
        for a in accounts:
            items.append({
                "id": a.id,
                "external_id": a.external_id,
                "customer_id": a.customer_id,
                "customer_name": a.customer_name,
                "customer_external_id": a.customer.external_id if a.customer else "N/A",
                "customer_user_number": a.customer.omerta_user_number if a.customer else "N/A",
                "account_type": a.account_type,
                "currency": a.currency,
                "balance": float(a.balance),
                "country": a.country,
                "status": a.status,
                "risk_level": a.risk_level,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }

    async def get_account_detail(self, identifier: str) -> dict[str, Any] | None:
        """Fetch detail view of a bank account, ledger entries, and frequent counterparties."""
        query = select(Account).options(
            selectinload(Account.customer),
            selectinload(Account.ledger_entries),
        )

        if identifier.isdigit():
            query = query.where(or_(Account.id == int(identifier), Account.external_id == identifier))
        else:
            query = query.where(Account.external_id == identifier)

        account = await self.session.scalar(query)
        if not account:
            return None

        # Fetch recent transactions
        txns_q = (
            select(Transaction)
            .options(selectinload(Transaction.recipient_account), selectinload(Transaction.account))
            .where(or_(Transaction.account_id == account.id, Transaction.recipient_account_id == account.id))
            .order_by(desc(Transaction.timestamp))
            .limit(15)
        )
        txns = (await self.session.scalars(txns_q)).all()

        # Build counterparties
        counterparties = {}
        for t in txns:
            is_outflow = (t.account_id == account.id)
            other_acc = t.recipient_account if is_outflow else t.account
            if other_acc and other_acc.id != account.id:
                c_info = counterparties.setdefault(other_acc.external_id, {
                    "account_external_id": other_acc.external_id,
                    "customer_name": other_acc.customer_name,
                    "total_transfers": 0,
                    "total_volume": 0.0,
                    "risk_level": other_acc.risk_level,
                })
                c_info["total_transfers"] += 1
                c_info["total_volume"] += float(t.amount)

        ledger_records = []
        for entry in account.ledger_entries or []:
            ledger_records.append({
                "entry_id": entry.external_id,
                "entry_type": entry.entry_type,
                "amount": float(entry.amount),
                "currency": entry.currency,
                "balance_after": float(entry.balance_after),
                "description": entry.description,
                "created_at": entry.created_at.isoformat(),
            })

        return {
            "account": {
                "id": account.id,
                "external_id": account.external_id,
                "customer_id": account.customer_id,
                "customer_name": account.customer_name,
                "customer_external_id": account.customer.external_id if account.customer else "N/A",
                "customer_user_number": account.customer.omerta_user_number if account.customer else "N/A",
                "account_type": account.account_type,
                "currency": account.currency,
                "balance": float(account.balance),
                "country": account.country,
                "status": account.status,
                "risk_level": account.risk_level,
                "created_at": account.created_at.isoformat() if account.created_at else None,
            },
            "ledger_entries": ledger_records[:30],
            "recent_transactions": [
                {
                    "id": t.id,
                    "external_id": t.external_id,
                    "direction": "OUTFLOW" if t.account_id == account.id else "INFLOW",
                    "counterparty": t.recipient_account.customer_name if t.account_id == account.id else t.account.customer_name,
                    "counterparty_account": t.recipient_account.external_id if t.account_id == account.id else t.account.external_id,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "type": t.transaction_type,
                    "status": t.status,
                    "risk_score": float(t.risk_score) if t.risk_score is not None else 0.0,
                    "risk_level": t.risk_level,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in txns
            ],
            "counterparties": list(counterparties.values()),
        }

    async def apply_admin_balance_adjustment(
        self,
        *,
        account_identifier: str,
        adjustment_amount: Decimal,
        reason: str,
        admin_actor_id: str,
    ) -> dict[str, Any]:
        """Apply an authorized demo balance adjustment through an immutable ledger entry."""
        if not reason.strip():
            raise ValueError("A documented compliance/admin reason is mandatory for demo adjustments.")

        stmt = select(Account).where(
            or_(Account.external_id == account_identifier, Account.id == (int(account_identifier) if account_identifier.isdigit() else -1))
        ).with_for_update()

        account = await self.session.scalar(stmt)
        if not account:
            raise ValueError("Account not found.")

        old_balance = account.balance
        new_balance = old_balance + adjustment_amount
        if new_balance < Decimal("0.00"):
            raise ValueError("Adjustment would result in a negative demo balance, which is not permitted.")

        account.balance = new_balance

        ledger_ext_id = f"LED-ADJ-{secrets.token_hex(4).upper()}"
        ledger_entry = AccountLedgerEntry(
            external_id=ledger_ext_id,
            account_id=account.id,
            entry_type="ADMIN_ADJUSTMENT",
            amount=adjustment_amount,
            currency=account.currency,
            balance_after=new_balance,
            description=f"Admin Adjustment: {reason.strip()} (By {admin_actor_id})",
            idempotency_key=f"ADJ-{secrets.token_hex(6).upper()}",
        )
        self.session.add(ledger_entry)

        # Audit event
        audit_event = AuditEvent(
            event_id=f"EVT-{secrets.token_hex(6).upper()}",
            event_type="ADMIN_BALANCE_ADJUSTMENT",
            actor_type="ADMIN",
            actor_id=admin_actor_id,
            source="AccountService",
            metadata_={
                "account_id": account.external_id,
                "old_balance": str(old_balance),
                "new_balance": str(new_balance),
                "adjustment_amount": str(adjustment_amount),
                "reason": reason.strip(),
            },
        )
        self.session.add(audit_event)
        await self.session.commit()

        return {
            "success": True,
            "account_id": account.external_id,
            "old_balance": float(old_balance),
            "new_balance": float(new_balance),
            "currency": account.currency,
            "ledger_entry_id": ledger_ext_id,
            "entry_type": "ADMIN_ADJUSTMENT",
            "reason": reason.strip(),
        }
