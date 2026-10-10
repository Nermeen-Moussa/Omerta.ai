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

from domain.services import layer3_engine, layer4_aml, step_up_service
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


_AML_RECENT_FLAGS: dict[tuple[str, int], datetime] = {}  # dedupe: (pattern, account) -> last alert time


def _layer4_enabled() -> bool:
    from infrastructure.config import get_settings

    return bool(getattr(get_settings(), "layer4_enabled", False))


def _layer3_enabled() -> bool:
    from infrastructure.config import get_settings

    return (getattr(get_settings(), "risk_engine", "legacy") or "legacy").lower() == "layer3"


class TransferError(Exception):
    """Base exception for transfer failures."""

    def __init__(
        self,
        message: str,
        code: str = "TRANSFER_ERROR",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


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
        step_up_challenge_id: str | None = None,
        step_up_code: str | None = None,
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
                step_up_challenge_id=step_up_challenge_id,
                step_up_code=step_up_code,
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
        step_up_challenge_id: str | None = None,
        step_up_code: str | None = None,
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

        # 6b. Layer 3 real-time ML scoring (opt-in: RISK_ENGINE=layer3)
        layer3 = None
        step_up_passed = False
        if _layer3_enabled():
            layer3 = await self._run_layer3(
                sender_customer=sender_customer,
                sender_account=sender_account,
                recipient_customer=recipient_customer,
                recipient_account=recipient_account,
                amount=amount,
                currency=currency,
                is_vpn=is_vpn,
                country=country,
                city=city,
            )
            if layer3.action == layer3_engine.BLOCK_ESCALATE:
                await self._block_and_escalate(
                    layer3=layer3,
                    sender_customer=sender_customer,
                    sender_account=sender_account,
                    recipient_account=recipient_account,
                    recipient_customer=recipient_customer,
                    amount=amount,
                    currency=currency,
                    reason="HIGH_RISK_SCORE",
                )
            elif layer3.action == layer3_engine.STEP_UP:
                binding = dict(
                    customer_id=sender_customer.id,
                    recipient=recipient_customer.omerta_user_number,
                    amount=f"{amount:.2f}",
                    currency=currency,
                )
                if step_up_code:
                    outcome = step_up_service.verify_challenge_detailed(
                        challenge_id=step_up_challenge_id, code=step_up_code, **binding
                    )
                    if outcome == "OK":
                        step_up_passed = True
                    elif outcome == "LOCKED":
                        await self._block_and_escalate(
                            layer3=layer3,
                            sender_customer=sender_customer,
                            sender_account=sender_account,
                            recipient_account=recipient_account,
                            recipient_customer=recipient_customer,
                            amount=amount,
                            currency=currency,
                            reason="STEP_UP_FAILED",
                        )
                    elif outcome == "WRONG":
                        raise TransferError(
                            "Incorrect verification code. Please try again.",
                            code="STEP_UP_INVALID_CODE",
                            status_code=428,
                            details={"challenge_id": step_up_challenge_id, "tier": layer3.tier},
                        )
                if not step_up_passed:
                    # no code supplied, or the challenge expired/unknown: (re)issue one
                    from infrastructure.config import get_settings

                    challenge = step_up_service.issue_challenge(
                        **binding,
                        include_dev_code=bool(getattr(get_settings(), "step_up_dev_echo", False)),
                    )
                    raise TransferError(
                        "Additional verification is required for this transfer.",
                        code="STEP_UP_REQUIRED",
                        status_code=428,
                        details={
                            **challenge,
                            "tier": layer3.tier,
                            "risk_score": layer3.score,
                            "typology": layer3.typology,
                        },
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

        if layer3 is not None:
            # Layer 3 result replaces the legacy mock score (ALLOW, or STEP_UP passed).
            final_risk = Decimal(str(layer3.score))
            risk_lvl = {"LOW": "LOW", "MEDIUM": "MODERATE"}.get(layer3.tier, "HIGH")
            requires_review = False
            signals = [
                {
                    "name": f"L3_TYPOLOGY_{layer3.typology}",
                    "severity": "MEDIUM" if layer3.tier != "LOW" else "LOW",
                    "description": "; ".join(layer3.typology_reasons) or "No typology signals.",
                    "source": "LAYER3_ENGINE",
                },
                *[
                    {
                        "name": "L3_RULE_SIGNAL",
                        "severity": "MEDIUM",
                        "description": r["reason"],
                        "source": "FRAUDGUARD_RULES",
                    }
                    for r in layer3.reasons[:8]
                ],
            ]
            txn.txn_metadata = {
                **(txn.txn_metadata or {}),
                "layer3": layer3.to_dict(),
                "step_up_passed": step_up_passed,
            }

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

        # Layer 4: graph ingest + AML pattern analysis on the CONFIRMED transfer (best-effort,
        # never allowed to fail or delay-break the customer's transfer).
        if _layer4_enabled():
            await self._run_layer4(
                txn=txn,
                sender_customer=sender_customer,
                sender_account=sender_account,
                recipient_customer=recipient_customer,
                recipient_account=recipient_account,
                amount=amount,
                currency=currency,
                risk_score=float(final_risk),
            )

        return await self.get_transfer_receipt(transfer_ref)

    async def _run_layer4(
        self,
        *,
        txn: Transaction,
        sender_customer: Customer,
        sender_account: Account,
        recipient_customer: Customer,
        recipient_account: Account,
        amount: Decimal,
        currency: str,
        risk_score: float,
    ) -> list[dict[str, Any]]:
        """Ingest into the graph, look for smurfing / mule patterns, alert + ticket on a hit."""
        import logging
        from datetime import timedelta

        from infrastructure.config import get_settings

        log = logging.getLogger(__name__)
        st = get_settings()
        now = datetime.now(UTC)

        # 1. Ingest confirmed txn into the relationship graph (Neo4j is a derived projection)
        if getattr(st, "layer4_neo4j_ingest", True):
            try:
                from infrastructure.neo4j.layer4_ingest import ingest_confirmed_transaction

                await ingest_confirmed_transaction(
                    txn_external_id=txn.external_id,
                    sender_account_id=sender_account.external_id,
                    recipient_account_id=recipient_account.external_id,
                    amount=float(amount),
                    currency=currency.upper(),
                    timestamp_iso=now.isoformat(),
                    risk_score=risk_score,
                )
            except Exception as exc:  # Neo4j down is not a reason to fail a transfer
                log.warning("layer4_neo4j_ingest_skipped: %s", exc)

        try:
            # 2. Pull the recent confirmed edges around both parties (from PostgreSQL: source of truth)
            window_h = int(getattr(st, "aml_window_hours", 72))
            since = now - timedelta(hours=window_h)
            focus = [sender_account.id, recipient_account.id]
            cols = (Transaction.external_id, Transaction.account_id, Transaction.recipient_account_id,
                    Transaction.amount, Transaction.currency, Transaction.timestamp)
            base = and_(
                Transaction.status == "COMPLETED",
                Transaction.recipient_account_id.is_not(None),
                Transaction.timestamp >= since,
            )
            rows = (await self.session.execute(
                select(*cols).where(and_(base, or_(Transaction.account_id.in_(focus),
                                                   Transaction.recipient_account_id.in_(focus)))).limit(2000)
            )).all()
            neighbours = {r[1] for r in rows} | {r[2] for r in rows}
            rows += (await self.session.execute(
                select(*cols).where(and_(base, or_(Transaction.account_id.in_(neighbours),
                                                   Transaction.recipient_account_id.in_(neighbours)))).limit(4000)
            )).all()
            seen, edges = set(), []
            for r in rows:
                if r[0] in seen:
                    continue
                seen.add(r[0])
                ts = r[5] if r[5].tzinfo else r[5].replace(tzinfo=UTC)
                edges.append(layer4_aml.Edge(r[0], r[1], r[2], float(r[3]), r[4], ts))

            # 3. Pattern analysis ("Smurfing pattern? structured sub-threshold txns")
            thresholds = {**layer4_aml.DEFAULT_THRESHOLDS, "EGP": float(getattr(st, "aml_threshold_egp", 50000.0))}
            findings = layer4_aml.analyze(edges, focus, now, window_h, thresholds)
            fresh = []
            for f in findings:
                key = (f.pattern, f.subject_account)
                last = _AML_RECENT_FLAGS.get(key)
                if last and (now - last) < timedelta(hours=window_h):
                    continue  # already escalated inside this window
                _AML_RECENT_FLAGS[key] = now
                fresh.append(f)

            txn.txn_metadata = {**(txn.txn_metadata or {}), "layer4": {
                "checked": True, "findings": [f.to_dict() for f in findings]}}
            if not fresh:
                await self.session.commit()
                return []

            # 4. YES -> alert + investigation ticket (escalate to investigation queue)
            for f in fresh:
                lvl = {"MEDIUM": "MODERATE"}.get(f.severity, f.severity)
                self.session.add(Alert(
                    external_id=f"ALT-{secrets.token_hex(4).upper()}",
                    transaction_id=txn.id,
                    alert_type=f"AML_{f.pattern}",
                    risk_score=Decimal(str(f.score)),
                    risk_level=lvl,
                    status="OPEN",
                ))
                subject_customer = sender_customer if f.subject_account == sender_account.id else recipient_customer
                try:
                    from domain.services.ticket_service import TicketService

                    await TicketService(self.session).create_ticket(
                        customer=subject_customer,
                        title=f"AML Review: {f.pattern.replace('_', ' ').title()} ({txn.external_id})",
                        description=f.summary,
                        ticket_type="RISK_REVIEW",
                        priority_override="CRITICAL" if f.severity == "CRITICAL" else "HIGH",
                        related_transaction_id=txn.id,
                        opened_by="SYSTEM",
                    )
                except Exception as exc:
                    log.warning("layer4_ticket_failed: %s", exc)
                self.session.add(AuditEvent(
                    event_id=f"EVT-{secrets.token_hex(6).upper()}",
                    event_type="AML_PATTERN_DETECTED",
                    actor_type="SYSTEM",
                    actor_id="layer4_aml",
                    source="TransferService",
                    transaction_id=txn.external_id,
                    metadata_=f.to_dict(),
                ))
            await self.session.commit()
            return [f.to_dict() for f in fresh]
        except Exception:
            log.exception("layer4_analysis_failed")
            try:
                await self.session.rollback()
            except Exception:
                pass
            return []

    async def _run_layer3(
        self,
        *,
        sender_customer: Customer,
        sender_account: Account,
        recipient_customer: Customer,
        recipient_account: Account,
        amount: Decimal,
        currency: str,
        is_vpn: bool,
        country: str | None,
        city: str | None,
    ) -> "layer3_engine.Layer3Decision":
        """Build the Layer 3 context from the database (best-effort) and score it."""
        from statistics import pstdev
        from zoneinfo import ZoneInfo

        now = datetime.now(UTC)
        from infrastructure.config import get_settings as _gs

        ctx = layer3_engine.TransferRiskContext(
            amount=float(amount), currency=currency.upper(), is_vpn=is_vpn,
            use_recipient_age_feature=bool(getattr(_gs(), "layer3_use_recipient_age", False)),
        )
        try:
            # Behaviour history of the sending account
            rows = (
                await self.session.execute(
                    select(Transaction.amount, Transaction.timestamp)
                    .where(and_(Transaction.account_id == sender_account.id, Transaction.status == "COMPLETED"))
                    .order_by(Transaction.timestamp.desc())
                    .limit(200)
                )
            ).all()
            amounts = [float(r[0]) for r in rows]
            ctx.hist_count = len(amounts)
            if amounts:
                ctx.hist_avg = sum(amounts) / len(amounts)
                ctx.hist_max = max(amounts)
                ctx.hist_std = pstdev(amounts) if len(amounts) > 1 else 0.0
            ctx.txn_count_5min = sum(1 for r in rows if (now - r[1]).total_seconds() <= 300)
            ctx.txn_count_1hour = sum(1 for r in rows if (now - r[1]).total_seconds() <= 3600)

            # Beneficiary novelty / recipient profile
            prior = await self.session.scalar(
                select(func.count(Transfer.id)).where(
                    and_(
                        Transfer.sender_customer_id == sender_customer.id,
                        Transfer.recipient_customer_id == recipient_customer.id,
                    )
                )
            )
            ctx.is_new_beneficiary = (prior or 0) == 0
            created = getattr(recipient_account, "created_at", None)
            if created:
                ctx.recipient_account_age_days = max((now - created).total_seconds() / 86400.0, 0.0)
            ctx.recipient_flagged = (recipient_customer.risk_level or "LOW").upper() in {"HIGH", "CRITICAL"}

            # Previous alerts on this sender's account (first-party / repeat-offender signal)
            ctx.previous_alert_count = int(
                await self.session.scalar(
                    select(func.count(Alert.id))
                    .join(Transaction, Alert.transaction_id == Transaction.id)
                    .where(Transaction.account_id == sender_account.id)
                )
                or 0
            )

            # Device / session context
            cur = await self.session.scalar(
                select(Session)
                .options(selectinload(Session.device))
                .where(and_(Session.customer_id == sender_customer.id, Session.is_active.is_(True)))
                .order_by(Session.started_at.desc())
                .limit(1)
            )
            if cur and cur.device_id:
                older = await self.session.scalar(
                    select(func.count(Session.id)).where(
                        and_(Session.customer_id == sender_customer.id, Session.started_at < cur.started_at)
                    )
                )
                seen_before = await self.session.scalar(
                    select(func.count(Session.id)).where(
                        and_(
                            Session.customer_id == sender_customer.id,
                            Session.device_id == cur.device_id,
                            Session.started_at < cur.started_at,
                        )
                    )
                )
                ctx.is_new_device = (older or 0) > 0 and (seen_before or 0) == 0
                ctx.device_customer_count = int(
                    await self.session.scalar(
                        select(func.count(func.distinct(Session.customer_id))).where(
                            Session.device_id == cur.device_id
                        )
                    )
                    or 1
                )
                if cur.device and cur.device.first_seen_at:
                    ctx.min_since_device_registered = max(
                        (now - cur.device.first_seen_at).total_seconds() / 60.0, 0.0
                    )

            # Geography + impossible travel (same engine the legacy path uses)
            declared = (sender_customer.declared_country or "EG").upper()
            curr_cntry = (country or declared).upper()
            ctx.is_new_country = curr_cntry != declared
            prev = await self.session.scalar(
                select(Session)
                .options(selectinload(Session.ip_address))
                .where(and_(Session.customer_id == sender_customer.id, Session.started_at < now))
                .order_by(Session.started_at.desc())
                .limit(1)
            )
            if prev:
                velocity = evaluate_geographic_velocity(
                    prev_country=prev.ip_address.country if prev.ip_address else declared,
                    prev_city="Cairo",
                    prev_timestamp=prev.started_at,
                    current_country=curr_cntry,
                    current_city=city or ("Cairo" if curr_cntry == "EG" else None),
                    current_timestamp=now,
                )
                ctx.impossible_travel = bool(velocity.is_impossible_travel)

            ctx.is_unusual_hour = now.astimezone(ZoneInfo("Africa/Cairo")).hour < 5
        except Exception:  # context is best-effort; neutral defaults for anything unavailable
            import logging

            logging.getLogger(__name__).exception("layer3_context_build_partial")
        return layer3_engine.assess(ctx)

    async def _block_and_escalate(
        self,
        *,
        layer3: "layer3_engine.Layer3Decision",
        sender_customer: Customer,
        sender_account: Account,
        recipient_account: Account,
        recipient_customer: Customer,
        amount: Decimal,
        currency: str,
        reason: str,
    ) -> None:
        """Do NOT move funds. Record the blocked attempt, open alert + investigation ticket, raise 403."""
        now = datetime.now(UTC)
        txn_ref = f"TXN-BLK-{secrets.token_hex(4).upper()}"
        score = Decimal(str(max(layer3.score, 71.0)))
        txn = Transaction(
            external_id=txn_ref,
            account_id=sender_account.id,
            recipient_account_id=recipient_account.id,
            amount=amount,
            currency=currency.upper(),
            transaction_type="CUSTOMER_TRANSFER",
            status="BLOCKED",
            timestamp=now,
            risk_score=score,
            risk_level="CRITICAL" if score >= Decimal("90") else "HIGH",
            review_status="REQUIRES_REVIEW",
            txn_metadata={"layer3": layer3.to_dict(), "block_reason": reason},
        )
        self.session.add(txn)
        await self.session.flush()

        assessment = RiskAssessment(
            external_id=f"RA-{secrets.token_hex(4).upper()}",
            transaction_id=txn.id,
            risk_score=score,
            risk_level=txn.risk_level,
            requires_human_review=True,
            correlation_id=f"CORR-{txn_ref}",
            summary=f"Layer 3 {reason}: score {layer3.score} ({layer3.tier}), typology {layer3.typology}.",
        )
        self.session.add(assessment)
        await self.session.flush()
        for r in layer3.reasons[:8]:
            self.session.add(
                RiskSignal(
                    assessment_id=assessment.id,
                    signal_name="L3_RULE_SIGNAL",
                    severity="HIGH",
                    description=r["reason"],
                    source="FRAUDGUARD_RULES",
                )
            )
        self.session.add(
            Alert(
                external_id=f"ALT-{secrets.token_hex(4).upper()}",
                transaction_id=txn.id,
                alert_type="LAYER3_TRANSFER_BLOCKED",
                risk_score=score,
                risk_level=txn.risk_level,
                status="OPEN",
            )
        )
        try:
            from domain.services.ticket_service import TicketService

            await TicketService(self.session).create_ticket(
                customer=sender_customer,
                title=f"Layer 3 Block: transfer {txn_ref} ({layer3.typology})",
                description=(
                    f"Transfer of {amount:,.2f} {currency} to {recipient_customer.omerta_user_number} "
                    f"was blocked ({reason}). Score {layer3.score}. "
                    f"Typology signals: {'; '.join(layer3.typology_reasons) or 'none'}."
                ),
                ticket_type="RISK_REVIEW",
                priority_override="CRITICAL" if score >= Decimal("90") else "HIGH",
                related_account_id=sender_account.id,
                related_risk_assessment_id=assessment.external_id,
                opened_by="SYSTEM",
            )
        except Exception:
            pass
        self.session.add(
            AuditEvent(
                event_id=f"EVT-{secrets.token_hex(6).upper()}",
                event_type="TRANSFER_BLOCKED_LAYER3",
                actor_type="SYSTEM",
                actor_id="layer3_engine",
                source="TransferService",
                transaction_id=txn_ref,
                metadata_={"reason": reason, **layer3.to_dict(), "amount": str(amount), "currency": currency},
            )
        )
        await self.session.commit()
        raise TransferError(
            "This transfer was blocked by our fraud-protection system and has been sent to our "
            "security team for review. No funds were moved.",
            code="TRANSFER_BLOCKED_HIGH_RISK",
            status_code=403,
            details={"reference": txn_ref, "risk_score": float(score), "tier": layer3.tier,
                     "typology": layer3.typology, "reason": reason},
        )

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
