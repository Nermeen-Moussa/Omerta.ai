"""Deterministic seed data for local development and testing.

Idempotent by design: every row is upserted on its natural business key
(``external_id`` / ``address``), so running the seed twice never creates
duplicates. Optional ``--reset`` truncates all tables first.

Includes:
- Admin and analyst users (admin@omerta.ai, analyst@omerta.ai, investigator@omerta.ai, auditor@omerta.ai)
- Interactive demo customers with user accounts and Omerta User Numbers:
    * Ziad Karim (ziad@omerta.ai / Customer@2026!, OMR-1092-4821, 50,000 EGP)
    * Layla Hassan (layla@omerta.ai / Customer@2026!, OMR-3847-1920, 25,000 EGP)
    * Amira El-Sayed (amira@omerta.ai / Customer@2026!, OMR-7193-8402, 120,000 EGP)
    * Omar Farouk (omar@omerta.ai / Customer@2026!, OMR-9481-5632, 15,000 EGP)
    * Nour Mansour (nour@omerta.ai / Customer@2026!, OMR-5238-7104, 80,000 EGP)
- Complete double-entry ledger entries for opening balances and transfers
- Multi-tier risk assessments (> 40.00 human review rule) and audit trail.

Run: ``uv run python -m infrastructure.database.seed [--reset]``
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from domain.evidence import content_hash
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.database.models import (
    Account,
    AccountLedgerEntry,
    Alert,
    AuditEvent,
    Base,
    CaseDisposition,
    CaseNote,
    Customer,
    Device,
    Evidence,
    InvestigationCase,
    IPAddress,
    KnowledgeChunk,
    KnowledgeDocument,
    RiskAssessment,
    RiskSignal,
    Session,
    Transaction,
    Transfer,
    User,
    init_db,
)
from infrastructure.database.session import create_engine, session_scope
from infrastructure.security.jwt_auth import hash_password

SAFE_DOC_IP = "202.0.113.77"
SAFE_DOC_IP_2 = "198.51.100.23"

_SEED_NOW = datetime.now(UTC)


def _days_ago(days: float) -> datetime:
    return _SEED_NOW - timedelta(days=days)


USERS: list[dict[str, Any]] = [
    {
        "external_id": "USR-1001",
        "username": "analyst@omerta.ai",
        "email": "analyst@omerta.ai",
        "hashed_password": hash_password("AnalystPass123!"),
        "full_name": "Tariq Mansour",
        "role": "FRAUD_ANALYST",
    },
    {
        "external_id": "USR-1002",
        "username": "admin@omerta.ai",
        "email": "admin@omerta.ai",
        "hashed_password": hash_password("AdminPass123!"),
        "full_name": "Dr. Sarah Al-Rashid",
        "role": "ADMINISTRATOR",
    },
    {
        "external_id": "USR-1003",
        "username": "investigator@omerta.ai",
        "email": "investigator@omerta.ai",
        "hashed_password": hash_password("InvestigatorPass123!"),
        "full_name": "Laila El-Kady",
        "role": "SENIOR_INVESTIGATOR",
    },
    {
        "external_id": "USR-1004",
        "username": "auditor@omerta.ai",
        "email": "auditor@omerta.ai",
        "hashed_password": hash_password("AuditorPass123!"),
        "full_name": "Omar Farooq",
        "role": "AUDITOR",
    },
    # Demo Customer Users
    {
        "external_id": "USR-CUST-1",
        "username": "ziad@omerta.ai",
        "email": "ziad@omerta.ai",
        "hashed_password": hash_password("Customer@2026!"),
        "full_name": "Ziad Karim",
        "role": "CUSTOMER",
    },
    {
        "external_id": "USR-CUST-2",
        "username": "layla@omerta.ai",
        "email": "layla@omerta.ai",
        "hashed_password": hash_password("Customer@2026!"),
        "full_name": "Layla Hassan",
        "role": "CUSTOMER",
    },
    {
        "external_id": "USR-CUST-3",
        "username": "amira@omerta.ai",
        "email": "amira@omerta.ai",
        "hashed_password": hash_password("Customer@2026!"),
        "full_name": "Amira El-Sayed",
        "role": "CUSTOMER",
    },
    {
        "external_id": "USR-CUST-4",
        "username": "omar@omerta.ai",
        "email": "omar@omerta.ai",
        "hashed_password": hash_password("Customer@2026!"),
        "full_name": "Omar Farouk",
        "role": "CUSTOMER",
    },
    {
        "external_id": "USR-CUST-5",
        "username": "nour@omerta.ai",
        "email": "nour@omerta.ai",
        "hashed_password": hash_password("Customer@2026!"),
        "full_name": "Nour Mansour",
        "role": "CUSTOMER",
    },
]

CUSTOMERS: list[dict[str, Any]] = [
    {
        "external_id": "CUST-1001",
        "omerta_user_number": "OMR-1092-4821",
        "user_external_id": "USR-CUST-1",
        "name": "Ziad Karim",
        "customer_type": "INDIVIDUAL",
        "email": "ziad@omerta.ai",
        "phone": "+201011112222",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "LOW",
        "registration_date": _days_ago(120),
    },
    {
        "external_id": "CUST-2001",
        "omerta_user_number": "OMR-3847-1920",
        "user_external_id": "USR-CUST-2",
        "name": "Layla Hassan",
        "customer_type": "INDIVIDUAL",
        "email": "layla@omerta.ai",
        "phone": "+201022223333",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "LOW",
        "registration_date": _days_ago(90),
    },
    {
        "external_id": "CUST-3001",
        "omerta_user_number": "OMR-7193-8402",
        "user_external_id": "USR-CUST-3",
        "name": "Amira El-Sayed",
        "customer_type": "INDIVIDUAL",
        "email": "amira@omerta.ai",
        "phone": "+201033334444",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "LOW",
        "registration_date": _days_ago(150),
    },
    {
        "external_id": "CUST-4001",
        "omerta_user_number": "OMR-9481-5632",
        "user_external_id": "USR-CUST-4",
        "name": "Omar Farouk",
        "customer_type": "INDIVIDUAL",
        "email": "omar@omerta.ai",
        "phone": "+201044445555",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "MEDIUM",
        "registration_date": _days_ago(40),
    },
    {
        "external_id": "CUST-5001",
        "omerta_user_number": "OMR-5238-7104",
        "user_external_id": "USR-CUST-5",
        "name": "Nour Mansour",
        "customer_type": "BUSINESS",
        "email": "nour@omerta.ai",
        "phone": "+201055556666",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "HIGH",
        "registration_date": _days_ago(10),
    },
]

ACCOUNTS: list[dict[str, Any]] = [
    {
        "external_id": "ACC-1001",
        "customer_external_id": "CUST-1001",
        "customer_name": "Ziad Karim",
        "account_type": "CHECKING",
        "currency": "EGP",
        "balance": Decimal("50000.00"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "LOW",
        "created_at": _days_ago(120),
    },
    {
        "external_id": "ACC-2001",
        "customer_external_id": "CUST-2001",
        "customer_name": "Layla Hassan",
        "account_type": "CHECKING",
        "currency": "EGP",
        "balance": Decimal("25000.00"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "LOW",
        "created_at": _days_ago(90),
    },
    {
        "external_id": "ACC-3001",
        "customer_external_id": "CUST-3001",
        "customer_name": "Amira El-Sayed",
        "account_type": "CHECKING",
        "currency": "EGP",
        "balance": Decimal("120000.00"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "LOW",
        "created_at": _days_ago(150),
    },
    {
        "external_id": "ACC-4001",
        "customer_external_id": "CUST-4001",
        "customer_name": "Omar Farouk",
        "account_type": "CHECKING",
        "currency": "EGP",
        "balance": Decimal("15000.00"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "MEDIUM",
        "created_at": _days_ago(40),
    },
    {
        "external_id": "ACC-5001",
        "customer_external_id": "CUST-5001",
        "customer_name": "Nour Mansour",
        "account_type": "BUSINESS",
        "currency": "EGP",
        "balance": Decimal("80000.00"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "HIGH",
        "created_at": _days_ago(10),
    },
]

DEVICES: list[dict[str, Any]] = [
    {
        "external_id": "DEV-101",
        "device_type": "MOBILE",
        "platform": "Android",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Mobile Safari/537.36",
        "first_seen_at": _days_ago(120),
        "last_seen_at": _SEED_NOW,
        "risk_level": "LOW",
    },
    {
        "external_id": "DEV-201",
        "device_type": "DESKTOP",
        "platform": "macOS",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) Safari/605.1.15",
        "first_seen_at": _days_ago(90),
        "last_seen_at": _SEED_NOW,
        "risk_level": "LOW",
    },
    {
        "external_id": "DEV-501",
        "device_type": "MOBILE",
        "platform": "Android",
        "user_agent": "Mozilla/5.0 (Linux; Android 13; Emulator) Safari/537.36",
        "is_emulator": True,
        "is_rooted": True,
        "first_seen_at": _days_ago(10),
        "last_seen_at": _SEED_NOW,
        "risk_level": "HIGH",
    },
]

IP_ADDRESSES: list[dict[str, Any]] = [
    {
        "address": "156.204.12.44",
        "country": "EG",
        "is_vpn": False,
        "first_seen_at": _days_ago(120),
        "last_seen_at": _SEED_NOW,
        "risk_level": "LOW",
    },
    {
        "address": "197.35.88.19",
        "country": "EG",
        "is_vpn": False,
        "first_seen_at": _days_ago(90),
        "last_seen_at": _SEED_NOW,
        "risk_level": "LOW",
    },
    {
        "address": SAFE_DOC_IP,
        "country": "CH",
        "is_vpn": True,
        "first_seen_at": _days_ago(10),
        "last_seen_at": _SEED_NOW,
        "risk_level": "HIGH",
    },
]


async def seed_all(engine: AsyncEngine, *, reset: bool = False) -> None:
    """Execute complete deterministic seed."""
    if reset:
        print("Resetting database schema (drop & recreate all tables)...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    else:
        await init_db(engine)

    async with session_scope(engine) as session:
        # 1. Users
        print("Seeding Users...")
        for u_data in USERS:
            existing = await session.scalar(select(User).where(User.username == u_data["username"]))
            if not existing:
                session.add(User(**u_data))
        await session.flush()

        users_rows = (await session.scalars(select(User))).all()
        user_ext_map = {u.external_id: u.id for u in users_rows}

        # 2. Customers
        print("Seeding Customers with Omerta User Numbers...")
        for c_data in CUSTOMERS:
            c_dict = dict(c_data)
            u_ext = c_dict.pop("user_external_id", None)
            u_id = user_ext_map.get(u_ext) if u_ext else None
            existing = await session.scalar(select(Customer).where(Customer.external_id == c_dict["external_id"]))
            if not existing:
                session.add(Customer(user_id=u_id, **c_dict))
        await session.flush()

        cust_rows = (await session.scalars(select(Customer))).all()
        cust_ext_map = {c.external_id: c.id for c in cust_rows}

        # 3. Devices & IPs
        print("Seeding Devices & IPs...")
        for d_data in DEVICES:
            existing = await session.scalar(select(Device).where(Device.external_id == d_data["external_id"]))
            if not existing:
                session.add(Device(**d_data))

        for ip_data in IP_ADDRESSES:
            existing = await session.scalar(select(IPAddress).where(IPAddress.address == ip_data["address"]))
            if not existing:
                session.add(IPAddress(**ip_data))
        await session.flush()

        dev_rows = (await session.scalars(select(Device))).all()
        dev_ext_map = {d.external_id: d.id for d in dev_rows}
        ip_rows = (await session.scalars(select(IPAddress))).all()
        ip_addr_map = {ip.address: ip.id for ip in ip_rows}

        # 4. Accounts & Opening Ledger Entries
        print("Seeding Accounts with Opening Ledger Entries...")
        for a_data in ACCOUNTS:
            a_dict = dict(a_data)
            c_ext = a_dict.pop("customer_external_id")
            c_id = cust_ext_map[c_ext]

            existing = await session.scalar(select(Account).where(Account.external_id == a_dict["external_id"]))
            if not existing:
                acc = Account(customer_id=c_id, **a_dict)
                session.add(acc)
                await session.flush()

                # Record Opening Balance Ledger Entry
                ledger = AccountLedgerEntry(
                    external_id=f"LED-OPEN-{acc.external_id}",
                    account_id=acc.id,
                    entry_type="OPENING_BALANCE",
                    amount=acc.balance,
                    currency=acc.currency,
                    balance_after=acc.balance,
                    description=f"Opening demo balance for account {acc.external_id}",
                    idempotency_key=f"OPEN-{acc.external_id}",
                )
                session.add(ledger)
        await session.flush()

        acc_rows = (await session.scalars(select(Account))).all()
        acc_ext_map = {a.external_id: a.id for a in acc_rows}

        # 5. Sessions
        print("Seeding Customer Sessions...")
        sessions_data = [
            {
                "external_id": "SESS-1001",
                "customer_id": cust_ext_map["CUST-1001"],
                "account_id": acc_ext_map["ACC-1001"],
                "device_id": dev_ext_map["DEV-101"],
                "ip_address_id": ip_addr_map["156.204.12.44"],
                "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8)",
                "is_vpn": False,
                "is_active": True,
                "started_at": _days_ago(1),
            },
            {
                "external_id": "SESS-2001",
                "customer_id": cust_ext_map["CUST-2001"],
                "account_id": acc_ext_map["ACC-2001"],
                "device_id": dev_ext_map["DEV-201"],
                "ip_address_id": ip_addr_map["197.35.88.19"],
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4)",
                "is_vpn": False,
                "is_active": True,
                "started_at": _days_ago(2),
            },
            {
                "external_id": "SESS-5001",
                "customer_id": cust_ext_map["CUST-5001"],
                "account_id": acc_ext_map["ACC-5001"],
                "device_id": dev_ext_map["DEV-501"],
                "ip_address_id": ip_addr_map[SAFE_DOC_IP],
                "user_agent": "Mozilla/5.0 (Linux; Android 13; Emulator)",
                "is_vpn": True,
                "is_emulator": True,
                "is_active": True,
                "started_at": _days_ago(0.5),
            },
        ]
        for s in sessions_data:
            existing = await session.scalar(select(Session).where(Session.external_id == s["external_id"]))
            if not existing:
                session.add(Session(**s))
        await session.flush()

        # 6. Sample Transactions & Transfers with Multi-tier Risk Assessment
        print("Seeding Sample Transactions, Transfers, and Review Alerts...")
        sample_txns = [
            {
                "external_id": "TXN-001",
                "sender_acc": "ACC-1001",
                "recipient_acc": "ACC-2001",
                "sender_cust": "CUST-1001",
                "recipient_cust": "CUST-2001",
                "amount": Decimal("1500.00"),
                "currency": "EGP",
                "timestamp": _days_ago(5),
                "risk_score": Decimal("12.00"),
                "risk_level": "LOW",
                "review_status": "NOT_REQUIRED",
                "note": "Dinner bill split",
            },
            {
                "external_id": "TXN-002",
                "sender_acc": "ACC-3001",
                "recipient_acc": "ACC-1001",
                "sender_cust": "CUST-3001",
                "recipient_cust": "CUST-1001",
                "amount": Decimal("12500.00"),
                "currency": "EGP",
                "timestamp": _days_ago(3),
                "risk_score": Decimal("22.50"),
                "risk_level": "MODERATE",
                "review_status": "NOT_REQUIRED",
                "note": "Freelance design work",
            },
            {
                "external_id": "TXN-003",
                "sender_acc": "ACC-5001",
                "recipient_acc": "ACC-4001",
                "sender_cust": "CUST-5001",
                "recipient_cust": "CUST-4001",
                "amount": Decimal("65000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(1),
                "risk_score": Decimal("78.50"),  # > 40 triggers human review
                "risk_level": "HIGH",
                "review_status": "REQUIRES_REVIEW",
                "note": "Consulting retainer transfer",
            },
        ]

        for idx, t in enumerate(sample_txns, 1):
            existing_txn = await session.scalar(select(Transaction).where(Transaction.external_id == t["external_id"]))
            if not existing_txn:
                s_acc_id = acc_ext_map[t["sender_acc"]]
                r_acc_id = acc_ext_map[t["recipient_acc"]]
                s_cust_id = cust_ext_map[t["sender_cust"]]
                r_cust_id = cust_ext_map[t["recipient_cust"]]

                txn = Transaction(
                    external_id=t["external_id"],
                    account_id=s_acc_id,
                    recipient_account_id=r_acc_id,
                    amount=t["amount"],
                    currency=t["currency"],
                    transaction_type="CUSTOMER_TRANSFER",
                    status="COMPLETED",
                    timestamp=t["timestamp"],
                    risk_score=t["risk_score"],
                    risk_level=t["risk_level"],
                    review_status=t["review_status"],
                    txn_metadata={"note": t["note"]},
                )
                session.add(txn)
                await session.flush()

                # Transfer record
                trf = Transfer(
                    external_id=f"TRF-{idx:04d}",
                    idempotency_key=f"SEED-IDEMP-{t['external_id']}",
                    sender_customer_id=s_cust_id,
                    sender_account_id=s_acc_id,
                    recipient_customer_id=r_cust_id,
                    recipient_account_id=r_acc_id,
                    amount=t["amount"],
                    currency=t["currency"],
                    note=t["note"],
                    status="COMPLETED",
                    transaction_id=txn.id,
                )
                session.add(trf)
                await session.flush()

                # Double entry ledger
                session.add_all([
                    AccountLedgerEntry(
                        external_id=f"LED-DB-{t['external_id']}",
                        account_id=s_acc_id,
                        transfer_id=trf.id,
                        transaction_id=txn.id,
                        entry_type="DEBIT",
                        amount=t["amount"],
                        currency=t["currency"],
                        balance_after=Decimal("50000.00"),
                        description=f"Transfer to {t['recipient_cust']}",
                    ),
                    AccountLedgerEntry(
                        external_id=f"LED-CR-{t['external_id']}",
                        account_id=r_acc_id,
                        transfer_id=trf.id,
                        transaction_id=txn.id,
                        entry_type="CREDIT",
                        amount=t["amount"],
                        currency=t["currency"],
                        balance_after=Decimal("30000.00"),
                        description=f"Transfer from {t['sender_cust']}",
                    ),
                ])

                # Risk Assessment
                req_rev = t["risk_score"] > Decimal("40.00")
                ra = RiskAssessment(
                    external_id=f"RA-{t['external_id']}",
                    transaction_id=txn.id,
                    risk_score=t["risk_score"],
                    risk_level=t["risk_level"],
                    requires_human_review=req_rev,
                    correlation_id=f"CORR-{t['external_id']}",
                    summary=f"Risk assessment score: {t['risk_score']}%. Human review required: {req_rev}.",
                )
                session.add(ra)
                await session.flush()

                if req_rev:
                    session.add(
                        Alert(
                            external_id=f"ALT-{t['external_id']}",
                            transaction_id=txn.id,
                            alert_type="HIGH_RISK_TRANSFER_REVIEW",
                            risk_score=t["risk_score"],
                            risk_level=t["risk_level"],
                            status="OPEN",
                        )
                    )
        await session.flush()
        print("Deterministic seed complete! All demo customers, ledger entries, and admin workflows ready.")


async def reset_all(engine: AsyncEngine) -> None:
    """Drop and recreate all tables in isolated test/dev database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed(engine: AsyncEngine) -> None:
    """Run deterministic seed without resetting schema."""
    await seed_all(engine, reset=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Omerta.ai database")
    parser.add_argument("--reset", action="store_true", help="Truncate all tables before seeding")
    args = parser.parse_args()

    engine = create_engine()
    asyncio.run(seed_all(engine, reset=args.reset))


if __name__ == "__main__":
    main()
