"""Customer Application Service for Omerta.ai.

Manages customer profiles, registration, account opening with auditable demo ledger entries,
unique Omerta User Number generation, session tracking with privacy consent, and customer-scoped data isolation.
"""

from datetime import UTC, datetime
from decimal import Decimal
import random
import secrets
from typing import Any
import uuid

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import (
    Account,
    AccountLedgerEntry,
    AuditEvent,
    Customer,
    Device,
    IPAddress,
    InvestigationCase,
    Session,
    Transaction,
    User,
)
from infrastructure.security.jwt_auth import hash_password


class CustomerService:
    """Service layer for banking customer records, registration, and 360-degree profiles."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def generate_omerta_user_number() -> str:
        """Generate a unique, non-sensitive Omerta User Number (e.g. OMR-7842-1950)."""
        part1 = random.randint(1000, 9999)
        part2 = random.randint(1000, 9999)
        return f"OMR-{part1}-{part2}"

    async def register_customer(
        self,
        *,
        full_name: str,
        email: str,
        username: str,
        password: str,
        phone: str = "",
        country: str = "EG",
        preferred_currency: str = "EGP",
        initial_balance: Decimal = Decimal("10000.00"),
        device_consent: bool = True,
        user_agent: str | None = None,
        ip_address: str | None = "192.168.1.50",
    ) -> dict[str, Any]:
        """Register a new banking customer with a demo account, opening balance, phone, and unique user number."""
        clean_email = email.strip().lower()
        clean_username = username.strip().lower()
        clean_phone = phone.strip()
        clean_name = full_name.strip()

        # 1. Enforce Terms of Service, Privacy Policy & Device Consent
        if not device_consent:
            raise ValueError(
                "You must accept the Banking Terms of Service, Privacy Policy, and Device Security Consent to create an account."
            )

        # 2. Check existing user by email
        existing_email = await self.session.scalar(
            select(User).where(User.email == clean_email).limit(1)
        )
        if existing_email:
            raise ValueError(f"A user with email '{clean_email}' already exists. Please sign in or use another email.")

        # 3. Check existing user by username
        existing_username = await self.session.scalar(
            select(User).where(User.username == clean_username).limit(1)
        )
        if existing_username:
            raise ValueError(f"A user with username '{clean_username}' already exists. Please choose a different username.")

        # 4. Check existing customer by registered phone number
        if clean_phone:
            import re
            clean_digits = re.sub(r"[^\d+]", "", clean_phone)
            pure_digits = re.sub(r"\D", "", clean_phone)
            phone_conds = [Customer.phone == clean_phone]
            if clean_digits:
                phone_conds.append(Customer.phone == clean_digits)
            if pure_digits and len(pure_digits) >= 6:
                phone_conds.append(and_(Customer.phone != "", Customer.phone.ilike(f"%{pure_digits[-8:]}%")))

            existing_phone = await self.session.scalar(
                select(Customer).where(or_(*phone_conds)).limit(1)
            )
            if existing_phone:
                raise ValueError(f"A customer profile with mobile phone '{clean_phone}' is already registered.")

        # 5. Check existing customer by full legal name
        existing_name = await self.session.scalar(
            select(Customer).where(func.lower(Customer.name) == clean_name.lower()).limit(1)
        )
        if existing_name:
            raise ValueError(f"A customer profile with the legal name '{clean_name}' already exists in the system.")

        # Ensure unique user number
        for _ in range(10):
            candidate_number = self.generate_omerta_user_number()
            collision = await self.session.scalar(
                select(Customer).where(Customer.omerta_user_number == candidate_number).limit(1)
            )
            if not collision:
                omerta_number = candidate_number
                break
        else:
            omerta_number = f"OMR-{secrets.token_hex(4).upper()}"

        user_ext_id = f"USR-{secrets.token_hex(4).upper()}"
        cust_ext_id = f"CUST-{secrets.token_hex(4).upper()}"
        acc_ext_id = f"ACC-{secrets.token_hex(4).upper()}"
        dev_ext_id = f"DEV-{secrets.token_hex(4).upper()}"
        sess_ext_id = f"SESS-{secrets.token_hex(4).upper()}"

        now = datetime.now(UTC)

        # 1. Create User
        user = User(
            external_id=user_ext_id,
            username=clean_username,
            email=clean_email,
            hashed_password=hash_password(password),
            full_name=clean_name,
            role="CUSTOMER",
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()

        # 2. Create Customer Profile
        customer = Customer(
            external_id=cust_ext_id,
            omerta_user_number=omerta_number,
            user_id=user.id,
            name=full_name.strip(),
            customer_type="INDIVIDUAL",
            email=clean_email,
            phone=clean_phone,
            country=country.upper()[:2],
            declared_country=country.upper()[:2],
            observed_country=country.upper()[:2],
            preferred_currency=preferred_currency.upper()[:3],
            device_consent=device_consent,
            device_consent_at=now if device_consent else None,
            status="ACTIVE",
            risk_level="LOW",
            registration_date=now,
        )
        self.session.add(customer)
        await self.session.flush()

        # 3. Create Opening Demo Account
        account = Account(
            external_id=acc_ext_id,
            customer_id=customer.id,
            customer_name=full_name.strip(),
            account_type="CHECKING",
            currency=preferred_currency.upper()[:3],
            balance=initial_balance,
            country=country.upper()[:2],
            status="ACTIVE",
            risk_level="LOW",
        )
        self.session.add(account)
        await self.session.flush()

        # 4. Record Immutable Opening Balance in Ledger
        ledger_entry = AccountLedgerEntry(
            external_id=f"LED-OPEN-{secrets.token_hex(4).upper()}",
            account_id=account.id,
            entry_type="OPENING_BALANCE",
            amount=initial_balance,
            currency=preferred_currency.upper()[:3],
            balance_after=initial_balance,
            description=f"Initial demo balance set during customer registration ({initial_balance:,.2f} {preferred_currency.upper()})",
            idempotency_key=f"OPENING-{cust_ext_id}",
        )
        self.session.add(ledger_entry)

        # 5. Record Initial Device, IP & Session if consent granted
        if device_consent:
            dev_info = self.parse_device_info(user_agent)
            
            # Find or create IP
            ip_clean = ip_address or "127.0.0.1"
            ip_rec = await self.session.scalar(
                select(IPAddress).where(IPAddress.address == ip_clean).limit(1)
            )
            if not ip_rec:
                ip_rec = IPAddress(
                    address=ip_clean,
                    country=country.upper()[:2],
                    is_vpn=False,
                    is_proxy=False,
                    is_datacenter=False,
                    first_seen_at=now,
                    last_seen_at=now,
                    risk_level="LOW",
                )
                self.session.add(ip_rec)
                await self.session.flush()

            device = Device(
                external_id=dev_ext_id,
                device_type=dev_info["device_type"],
                platform=dev_info["platform"],
                user_agent=user_agent or "Mozilla/5.0 (X11; Linux x86_64)",
                first_seen_at=now,
                last_seen_at=now,
                risk_level="LOW",
            )
            self.session.add(device)
            await self.session.flush()

            session_rec = Session(
                external_id=sess_ext_id,
                user_id=user.id,
                customer_id=customer.id,
                account_id=account.id,
                device_id=device.id,
                ip_address_id=ip_rec.id,
                user_agent=user_agent or "Mozilla/5.0 (X11; Linux x86_64)",
                is_vpn=False,
                is_emulator=False,
                is_active=True,
                started_at=now,
            )
            self.session.add(session_rec)

        # 6. Audit Event
        audit_event = AuditEvent(
            event_id=f"EVT-{secrets.token_hex(6).upper()}",
            event_type="CUSTOMER_REGISTERED",
            actor_type="CUSTOMER",
            actor_id=user_ext_id,
            source="CustomerService",
            metadata_={
                "customer_id": cust_ext_id,
                "omerta_user_number": omerta_number,
                "initial_balance": str(initial_balance),
                "currency": preferred_currency.upper()[:3],
                "device_consent": device_consent,
            },
        )
        self.session.add(audit_event)
        await self.session.commit()

        return {
            "user": {
                "id": user.external_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
            },
            "customer": {
                "id": customer.external_id,
                "name": customer.name,
                "omerta_user_number": customer.omerta_user_number,
                "declared_country": customer.declared_country,
                "preferred_currency": customer.preferred_currency,
                "device_consent": customer.device_consent,
            },
            "session_id": sess_ext_id if device_consent else None,
            "account": {
                "account_id": account.external_id,
                "currency": account.currency,
                "balance": float(account.balance),
                "status": account.status,
            },
        }

    async def get_customer_by_user_id(self, user_id: int | str) -> Customer | None:
        """Fetch Customer profile by User ID (integer PK or external_id)."""
        if isinstance(user_id, int):
            stmt = (
                select(Customer)
                .options(selectinload(Customer.accounts), selectinload(Customer.user))
                .where(Customer.user_id == user_id)
                .limit(1)
            )
        else:
            stmt = (
                select(Customer)
                .options(selectinload(Customer.accounts), selectinload(Customer.user))
                .join(User, Customer.user_id == User.id)
                .where(User.external_id == user_id)
                .limit(1)
            )
        return await self.session.scalar(stmt)

    async def get_customer_dashboard_overview(self, user_id: int | str) -> dict[str, Any]:
        """Fetch personalized customer dashboard metrics and activity."""
        customer = await self.get_customer_by_user_id(user_id)
        if not customer:
            raise ValueError("Customer profile not found for authenticated user.")

        # Customer accounts
        accounts = customer.accounts or []
        account_summaries = []
        total_balance_by_currency: dict[str, Decimal] = {}

        for acc in accounts:
            curr = acc.currency
            total_balance_by_currency[curr] = total_balance_by_currency.get(curr, Decimal("0.00")) + acc.balance
            account_summaries.append({
                "account_id": acc.external_id,
                "account_type": acc.account_type,
                "currency": acc.currency,
                "balance": float(acc.balance),
                "status": acc.status,
                "created_at": acc.created_at.isoformat() if acc.created_at else None,
            })

        account_ids = [acc.id for acc in accounts]

        # Recent transactions (scoped to customer accounts)
        recent_txns = []
        incoming_volume = Decimal("0.00")
        outgoing_volume = Decimal("0.00")
        incoming_count = 0
        outgoing_count = 0

        if account_ids:
            txns_query = (
                select(Transaction)
                .options(
                    selectinload(Transaction.account),
                    selectinload(Transaction.recipient_account),
                )
                .where(
                    or_(
                        Transaction.account_id.in_(account_ids),
                        Transaction.recipient_account_id.in_(account_ids),
                    )
                )
                .order_by(Transaction.timestamp.desc())
                .limit(20)
            )
            rows = (await self.session.scalars(txns_query)).all()

            for t in rows:
                is_outgoing = t.account_id in account_ids
                is_incoming = t.recipient_account_id in account_ids

                if is_outgoing:
                    outgoing_volume += t.amount
                    outgoing_count += 1
                if is_incoming:
                    incoming_volume += t.amount
                    incoming_count += 1

                counterparty = t.recipient_account.customer_name if is_outgoing else t.account.customer_name

                recent_txns.append({
                    "transaction_id": t.external_id,
                    "direction": "OUTGOING" if is_outgoing else "INCOMING",
                    "counterparty": counterparty,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "status": t.status,
                    "timestamp": t.timestamp.isoformat(),
                    "type": t.transaction_type,
                })

        return {
            "customer": {
                "name": customer.name,
                "omerta_user_number": customer.omerta_user_number,
                "email": customer.email,
                "country": customer.declared_country or customer.country,
                "preferred_currency": customer.preferred_currency,
                "status": customer.status,
                "member_since": customer.registration_date.isoformat(),
            },
            "accounts": account_summaries,
            "balances": {k: float(v) for k, v in total_balance_by_currency.items()},
            "activity": {
                "incoming_volume": float(incoming_volume),
                "outgoing_volume": float(outgoing_volume),
                "incoming_count": incoming_count,
                "outgoing_count": outgoing_count,
                "total_transactions": incoming_count + outgoing_count,
            },
            "recent_transactions": recent_txns[:10],
            "demo_notice": "Omerta.ai is an intelligent demo simulation platform. All account balances and transactions are simulated.",
        }

    async def get_customer_accounts(self, user_id: int | str) -> list[dict[str, Any]]:
        """Get all accounts owned by the authenticated customer with ledger metadata."""
        customer = await self.get_customer_by_user_id(user_id)
        if not customer:
            return []

        stmt = (
            select(Account)
            .options(selectinload(Account.ledger_entries))
            .where(Account.customer_id == customer.id)
            .order_by(Account.id.asc())
        )
        accounts = (await self.session.scalars(stmt)).all()

        results = []
        for acc in accounts:
            recent_ledger = []
            for entry in (acc.ledger_entries or [])[:5]:
                recent_ledger.append({
                    "entry_id": entry.external_id,
                    "entry_type": entry.entry_type,
                    "amount": float(entry.amount),
                    "currency": entry.currency,
                    "balance_after": float(entry.balance_after),
                    "description": entry.description,
                    "created_at": entry.created_at.isoformat(),
                })

            results.append({
                "id": acc.id,
                "account_id": acc.external_id,
                "account_type": acc.account_type,
                "currency": acc.currency,
                "balance": float(acc.balance),
                "formatted_balance": f"{acc.balance:,.2f} {acc.currency}",
                "status": acc.status,
                "created_at": acc.created_at.isoformat() if acc.created_at else None,
                "recent_ledger": recent_ledger,
            })
        return results

    async def create_additional_account(
        self,
        *,
        user_id: int | str,
        account_type: str = "SAVINGS",
        currency: str = "EGP",
        initial_balance: Decimal = Decimal("5000.00"),
    ) -> dict[str, Any]:
        """Create an additional demo account for the customer with an auditable opening ledger entry."""
        customer = await self.get_customer_by_user_id(user_id)
        if not customer:
            raise ValueError("Customer profile not found.")

        acc_ext_id = f"ACC-{secrets.token_hex(4).upper()}"
        acc = Account(
            external_id=acc_ext_id,
            customer_id=customer.id,
            customer_name=customer.name,
            account_type=account_type.upper(),
            currency=currency.upper(),
            balance=initial_balance,
            country=customer.declared_country or "EG",
            status="ACTIVE",
            risk_level="LOW",
        )
        self.session.add(acc)
        await self.session.flush()

        ledger_entry = AccountLedgerEntry(
            external_id=f"LED-OPEN-{secrets.token_hex(4).upper()}",
            account_id=acc.id,
            entry_type="OPENING_BALANCE",
            amount=initial_balance,
            currency=currency.upper(),
            balance_after=initial_balance,
            description=f"Opening balance for new {account_type.title()} demo account",
            idempotency_key=f"OPENING-{acc_ext_id}",
        )
        self.session.add(ledger_entry)

        # Audit
        self.session.add(
            AuditEvent(
                event_id=f"EVT-{secrets.token_hex(6).upper()}",
                event_type="ACCOUNT_OPENED",
                actor_type="CUSTOMER",
                actor_id=str(customer.user_id),
                source="CustomerService",
                metadata_={
                    "account_id": acc_ext_id,
                    "currency": currency.upper(),
                    "initial_balance": str(initial_balance),
                },
            )
        )
        await self.session.commit()

        return {
            "account_id": acc.external_id,
            "account_type": acc.account_type,
            "currency": acc.currency,
            "balance": float(acc.balance),
            "status": acc.status,
            "created_at": acc.created_at.isoformat() if acc.created_at else None,
        }

    async def get_customer_transactions(
        self,
        *,
        user_id: int | str,
        search: str | None = None,
        direction: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Fetch transaction history strictly scoped to the authenticated customer."""
        customer = await self.get_customer_by_user_id(user_id)
        if not customer:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

        account_ids = [acc.id for acc in customer.accounts or []]
        if not account_ids:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

        query = select(Transaction).options(
            selectinload(Transaction.account),
            selectinload(Transaction.recipient_account),
        )

        conditions = []
        if direction == "OUTGOING":
            conditions.append(Transaction.account_id.in_(account_ids))
        elif direction == "INCOMING":
            conditions.append(Transaction.recipient_account_id.in_(account_ids))
        else:
            conditions.append(
                or_(
                    Transaction.account_id.in_(account_ids),
                    Transaction.recipient_account_id.in_(account_ids),
                )
            )

        if status:
            conditions.append(Transaction.status == status.upper())

        if search:
            clean = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Transaction.external_id.ilike(clean),
                    Transaction.account.has(Account.customer_name.ilike(clean)),
                    Transaction.recipient_account.has(Account.customer_name.ilike(clean)),
                )
            )

        if conditions:
            query = query.where(and_(*conditions))

        count_q = select(func.count(Transaction.id)).where(and_(*conditions))
        total = await self.session.scalar(count_q) or 0

        query = query.order_by(Transaction.timestamp.desc())
        offset = (max(1, page) - 1) * page_size
        rows = (await self.session.scalars(query.offset(offset).limit(page_size))).all()

        items = []
        for t in rows:
            is_outgoing = t.account_id in account_ids
            counterparty = t.recipient_account.customer_name if is_outgoing else t.account.customer_name
            items.append({
                "transaction_id": t.external_id,
                "direction": "OUTGOING" if is_outgoing else "INCOMING",
                "counterparty": counterparty,
                "amount": float(t.amount),
                "currency": t.currency,
                "status": t.status,
                "timestamp": t.timestamp.isoformat(),
                "type": t.transaction_type,
                "account_number": t.account.external_id if is_outgoing else t.recipient_account.external_id,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }

    @staticmethod
    def parse_device_info(user_agent: str | None) -> dict[str, str]:
        """Accurately parse operating system, browser, and device classification from User-Agent string."""
        if not user_agent:
            return {
                "os": "Linux / Web",
                "browser": "Web Browser",
                "platform": "Linux",
                "device_type": "DESKTOP",
                "label": "Web Browser on Linux",
            }

        ua = user_agent.lower()

        # Operating System
        if "windows nt 10.0" in ua or "windows 11" in ua or "windows 10" in ua:
            os_name = "Windows 11 / 10"
            platform = "Windows"
            dev_type = "DESKTOP"
        elif "windows" in ua:
            os_name = "Windows"
            platform = "Windows"
            dev_type = "DESKTOP"
        elif "iphone" in ua:
            os_name = "iOS (iPhone)"
            platform = "iOS"
            dev_type = "MOBILE"
        elif "ipad" in ua:
            os_name = "iPadOS"
            platform = "iOS"
            dev_type = "TABLET"
        elif "android" in ua:
            os_name = "Android"
            platform = "Android"
            dev_type = "MOBILE"
        elif "macintosh" in ua or "mac os" in ua:
            os_name = "macOS"
            platform = "macOS"
            dev_type = "DESKTOP"
        elif "ubuntu" in ua:
            os_name = "Linux (Ubuntu)"
            platform = "Linux"
            dev_type = "DESKTOP"
        elif "linux" in ua or "x11" in ua:
            os_name = "Linux"
            platform = "Linux"
            dev_type = "DESKTOP"
        else:
            os_name = "Web Client"
            platform = "Web"
            dev_type = "DESKTOP"

        # Browser
        if "edg/" in ua or "edge/" in ua:
            browser = "Microsoft Edge"
        elif "opr/" in ua or "opera" in ua:
            browser = "Opera"
        elif "firefox" in ua or "fxios" in ua:
            browser = "Mozilla Firefox"
        elif "chrome" in ua or "crios" in ua:
            browser = "Google Chrome"
        elif "safari" in ua:
            browser = "Apple Safari"
        else:
            browser = "Web Browser"

        return {
            "os": os_name,
            "browser": browser,
            "platform": platform,
            "device_type": dev_type,
            "label": f"{browser} on {os_name}",
        }

    async def get_customer_sessions(self, user_id: int | str) -> list[dict[str, Any]]:
        """Fetch active and past sessions for security review with accurate OS/Browser and VPN notices."""
        customer = await self.get_customer_by_user_id(user_id)
        if not customer:
            return []

        stmt = (
            select(Session)
            .options(selectinload(Session.device), selectinload(Session.ip_address))
            .where(Session.customer_id == customer.id)
            .order_by(Session.started_at.desc())
            .limit(20)
        )
        sessions = (await self.session.scalars(stmt)).all()

        results = []
        for s in sessions:
            ua_raw = s.user_agent or (s.device.user_agent if s.device else None)
            dev_info = self.parse_device_info(ua_raw)
            device_label = dev_info["label"]
            observed_country = s.ip_address.country if s.ip_address else (customer.declared_country or "EG")
            ip_address = s.ip_address.address if s.ip_address else "127.0.0.1"
            is_vpn = s.is_vpn or (s.ip_address.is_vpn if s.ip_address else False)

            if is_vpn:
                notice = f"🛡️ VPN / Proxy Connection Active: This session is routed through an encrypted VPN / Proxy gateway (Exit Node: {observed_country}). Real-time network telemetry detected an external proxy tunnel or datacenter ASN."
            elif observed_country != (customer.declared_country or "EG"):
                notice = f"⚠️ Location Anomaly: Sign-in observed from {observed_country}, differing from your registered home country ({customer.declared_country or 'EG'})."
            else:
                notice = f"🌐 Direct Verified Connection: Connected directly via authorized ISP in Egypt ({observed_country}). No proxy tunnels or VPN anonymizers detected."

            results.append({
                "session_id": s.external_id,
                "device_label": device_label,
                "browser": dev_info["browser"],
                "os": dev_info["os"],
                "platform": dev_info["platform"],
                "ip_address": ip_address,
                "user_agent": s.user_agent,
                "observed_country": observed_country,
                "is_vpn": is_vpn,
                "is_active": s.is_active,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "security_notice": notice,
            })

        return results

    async def revoke_session(self, user_id: int | str, session_id: str) -> bool:
        """Revoke an active customer session."""
        customer = await self.get_customer_by_user_id(user_id)
        if not customer:
            return False

        stmt = select(Session).where(
            and_(Session.external_id == session_id, Session.customer_id == customer.id)
        )
        session_rec = await self.session.scalar(stmt)
        if not session_rec:
            return False

        session_rec.is_active = False
        session_rec.revoked_at = datetime.now(UTC)
        await self.session.commit()
        return True

    async def update_device_consent(self, user_id: int | str, consent: bool) -> bool:
        """Update customer device & session telemetry consent setting."""
        customer = await self.get_customer_by_user_id(user_id)
        if not customer:
            return False

        customer.device_consent = consent
        customer.device_consent_at = datetime.now(UTC) if consent else None
        await self.session.commit()
        return True

    async def record_login_session(
        self,
        *,
        user: User,
        client_ip: str,
        user_agent: str,
        country: str = "EG",
        is_vpn: bool = False,
        force_login: bool = False,
    ) -> tuple[bool, str | None, dict[str, Any]]:
        """Record login telemetry, enforce single active session constraint, and detect multi-accounts on device."""
        now = datetime.now(UTC)

        # 1. Supersede and revoke prior active sessions strictly for THIS user
        active_stmt = (
            select(Session)
            .where(and_(Session.user_id == user.id, Session.is_active.is_(True)))
            .order_by(Session.started_at.desc())
        )
        active_sessions = (await self.session.scalars(active_stmt)).all()

        for s in active_sessions:
            s.is_active = False
            s.ended_at = now
            s.revoked_at = now
        await self.session.flush()

        # 2. Find or create IPAddress
        ip_rec = await self.session.scalar(
            select(IPAddress).where(IPAddress.address == client_ip).limit(1)
        )
        if not ip_rec:
            ip_rec = IPAddress(
                address=client_ip,
                country=country.upper()[:2],
                is_vpn=is_vpn,
                is_proxy=is_vpn,
                is_datacenter=False,
                first_seen_at=now,
                last_seen_at=now,
                risk_level="MEDIUM" if is_vpn else "LOW",
            )
            self.session.add(ip_rec)
            await self.session.flush()
        else:
            ip_rec.last_seen_at = now
            if is_vpn:
                ip_rec.is_vpn = True

        # 3. Detect Platform / Device
        platform = "Web"
        dev_type = "DESKTOP"
        ua_lower = user_agent.lower()
        if "iphone" in ua_lower or "ipad" in ua_lower or "ios" in ua_lower:
            platform = "iOS"
            dev_type = "MOBILE"
        elif "android" in ua_lower:
            platform = "Android"
            dev_type = "MOBILE"
        elif "macintosh" in ua_lower or "mac os" in ua_lower:
            platform = "macOS"
            dev_type = "DESKTOP"
        elif "windows" in ua_lower:
            platform = "Windows"
            dev_type = "DESKTOP"
        elif "linux" in ua_lower:
            platform = "Linux"
            dev_type = "DESKTOP"

        dev_rec = await self.session.scalar(
            select(Device).where(Device.user_agent == user_agent[:255]).limit(1)
        )
        if not dev_rec:
            dev_rec = Device(
                external_id=f"DEV-{secrets.token_hex(4).upper()}",
                device_type=dev_type,
                platform=platform,
                user_agent=user_agent[:255],
                first_seen_at=now,
                last_seen_at=now,
                risk_level="LOW",
            )
            self.session.add(dev_rec)
            await self.session.flush()
        else:
            dev_rec.last_seen_at = now

        # 4. Multi-Account on Same Device / IP Detection
        other_users_stmt = (
            select(Session.user_id)
            .where(
                and_(
                    or_(Session.device_id == dev_rec.id, Session.ip_address_id == ip_rec.id),
                    Session.user_id != user.id,
                )
            )
            .distinct()
        )
        other_user_ids = (await self.session.scalars(other_users_stmt)).all()
        multiple_accounts_detected = len(other_user_ids) > 0

        if multiple_accounts_detected:
            audit = AuditEvent(
                event_id=f"EVT-MULTI-{secrets.token_hex(4).upper()}",
                event_type="MULTIPLE_ACCOUNTS_ON_SAME_DEVICE",
                actor_type=user.role,
                actor_id=user.external_id,
                source="SecurityTelemetry",
                metadata_={
                    "user_id": user.external_id,
                    "ip_address": client_ip,
                    "device_id": dev_rec.external_id,
                    "other_distinct_users_count": len(other_user_ids),
                    "is_vpn": is_vpn,
                },
            )
            self.session.add(audit)

        # 5. Create new Session
        customer_id = user.customer.id if user.customer else None
        first_acc_id = user.customer.accounts[0].id if (user.customer and user.customer.accounts) else None
        session_rec = Session(
            external_id=f"SESS-{secrets.token_hex(4).upper()}",
            user_id=user.id,
            customer_id=customer_id,
            account_id=first_acc_id,
            device_id=dev_rec.id,
            ip_address_id=ip_rec.id,
            user_agent=user_agent[:255],
            is_vpn=is_vpn,
            is_emulator=False,
            is_active=True,
            started_at=now,
        )
        self.session.add(session_rec)
        await self.session.commit()

        return (
            True,
            None,
            {
                "session_id": session_rec.external_id,
                "ip_address": client_ip,
                "country": ip_rec.country,
                "platform": dev_rec.platform,
                "device_type": dev_rec.device_type,
                "is_vpn": is_vpn,
                "multiple_accounts_detected": multiple_accounts_detected,
            },
        )

    async def update_telemetry_heartbeat(
        self,
        *,
        user_identifier: int | str,
        client_ip: str,
        country: str = "EG",
        is_vpn: bool = False,
        user_agent: str | None = None,
        isp: str | None = None,
        org: str | None = None,
        browser_timezone: str | None = None,
        ip_timezone: str | None = None,
    ) -> dict[str, Any]:
        """Periodically (every 30s) process live client network telemetry, update active sessions, and enforce VPN security policies."""
        now = datetime.now(UTC)

        # 1. Resolve User
        clean_ident = str(user_identifier).strip()
        stmt = (
            select(User)
            .options(selectinload(User.customer))
            .where(
                (User.external_id == clean_ident)
                | (User.username == clean_ident.lower())
                | (User.email == clean_ident.lower())
                | ((User.id == int(clean_ident)) if clean_ident.isdigit() else False)
            )
        )
        user = await self.session.scalar(stmt)
        if not user:
            return {"success": False, "error": "USER_NOT_FOUND", "message": "User not found."}

        is_staff_or_admin = user.role in [
            "ADMINISTRATOR",
            "SUB_ADMINISTRATOR",
            "FRAUD_ANALYST",
            "SENIOR_INVESTIGATOR",
            "AUDITOR",
            "COMPLIANCE_AUDITOR",
        ]

        # 2. Enforce Admin VPN Lockout / Auto-unlock
        if is_staff_or_admin:
            if is_vpn:
                user.is_active = False
                # Terminate active sessions
                active_sessions = (
                    await self.session.scalars(
                        select(Session).where(Session.user_id == user.id, Session.is_active.is_(True))
                    )
                ).all()
                for sess in active_sessions:
                    sess.is_active = False
                    sess.ended_at = now
                    sess.revoked_at = now

                audit = AuditEvent(
                    event_id=f"EVT-VPN-LOCK-30S-{secrets.token_hex(4).upper()}",
                    event_type="ADMIN_VPN_SECURITY_LOCK",
                    actor_type=user.role,
                    actor_id=user.external_id,
                    source="Periodic30sTelemetryHeartbeat",
                    metadata_={
                        "user_id": user.external_id,
                        "ip_address": client_ip,
                        "country": country,
                        "isp": isp,
                        "trigger": "30_SECOND_RECURRING_TELEMETRY_CHECK",
                        "reason": "Commercial VPN / Proxy active on administrative connection.",
                    },
                )
                self.session.add(audit)
                await self.session.commit()
                return {
                    "success": True,
                    "status": "LOCKED",
                    "locked": True,
                    "error": "ADMIN_VPN_SECURITY_LOCK",
                    "message": "Security Alert: VPN/Proxy connection detected during 30s telemetry check. Administrator account locked and active session terminated.",
                }
            elif not user.is_active:
                # Connected with clean normal IP without VPN -> Auto unlock!
                user.is_active = True
                audit = AuditEvent(
                    event_id=f"EVT-CLEAN-UNLOCK-30S-{secrets.token_hex(4).upper()}",
                    event_type="ADMIN_ACCOUNT_AUTO_UNLOCKED",
                    actor_type=user.role,
                    actor_id=user.external_id,
                    source="Periodic30sTelemetryHeartbeat",
                    metadata_={
                        "user_id": user.external_id,
                        "ip_address": client_ip,
                        "country": country,
                        "trigger": "30_SECOND_RECURRING_TELEMETRY_CHECK",
                        "reason": "Clean non-VPN IP connection restored.",
                    },
                )
                self.session.add(audit)

        # 3. Find or create IPAddress
        clean_country = (country or "EG").upper()[:2]
        ip_rec = await self.session.scalar(
            select(IPAddress).where(IPAddress.address == client_ip).limit(1)
        )
        if not ip_rec:
            ip_rec = IPAddress(
                address=client_ip,
                country=clean_country,
                is_vpn=is_vpn,
                is_proxy=is_vpn,
                is_datacenter=False,
                first_seen_at=now,
                last_seen_at=now,
                risk_level="MEDIUM" if is_vpn else "LOW",
            )
            self.session.add(ip_rec)
            await self.session.flush()
        else:
            ip_rec.last_seen_at = now
            ip_rec.country = clean_country
            ip_rec.is_vpn = is_vpn

        # 4. Find active session for user and update telemetry
        sess_stmt = (
            select(Session)
            .options(selectinload(Session.device), selectinload(Session.ip_address))
            .where(Session.user_id == user.id, Session.is_active.is_(True))
            .order_by(Session.started_at.desc())
            .limit(1)
        )
        active_sess = await self.session.scalar(sess_stmt)

        if active_sess:
            active_sess.ip_address_id = ip_rec.id
            active_sess.is_vpn = is_vpn
            if user_agent:
                active_sess.user_agent = user_agent[:255]
                if active_sess.device:
                    active_sess.device.last_seen_at = now
                    active_sess.device.user_agent = user_agent[:255]

        # 5. Update Customer observed country if customer
        if user.customer:
            user.customer.observed_country = clean_country

        await self.session.commit()

        return {
            "success": True,
            "status": "ACTIVE",
            "locked": False,
            "session_id": active_sess.external_id if active_sess else None,
            "client_ip": client_ip,
            "country": clean_country,
            "is_vpn": is_vpn,
            "isp": isp,
            "checked_at": now.isoformat(),
            "next_interval_seconds": 30,
        }

    # --- ADMIN QUERIES ---

    async def list_customers(
        self,
        *,
        search: str | None = None,
        customer_type: str | None = None,
        risk_level: str | None = None,
        country: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """Admin view: paginated, searchable list of all customers."""
        query = select(Customer).options(selectinload(Customer.accounts))

        conditions = []
        if search:
            clean = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Customer.external_id.ilike(clean),
                    Customer.omerta_user_number.ilike(clean),
                    Customer.name.ilike(clean),
                    Customer.email.ilike(clean),
                    Customer.phone.ilike(clean),
                )
            )
        if customer_type:
            conditions.append(Customer.customer_type == customer_type.upper())
        if risk_level:
            conditions.append(Customer.risk_level == risk_level.upper())
        if country:
            conditions.append(Customer.country == country.upper())

        if conditions:
            query = query.where(*conditions)

        count_q = select(func.count(Customer.id))
        if conditions:
            count_q = count_q.where(*conditions)
        total = await self.session.scalar(count_q) or 0

        offset = (max(1, page) - 1) * page_size
        query = query.order_by(Customer.id.asc()).offset(offset).limit(page_size)

        customers = (await self.session.scalars(query)).all()

        items = []
        for c in customers:
            items.append({
                "id": c.id,
                "external_id": c.external_id,
                "omerta_user_number": c.omerta_user_number,
                "name": c.name,
                "customer_type": c.customer_type,
                "email": c.email,
                "phone": c.phone,
                "country": c.country,
                "status": c.status,
                "risk_level": c.risk_level,
                "account_count": len(c.accounts),
                "registration_date": c.registration_date.isoformat(),
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }

    async def get_customer_360(self, identifier: str) -> dict[str, Any] | None:
        """Admin view: 360-degree customer profile."""
        clean = identifier.strip()
        stmt = (
            select(Customer)
            .options(
                selectinload(Customer.accounts),
                selectinload(Customer.sessions).selectinload(Session.device),
                selectinload(Customer.sessions).selectinload(Session.ip_address),
            )
            .where(
                or_(
                    Customer.external_id == clean,
                    Customer.omerta_user_number == clean,
                )
            )
            .limit(1)
        )
        c = await self.session.scalar(stmt)
        if not c:
            return None

        accounts = []
        for acc in c.accounts:
            accounts.append({
                "id": acc.id,
                "external_id": acc.external_id,
                "type": acc.account_type,
                "currency": acc.currency,
                "balance": float(acc.balance),
                "status": acc.status,
                "risk_level": acc.risk_level,
                "created_at": acc.created_at.isoformat() if acc.created_at else None,
            })

        return {
            "customer": {
                "id": c.id,
                "external_id": c.external_id,
                "omerta_user_number": c.omerta_user_number,
                "name": c.name,
                "customer_type": c.customer_type,
                "email": c.email,
                "phone": c.phone,
                "country": c.country,
                "declared_country": c.declared_country,
                "observed_country": c.observed_country,
                "preferred_currency": c.preferred_currency,
                "device_consent": c.device_consent,
                "status": c.status,
                "risk_level": c.risk_level,
                "registration_date": c.registration_date.isoformat(),
            },
            "accounts": accounts,
            "total_accounts": len(accounts),
            "total_balance_egp": sum(a["balance"] for a in accounts if a["currency"] == "EGP"),
            "total_balance_usd": sum(a["balance"] for a in accounts if a["currency"] == "USD"),
        }
