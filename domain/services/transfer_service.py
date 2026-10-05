"""Transfer & Ledger Execution Service for Omerta.ai.

Enforces double-entry ledger integrity, atomic debit/credit balance updates,
concurrency locking, idempotency protection, recipient discovery by Omerta User Number,
and automatic mock risk evaluation (> 40.00 human review trigger).
"""

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
import re
from datetime import UTC, datetime
from decimal import Decimal
import secrets
from typing import Any
import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.services.location_velocity import evaluate_geographic_velocity
from infrastructure.database.models import (
    Account,
    AccountLedgerEntry,
    Alert,
    AuditEvent,
    Customer,
    Device,
    IPAddress,
    RiskAssessment,
    RiskSignal,
    Session,
    Transaction,
    Transfer,
    User,
)


class TransferConcurrencyManager:
    """Thread-safe & async coroutine concurrency controller for banking transfers.

    Combines an asyncio.Semaphore to bound concurrent in-flight transfer workloads
    with per-account asyncio.Lock mutexes in strict alphanumeric order to eliminate
    race conditions and avoid AB-BA deadlocks.
    """

    def __init__(self, max_concurrent: int = 25):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._account_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._admin_lock = asyncio.Lock()

    async def acquire_locks(self, sender_key: str, recipient_key: str) -> list[asyncio.Lock]:
        """Acquire ordered mutex locks and semaphore for transfer participant accounts."""
        async with self._admin_lock:
            # Sort keys to ensure deterministic lock acquisition order (prevents AB-BA deadlocks)
            keys = sorted([str(sender_key), str(recipient_key)])
            locks = [self._account_locks[k] for k in keys]

        await self._semaphore.acquire()
        for lock in locks:
            await lock.acquire()

        return locks

    def release_locks(self, locks: list[asyncio.Lock]) -> None:
        """Release per-account mutex locks in reverse order and free semaphore."""
        for lock in reversed(locks):
            if lock.locked():
                lock.release()
        self._semaphore.release()

    @asynccontextmanager
    async def transfer_lock(self, sender_key: str, recipient_key: str):
        """Async context manager wrapper around semaphore & mutex lock acquisition."""
        locks = await self.acquire_locks(sender_key, recipient_key)
        try:
            yield
        finally:
            self.release_locks(locks)


_GLOBAL_TRANSFER_CONCURRENCY = TransferConcurrencyManager()


class TransferError(Exception):
    """Base exception for transfer failures."""

    def __init__(self, message: str, code: str = "TRANSFER_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class TransferService:
    """Orchestrates secure customer-to-customer simulated transfers."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _resolve_customer_by_identifier(self, identifier: str) -> Customer | None:
        """Resolve a customer by Omerta User Number or Registered Phone Number."""
        clean = identifier.strip()
        if not clean:
            return None
        clean_upper = clean.upper()
        # Clean digits from phone string
        digits_only = re.sub(r"[^\d+]", "", clean)
        pure_digits = re.sub(r"\D", "", clean)

        conditions = [
            Customer.omerta_user_number == clean_upper,
        ]
        if digits_only:
            conditions.append(Customer.phone == digits_only)
            conditions.append(Customer.phone == clean)
        if pure_digits and len(pure_digits) >= 6:
            # Match suffix / international variation
            conditions.append(and_(Customer.phone != "", Customer.phone.ilike(f"%{pure_digits[-9:]}%")))

        stmt = (
            select(Customer)
            .options(selectinload(Customer.accounts))
            .where(or_(*conditions))
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def lookup_recipient(self, identifier: str) -> dict[str, Any]:
        """Look up a recipient by unique Omerta User Number or Mobile Phone Number.

        Returns only customer-safe confirmation metadata (masked display name,
        valid user number, masked phone, available currencies). Does not leak private profile,
        email, balance, or transaction history.
        """
        customer = await self._resolve_customer_by_identifier(identifier)
        if not customer:
            raise TransferError(
                f"No registered customer found with identifier '{identifier}'. Please check the Omerta User # or Phone Number.",
                code="RECIPIENT_NOT_FOUND",
                status_code=404,
            )

        if customer.status != "ACTIVE":
            raise TransferError(
                "Recipient account is not active for transfers.",
                code="RECIPIENT_INACTIVE",
                status_code=400,
            )

        # Mask name for privacy (e.g., "Amira El-Sayed" -> "Amira E.")
        parts = customer.name.split()
        if len(parts) > 1:
            masked_name = f"{parts[0]} {parts[1][0]}."
        else:
            masked_name = customer.name

        # Mask phone number (e.g., "+201033334444" -> "+20 10 •••• 4444")
        masked_phone = None
        if customer.phone:
            p = customer.phone
            if len(p) >= 8:
                masked_phone = f"{p[:5]} •••• {p[-4:]}"
            else:
                masked_phone = f"•••• {p[-4:]}"

        supported_currencies = [acc.currency for acc in customer.accounts if acc.status == "ACTIVE"]
        if not supported_currencies:
            supported_currencies = [customer.preferred_currency or "EGP"]

        return {
            "found": True,
            "omerta_user_number": customer.omerta_user_number,
            "phone_masked": masked_phone,
            "display_name": masked_name,
            "country": customer.declared_country or customer.country,
            "supported_currencies": list(set(supported_currencies)),
            "preferred_currency": customer.preferred_currency or "EGP",
        }

    async def execute_transfer(
        self,
        *,
        sender_user_id: int,
        sender_account_id: int | str,
        recipient_user_number: str,
        amount: Decimal,
        currency: str,
        note: str | None = None,
        idempotency_key: str | None = None,
        ip_address: str | None = "192.168.1.100",
        user_agent: str | None = "OmertaWeb/2.0",
        is_vpn: bool = False,
        city: str | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        """Atomically execute a transfer from sender to recipient with Python Semaphore & Mutex lock synchronization."""
        if amount <= Decimal("0.00"):
            raise TransferError("Transfer amount must be strictly positive.", code="INVALID_AMOUNT")

        if not idempotency_key:
            idempotency_key = f"IDEMP-{uuid.uuid4().hex[:16]}"

        async with _GLOBAL_TRANSFER_CONCURRENCY.transfer_lock(str(sender_account_id), str(recipient_user_number)):
            return await self._execute_transfer_internal(
                sender_user_id=sender_user_id,
                sender_account_id=sender_account_id,
                recipient_user_number=recipient_user_number,
                amount=amount,
                currency=currency,
                note=note,
                idempotency_key=idempotency_key,
                ip_address=ip_address,
                user_agent=user_agent,
                is_vpn=is_vpn,
                city=city,
                country=country,
            )

    async def _execute_transfer_internal(
        self,
        *,
        sender_user_id: int,
        sender_account_id: int | str,
        recipient_user_number: str,
        amount: Decimal,
        currency: str,
        note: str | None = None,
        idempotency_key: str | None = None,
        ip_address: str | None = "192.168.1.100",
        user_agent: str | None = "OmertaWeb/2.0",
        is_vpn: bool = False,
        city: str | None = None,
        country: str | None = None,
    ) -> dict[str, Any]:
        # 1. Check idempotency
        existing_transfer = await self.session.scalar(
            select(Transfer).where(Transfer.idempotency_key == idempotency_key).limit(1)
        )
        if existing_transfer:
            return await self.get_transfer_receipt(existing_transfer.external_id)

        # 2. Fetch sender customer & user
        sender_stmt = (
            select(Customer)
            .options(selectinload(Customer.accounts))
            .where(Customer.user_id == sender_user_id)
            .limit(1)
        )
        sender_customer = await self.session.scalar(sender_stmt)
        if not sender_customer:
            raise TransferError("Sender profile not found.", code="SENDER_NOT_FOUND", status_code=404)

        if sender_customer.status != "ACTIVE":
            raise TransferError("Your customer profile is currently inactive or suspended.", code="SENDER_INACTIVE")

        # 3. Resolve sender account with row lock
        if isinstance(sender_account_id, int):
            sender_acc_stmt = (
                select(Account)
                .where(and_(Account.id == sender_account_id, Account.customer_id == sender_customer.id))
                .with_for_update()
            )
        else:
            sender_acc_stmt = (
                select(Account)
                .where(and_(Account.external_id == sender_account_id, Account.customer_id == sender_customer.id))
                .with_for_update()
            )
        sender_account = await self.session.scalar(sender_acc_stmt)
        if not sender_account:
            raise TransferError("Source account not found or does not belong to you.", code="ACCOUNT_NOT_OWNED", status_code=403)

        if sender_account.status != "ACTIVE":
            raise TransferError("Selected source account is not active.", code="ACCOUNT_INACTIVE")

        if sender_account.currency.upper() != currency.upper():
            raise TransferError(
                f"Source account currency ({sender_account.currency}) does not match transfer currency ({currency}).",
                code="CURRENCY_MISMATCH",
            )

        # 4. Resolve recipient customer (supports Omerta User Number or Mobile Phone Number)
        recipient_customer = await self._resolve_customer_by_identifier(recipient_user_number)
        if not recipient_customer:
            raise TransferError(
                f"Recipient identifier '{recipient_user_number}' not found. Please verify the Omerta User Number or Phone Number.",
                code="RECIPIENT_NOT_FOUND",
                status_code=404,
            )

        if recipient_customer.id == sender_customer.id:
            raise TransferError("Cannot transfer funds to your own customer account.", code="SELF_TRANSFER_DISALLOWED")

        if recipient_customer.status != "ACTIVE":
            raise TransferError("Recipient customer profile is not active.", code="RECIPIENT_INACTIVE")

        # 5. Resolve matching recipient account with row lock
        recipient_acc_stmt = (
            select(Account)
            .where(
                and_(
                    Account.customer_id == recipient_customer.id,
                    Account.currency == currency.upper(),
                    Account.status == "ACTIVE",
                )
            )
            .order_by(Account.id.asc())
            .with_for_update()
            .limit(1)
        )
        recipient_account = await self.session.scalar(recipient_acc_stmt)
        if not recipient_account:
            # Fallback: if recipient has any active account, check if same currency
            raise TransferError(
                f"Recipient does not have an active account matching currency '{currency}'.",
                code="RECIPIENT_CURRENCY_UNSUPPORTED",
            )

        # 6. Check sender balance
        if sender_account.balance < amount:
            raise TransferError(
                f"Insufficient available demo balance. Required: {amount:,.2f} {currency}, Available: {sender_account.balance:,.2f} {currency}",
                code="INSUFFICIENT_FUNDS",
                status_code=400,
            )

        # 7. Apply ledger updates atomically
        sender_account.balance = Decimal(str(sender_account.balance)) - amount
        recipient_account.balance = Decimal(str(recipient_account.balance)) + amount

        now = datetime.now(UTC)
        transfer_ref = f"TRF-{secrets.token_hex(4).upper()}-{now.strftime('%M%S')}"
        txn_ref = f"TXN-SIM-{secrets.token_hex(4).upper()}"
        debit_ledger_ref = f"LED-DB-{secrets.token_hex(4).upper()}"
        credit_ledger_ref = f"LED-CR-{secrets.token_hex(4).upper()}"

        # 8. Create Transaction row
        txn = Transaction(
            external_id=txn_ref,
            account_id=sender_account.id,
            recipient_account_id=recipient_account.id,
            amount=amount,
            currency=currency.upper(),
            transaction_type="CUSTOMER_TRANSFER",
            status="COMPLETED",
            timestamp=now,
            is_new_device=False,
            is_new_ip=False,
            txn_metadata={"note": note, "transfer_ref": transfer_ref, "is_vpn": is_vpn},
        )
        self.session.add(txn)
        await self.session.flush()

        # 9. Create Transfer row
        transfer = Transfer(
            external_id=transfer_ref,
            idempotency_key=idempotency_key,
            sender_customer_id=sender_customer.id,
            sender_account_id=sender_account.id,
            recipient_customer_id=recipient_customer.id,
            recipient_account_id=recipient_account.id,
            amount=amount,
            currency=currency.upper(),
            note=note,
            status="COMPLETED",
            transaction_id=txn.id,
        )
        self.session.add(transfer)
        await self.session.flush()

        # 10. Create Immutable Ledger Entries
        debit_entry = AccountLedgerEntry(
            external_id=debit_ledger_ref,
            account_id=sender_account.id,
            transfer_id=transfer.id,
            transaction_id=txn.id,
            entry_type="DEBIT",
            amount=amount,
            currency=currency.upper(),
            balance_after=sender_account.balance,
            description=f"Simulated Transfer to {recipient_customer.name} ({recipient_customer.omerta_user_number})",
            idempotency_key=f"{idempotency_key}-DEBIT",
        )
        credit_entry = AccountLedgerEntry(
            external_id=credit_ledger_ref,
            account_id=recipient_account.id,
            transfer_id=transfer.id,
            transaction_id=txn.id,
            entry_type="CREDIT",
            amount=amount,
            currency=currency.upper(),
            balance_after=recipient_account.balance,
            description=f"Simulated Transfer from {sender_customer.name} ({sender_customer.omerta_user_number})",
            idempotency_key=f"{idempotency_key}-CREDIT",
        )
        self.session.add_all([debit_entry, credit_entry])

        # 11. Mock Risk Assessment Engine (> 40 Human Review Rule)
        base_risk = Decimal("8.00")
        signals = []

        if amount >= Decimal("50000.00"):
            base_risk += Decimal("35.00")
            signals.append({
                "name": "HIGH_VALUE_TRANSFER",
                "severity": "HIGH",
                "description": f"Transfer amount of {amount:,.2f} {currency} exceeds routine threshold.",
                "source": "TRANSACTION_RULE",
            })

        if is_vpn:
            base_risk += Decimal("25.00")
            signals.append({
                "name": "VPN_PROXY_OBSERVED",
                "severity": "MEDIUM",
                "description": "Observed session origin associated with commercial VPN/proxy provider.",
                "source": "IP_ANALYSIS",
            })

        if amount % Decimal("10000.00") == Decimal("0.00") and amount >= Decimal("20000.00"):
            base_risk += Decimal("12.00")
            signals.append({
                "name": "STRUCTURING_ROUND_AMOUNT",
                "severity": "LOW",
                "description": "Exact large round figure transfer pattern.",
                "source": "TRANSACTION_RULE",
            })

        # Geographic Velocity & Impossible Travel Anomaly Check
        prev_sess = await self.session.scalar(
            select(Session)
            .options(selectinload(Session.ip_address))
            .where(and_(Session.customer_id == sender_customer.id, Session.started_at < now))
            .order_by(Session.started_at.desc())
            .limit(1)
        )
        if prev_sess:
            prev_cntry = prev_sess.ip_address.country if prev_sess.ip_address else (sender_customer.declared_country or "EG")
            prev_cty = "Cairo"  # default historical city
            curr_cntry = country or (sender_customer.declared_country or "EG")
            curr_cty = city or ("Cairo" if curr_cntry.upper() == "EG" else None)

            velocity = evaluate_geographic_velocity(
                prev_country=prev_cntry,
                prev_city=prev_cty,
                prev_timestamp=prev_sess.started_at,
                current_country=curr_cntry,
                current_city=curr_cty,
                current_timestamp=now,
            )
            if velocity.is_impossible_travel:
                base_risk += Decimal(str(velocity.risk_score_penalty))
                signals.append({
                    "name": "IMPOSSIBLE_TRAVEL_VELOCITY",
                    "severity": "CRITICAL",
                    "description": velocity.reason,
                    "source": "GEOGRAPHIC_VELOCITY_ENGINE",
                })
                sender_customer.risk_level = "CRITICAL"


        final_risk = min(Decimal("95.00"), base_risk)
        requires_review = final_risk > Decimal("40.00")

        if final_risk <= Decimal("20.00"):
            risk_lvl = "LOW"
        elif final_risk <= Decimal("40.00"):
            risk_lvl = "MODERATE"
        elif final_risk <= Decimal("70.00"):
            risk_lvl = "HIGH"
        else:
            risk_lvl = "CRITICAL"

        txn.risk_score = final_risk
        txn.risk_level = risk_lvl
        txn.review_status = "REQUIRES_REVIEW" if requires_review else "NOT_REQUIRED"

        # Record Risk Assessment
        risk_assessment = RiskAssessment(
            external_id=f"RA-{secrets.token_hex(4).upper()}",
            transaction_id=txn.id,
            risk_score=final_risk,
            risk_level=risk_lvl,
            requires_human_review=requires_review,
            correlation_id=f"CORR-{txn.external_id}",
            summary=f"Automated risk evaluation: {len(signals)} signal(s) detected. Review required: {requires_review}.",
        )
        self.session.add(risk_assessment)
        await self.session.flush()

        for s in signals:
            sig = RiskSignal(
                assessment_id=risk_assessment.id,
                signal_name=s["name"],
                severity=s["severity"],
                description=s["description"],
                source=s["source"],
            )
            self.session.add(sig)

        if requires_review:
            alert = Alert(
                external_id=f"ALT-{secrets.token_hex(4).upper()}",
                transaction_id=txn.id,
                alert_type="HIGH_RISK_TRANSFER_REVIEW",
                risk_score=final_risk,
                risk_level=risk_lvl,
                status="OPEN",
            )
            self.session.add(alert)

            try:
                from domain.services.ticket_service import TicketService
                tkt_svc = TicketService(self.session)
                sig_names = ", ".join(s["name"] for s in signals) if signals else "Elevated risk score"
                await tkt_svc.create_ticket(
                    customer=sender_customer,
                    title=f"Risk Review: Automated Alert for Transfer {transfer_ref}",
                    description=f"Transaction {transfer_ref} triggered automated risk score {final_risk:.2f}% ({risk_lvl}). Signals: {sig_names}.",
                    ticket_type="RISK_REVIEW",
                    priority_override="HIGH" if final_risk < Decimal("75.00") else "CRITICAL",
                    related_transaction_id=transfer.id,
                    related_account_id=sender_account.id,
                    related_risk_assessment_id=risk_assessment.external_id,
                    opened_by="SYSTEM",
                )
            except Exception:
                pass

        # 12. Record Audit Event
        audit_event = AuditEvent(
            event_id=f"EVT-{secrets.token_hex(6).upper()}",
            event_type="TRANSFER_EXECUTED",
            actor_type="CUSTOMER",
            actor_id=str(sender_user_id),
            source="TransferService",
            transaction_id=txn.external_id,
            metadata_={
                "transfer_ref": transfer_ref,
                "amount": str(amount),
                "currency": currency,
                "sender_user_number": sender_customer.omerta_user_number,
                "recipient_user_number": recipient_customer.omerta_user_number,
                "risk_score": float(final_risk),
                "requires_review": requires_review,
            },
        )
        self.session.add(audit_event)
        await self.session.commit()

        return await self.get_transfer_receipt(transfer_ref)

    async def get_transfer_receipt(self, transfer_ref: str) -> dict[str, Any]:
        """Fetch receipt for a completed transfer."""
        stmt = (
            select(Transfer)
            .options(
                selectinload(Transfer.sender_customer),
                selectinload(Transfer.recipient_customer),
                selectinload(Transfer.sender_account),
                selectinload(Transfer.recipient_account),
                selectinload(Transfer.transaction),
            )
            .where(Transfer.external_id == transfer_ref)
            .limit(1)
        )
        transfer = await self.session.scalar(stmt)
        if not transfer:
            raise TransferError("Transfer record not found.", code="TRANSFER_NOT_FOUND", status_code=404)

        return {
            "transfer_id": transfer.external_id,
            "transaction_reference": transfer.transaction.external_id if transfer.transaction else None,
            "status": transfer.status,
            "amount": float(transfer.amount),
            "currency": transfer.currency,
            "formatted_amount": f"{transfer.amount:,.2f} {transfer.currency}",
            "note": transfer.note,
            "created_at": transfer.created_at.isoformat(),
            "risk_score": float(transfer.transaction.risk_score) if transfer.transaction and transfer.transaction.risk_score is not None else 0.0,
            "risk_level": transfer.transaction.risk_level if transfer.transaction and transfer.transaction.risk_level else "LOW",
            "review_status": transfer.transaction.review_status if transfer.transaction and transfer.transaction.review_status else "NOT_REQUIRED",
            "sender": {
                "name": transfer.sender_customer.name,
                "omerta_user_number": transfer.sender_customer.omerta_user_number,
                "account_id": transfer.sender_account.external_id,
            },
            "recipient": {
                "name": transfer.recipient_customer.name,
                "omerta_user_number": transfer.recipient_customer.omerta_user_number,
                "account_id": transfer.recipient_account.external_id,
            },
            "fee": "0.00 DEMO",
            "is_demo": True,
            "disclaimer": "This is a simulated demo transfer for testing and compliance training purposes.",
        }

    async def list_customer_transfers(
        self,
        *,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """List all transfers involving the authenticated customer."""
        customer = await self.session.scalar(
            select(Customer).where(Customer.user_id == user_id).limit(1)
        )
        if not customer:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

        query = (
            select(Transfer)
            .options(
                selectinload(Transfer.sender_customer),
                selectinload(Transfer.recipient_customer),
                selectinload(Transfer.sender_account),
                selectinload(Transfer.recipient_account),
            )
            .where(
                or_(
                    Transfer.sender_customer_id == customer.id,
                    Transfer.recipient_customer_id == customer.id,
                )
            )
            .order_by(Transfer.id.desc())
        )

        count_q = select(func.count(Transfer.id)).where(
            or_(
                Transfer.sender_customer_id == customer.id,
                Transfer.recipient_customer_id == customer.id,
            )
        )
        total = await self.session.scalar(count_q) or 0

        offset = (max(1, page) - 1) * page_size
        rows = (await self.session.scalars(query.offset(offset).limit(page_size))).all()

        items = []
        for t in rows:
            is_sender = t.sender_customer_id == customer.id
            items.append({
                "transfer_id": t.external_id,
                "direction": "OUTGOING" if is_sender else "INCOMING",
                "counterparty_name": t.recipient_customer.name if is_sender else t.sender_customer.name,
                "counterparty_user_number": t.recipient_customer.omerta_user_number if is_sender else t.sender_customer.omerta_user_number,
                "amount": float(t.amount),
                "currency": t.currency,
                "note": t.note,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }
