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
import secrets
from typing import Any

from domain.evidence import content_hash
from sqlalchemy import delete, or_, select
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
    SupportMessage,
    SupportTicket,
    Transaction,
    Transfer,
    TransferRestoration,
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
        "external_id": "USR-CUST-0",
        "username": "mohamed@omerta.ai",
        "email": "mohamed@omerta.ai",
        "hashed_password": hash_password("Customer@2026!"),
        "full_name": "Mohamed El-Sayed",
        "role": "CUSTOMER",
    },
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
        "external_id": "CUST-0001",
        "omerta_user_number": "OMR-0001-2026",
        "user_external_id": "USR-CUST-0",
        "name": "Mohamed El-Sayed",
        "customer_type": "INDIVIDUAL",
        "email": "mohamed@omerta.ai",
        "phone": "+201011112222",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "LOW",
        "registration_date": _days_ago(120),
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29801011234567",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
    },
    {
        "external_id": "CUST-1001",
        "omerta_user_number": "OMR-1092-4821",
        "user_external_id": "USR-CUST-1",
        "name": "Ziad Karim",
        "customer_type": "INDIVIDUAL",
        "email": "ziad@omerta.ai",
        "phone": "+201011113333",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "LOW",
        "registration_date": _days_ago(120),
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29801011987654",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
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
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29902022345678",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
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
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29703033456789",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
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
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29604044567890",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
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
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29505055678901",
        "transfer_status": "ACTIVE",
        "identity_status": "PENDING_REVIEW",
    },
    {
        "external_id": "CUST-6001",
        "omerta_user_number": "OMR-6091-1122",
        "name": "Ahmed Shawky",
        "customer_type": "INDIVIDUAL",
        "email": "ahmed.shawky@omerta.ai",
        "phone": "+201066667777",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "HIGH",
        "registration_date": _days_ago(25),
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29406066789012",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
    },
    {
        "external_id": "CUST-7001",
        "omerta_user_number": "OMR-7788-9900",
        "name": "Kareem Fathy",
        "customer_type": "INDIVIDUAL",
        "email": "kareem.fathy@omerta.ai",
        "phone": "+201077778888",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "CRITICAL",
        "registration_date": _days_ago(15),
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29307077890123",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
    },
    {
        "external_id": "CUST-8001",
        "omerta_user_number": "OMR-8812-3344",
        "name": "Tamer Samy",
        "customer_type": "INDIVIDUAL",
        "email": "tamer.samy@omerta.ai",
        "phone": "+201088889999",
        "country": "EG",
        "declared_country": "EG",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "HIGH",
        "registration_date": _days_ago(20),
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29208088901234",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
    },
    {
        "external_id": "CUST-9001",
        "omerta_user_number": "OMR-9900-4455",
        "name": "Offshore Vault Clearing",
        "customer_type": "CORPORATE",
        "email": "vault@omerta.ai",
        "phone": "+201099990000",
        "country": "CY",
        "declared_country": "CY",
        "preferred_currency": "EGP",
        "device_consent": True,
        "risk_level": "HIGH",
        "registration_date": _days_ago(60),
        "hashed_transfer_password": hash_password("Customer@2026!"),
        "national_id_number": "29109099012345",
        "transfer_status": "ACTIVE",
        "identity_status": "VERIFIED",
    },
]

ACCOUNTS: list[dict[str, Any]] = [
    {
        "external_id": "ACC-0001",
        "customer_external_id": "CUST-0001",
        "customer_name": "Mohamed El-Sayed",
        "account_type": "CHECKING",
        "currency": "EGP",
        "balance": Decimal("122375.70"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "LOW",
        "created_at": _days_ago(120),
    },
    {
        "external_id": "ACC-1001",
        "customer_external_id": "CUST-1001",
        "customer_name": "Ziad Karim",
        "account_type": "SAVINGS",
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
    {
        "external_id": "ACC-6001",
        "customer_external_id": "CUST-6001",
        "customer_name": "Ahmed Shawky",
        "account_type": "CHECKING",
        "currency": "EGP",
        "balance": Decimal("95000.00"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "HIGH",
        "created_at": _days_ago(25),
    },
    {
        "external_id": "ACC-7001",
        "customer_external_id": "CUST-7001",
        "customer_name": "Kareem Fathy",
        "account_type": "CHECKING",
        "currency": "EGP",
        "balance": Decimal("145000.00"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "CRITICAL",
        "created_at": _days_ago(15),
    },
    {
        "external_id": "ACC-8001",
        "customer_external_id": "CUST-8001",
        "customer_name": "Tamer Samy",
        "account_type": "CHECKING",
        "currency": "EGP",
        "balance": Decimal("75000.00"),
        "country": "EG",
        "status": "ACTIVE",
        "risk_level": "HIGH",
        "created_at": _days_ago(20),
    },
    {
        "external_id": "ACC-9001",
        "customer_external_id": "CUST-9001",
        "customer_name": "Offshore Vault Clearing",
        "account_type": "WIRE_CLEARING",
        "currency": "EGP",
        "balance": Decimal("500000.00"),
        "country": "CY",
        "status": "ACTIVE",
        "risk_level": "HIGH",
        "created_at": _days_ago(60),
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
    {
        "external_id": "DEV-0098",
        "device_type": "MOBILE",
        "platform": "Android",
        "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) Safari/537.36",
        "is_emulator": True,
        "is_rooted": True,
        "first_seen_at": _days_ago(30),
        "last_seen_at": _SEED_NOW,
        "risk_level": "CRITICAL",
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
        "address": "197.151.166.183",
        "country": "EG",
        "is_vpn": False,
        "first_seen_at": _days_ago(30),
        "last_seen_at": _SEED_NOW,
        "risk_level": "LOW",
    },
    {
        "address": "198.51.100.23",
        "country": "CH",
        "is_vpn": True,
        "is_datacenter": True,
        "first_seen_at": _days_ago(30),
        "last_seen_at": _SEED_NOW,
        "risk_level": "HIGH",
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
            existing = await session.scalar(
                select(User).where(
                    or_(
                        User.username == u_data["username"],
                        User.email == u_data["email"],
                        User.external_id == u_data["external_id"],
                    )
                )
            )
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
            existing = await session.scalar(
                select(Customer).where(
                    or_(
                        Customer.external_id == c_dict["external_id"],
                        (Customer.user_id == u_id) if u_id else False,
                    )
                )
            )
            if not existing:
                session.add(Customer(user_id=u_id, **c_dict))
            else:
                existing.external_id = c_dict["external_id"]
                existing.omerta_user_number = c_dict["omerta_user_number"]
                if not existing.hashed_transfer_password:
                    existing.hashed_transfer_password = c_dict.get("hashed_transfer_password")
                if not existing.national_id_number:
                    existing.national_id_number = c_dict.get("national_id_number")
                if not existing.transfer_status:
                    existing.transfer_status = "ACTIVE"
                if not existing.identity_status:
                    existing.identity_status = "VERIFIED"
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
                "account_id": acc_ext_map["ACC-0001"],
                "device_id": dev_ext_map["DEV-101"],
                "ip_address_id": ip_addr_map["156.204.12.44"],
                "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8)",
                "is_vpn": False,
                "is_active": True,
                "started_at": _days_ago(1),
            },
            {
                "external_id": "SESS-1002",
                "customer_id": cust_ext_map["CUST-1001"],
                "account_id": acc_ext_map["ACC-0001"],
                "device_id": dev_ext_map["DEV-0098"],
                "ip_address_id": ip_addr_map["197.151.166.183"],
                "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B)",
                "is_vpn": False,
                "is_active": True,
                "started_at": _days_ago(0.8),
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
            {
                "external_id": "SESS-7001",
                "customer_id": cust_ext_map["CUST-7001"],
                "account_id": acc_ext_map["ACC-7001"],
                "device_id": dev_ext_map["DEV-0098"],
                "ip_address_id": ip_addr_map["198.51.100.23"],
                "user_agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B)",
                "is_vpn": True,
                "is_emulator": True,
                "is_active": True,
                "started_at": _days_ago(0.3),
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
                "sender_acc": "ACC-3001",
                "recipient_acc": "ACC-0001",
                "sender_cust": "CUST-3001",
                "recipient_cust": "CUST-1001",
                "device": "DEV-201",
                "ip": "156.204.12.44",
                "amount": Decimal("15000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(5),
                "risk_score": Decimal("12.00"),
                "risk_level": "LOW",
                "review_status": "NOT_REQUIRED",
                "note": "Consulting invoice settlement",
            },
            {
                "external_id": "TXN-002",
                "sender_acc": "ACC-2001",
                "recipient_acc": "ACC-0001",
                "sender_cust": "CUST-2001",
                "recipient_cust": "CUST-1001",
                "device": "DEV-201",
                "ip": "197.35.88.19",
                "amount": Decimal("8500.00"),
                "currency": "EGP",
                "timestamp": _days_ago(4),
                "risk_score": Decimal("15.00"),
                "risk_level": "LOW",
                "review_status": "NOT_REQUIRED",
                "note": "Peer repayment for office expenses",
            },
            {
                "external_id": "TXN-003",
                "sender_acc": "ACC-6001",
                "recipient_acc": "ACC-0001",
                "sender_cust": "CUST-6001",
                "recipient_cust": "CUST-1001",
                "device": "DEV-0098",
                "ip": "198.51.100.23",
                "amount": Decimal("45000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(3),
                "risk_score": Decimal("82.50"),
                "risk_level": "HIGH",
                "review_status": "REQUIRES_REVIEW",
                "note": "High-risk transfer via VPN gateway",
            },
            {
                "external_id": "TXN-004",
                "sender_acc": "ACC-0001",
                "recipient_acc": "ACC-7001",
                "sender_cust": "CUST-1001",
                "recipient_cust": "CUST-7001",
                "device": "DEV-0098",
                "ip": "197.151.166.183",
                "amount": Decimal("35000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(2),
                "risk_score": Decimal("74.00"),
                "risk_level": "HIGH",
                "review_status": "REQUIRES_REVIEW",
                "note": "Pass-through transfer via co-located device",
            },
            {
                "external_id": "TXN-005",
                "sender_acc": "ACC-6001",
                "recipient_acc": "ACC-7001",
                "sender_cust": "CUST-6001",
                "recipient_cust": "CUST-7001",
                "device": "DEV-0098",
                "ip": "198.51.100.23",
                "amount": Decimal("48000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(2),
                "risk_score": Decimal("88.00"),
                "risk_level": "CRITICAL",
                "review_status": "REQUIRES_REVIEW",
                "note": "Structuring smurfing deposit tranche 1",
            },
            {
                "external_id": "TXN-006",
                "sender_acc": "ACC-8001",
                "recipient_acc": "ACC-7001",
                "sender_cust": "CUST-8001",
                "recipient_cust": "CUST-7001",
                "device": "DEV-0098",
                "ip": "198.51.100.23",
                "amount": Decimal("49500.00"),
                "currency": "EGP",
                "timestamp": _days_ago(1.5),
                "risk_score": Decimal("89.50"),
                "risk_level": "CRITICAL",
                "review_status": "REQUIRES_REVIEW",
                "note": "Structuring smurfing deposit tranche 2",
            },
            {
                "external_id": "TXN-007",
                "sender_acc": "ACC-7001",
                "recipient_acc": "ACC-9001",
                "sender_cust": "CUST-7001",
                "recipient_cust": "CUST-9001",
                "device": "DEV-0098",
                "ip": "198.51.100.23",
                "amount": Decimal("130000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(1),
                "risk_score": Decimal("96.00"),
                "risk_level": "CRITICAL",
                "review_status": "REQUIRES_REVIEW",
                "note": "Rapid consolidation & offshore wire exit",
            },
            {
                "external_id": "TXN-008",
                "sender_acc": "ACC-5001",
                "recipient_acc": "ACC-4001",
                "sender_cust": "CUST-5001",
                "recipient_cust": "CUST-4001",
                "device": "DEV-501",
                "ip": SAFE_DOC_IP,
                "amount": Decimal("65000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(1),
                "risk_score": Decimal("78.50"),
                "risk_level": "HIGH",
                "review_status": "REQUIRES_REVIEW",
                "note": "Business vendor transfer",
            },
            {
                "external_id": "TXN-009",
                "sender_acc": "ACC-4001",
                "recipient_acc": "ACC-2001",
                "sender_cust": "CUST-4001",
                "recipient_cust": "CUST-2001",
                "device": "DEV-101",
                "ip": "156.204.12.44",
                "amount": Decimal("22000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(0.8),
                "risk_score": Decimal("28.00"),
                "risk_level": "LOW",
                "review_status": "NOT_REQUIRED",
                "note": "Merchant payout",
            },
            {
                "external_id": "TXN-010",
                "sender_acc": "ACC-0001",
                "recipient_acc": "ACC-2001",
                "sender_cust": "CUST-1001",
                "recipient_cust": "CUST-2001",
                "device": "DEV-101",
                "ip": "156.204.12.44",
                "amount": Decimal("12000.00"),
                "currency": "EGP",
                "timestamp": _days_ago(0.5),
                "risk_score": Decimal("15.00"),
                "risk_level": "LOW",
                "review_status": "NOT_REQUIRED",
                "note": "Personal transfer",
            },
        ]

        for idx, t in enumerate(sample_txns, 1):
            existing_txn = await session.scalar(select(Transaction).where(Transaction.external_id == t["external_id"]))
            if not existing_txn:
                s_acc_id = acc_ext_map[t["sender_acc"]]
                r_acc_id = acc_ext_map[t["recipient_acc"]]
                s_cust_id = cust_ext_map[t["sender_cust"]]
                r_cust_id = cust_ext_map[t["recipient_cust"]]
                dev_id = dev_ext_map.get(t.get("device"))
                ip_id = ip_addr_map.get(t.get("ip"))

                txn = Transaction(
                    external_id=t["external_id"],
                    account_id=s_acc_id,
                    recipient_account_id=r_acc_id,
                    device_id=dev_id,
                    ip_address_id=ip_id,
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
        # 7. Synthetic Tickets & Security Case Resolution Records
        print("Seeding Synthetic Support & Security Tickets, Restorations, and Messages...")
        admin_uid = user_ext_map.get("USR-1002")
        analyst_uid = user_ext_map.get("USR-1001")

        seed_tickets_data = [
            {
                "external_id": "OMR-TKT-000001",
                "customer_id": cust_ext_map["CUST-1001"],  # Ziad Karim
                "ticket_type": "TRANSFER_PASSWORD_LOCK",
                "category": "TRANSFER_SECURITY",
                "priority": "HIGH",
                "status": "OPEN",
                "title": "Transfer Password Lockout — Security Hold",
                "subject": "Transfer Password Lockout — Security Hold",
                "description": "My transfer password failed 3 consecutive times while authorizing a transfer. Account access is active, but transfer services are locked. Requesting identity verification review.",
                "customer_message": "My transfer password failed 3 consecutive times while authorizing a transfer. Account access is active, but transfer services are locked. Requesting identity verification review.",
                "opened_by": "SYSTEM",
                "requires_identity_verification": True,
                "identity_verification_status": "PENDING",
                "requires_compliance_review": False,
                "escalated_to_compliance": False,
                "customer_restoration_count_at_creation": 0,
                "created_at": _days_ago(1),
                "messages": [
                    {
                        "sender_role": "SYSTEM",
                        "sender_name": "Omerta Active Defense",
                        "message_text": "🚨 Security Event: 3 consecutive failed transfer password attempts detected. Transfer services suspended. Normal account login remains active.",
                    },
                    {
                        "sender_user_id": user_ext_map.get("USR-CUST-1"),
                        "sender_role": "CUSTOMER",
                        "sender_name": "Ziad Karim",
                        "message_text": "I forgot my transfer password while trying to send money to Layla. Please help me unlock my transfers.",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000002",
                "customer_id": cust_ext_map["CUST-2001"],  # Layla Hassan
                "ticket_type": "IDENTITY_VERIFICATION",
                "category": "IDENTITY_VERIFICATION",
                "priority": "MEDIUM",
                "status": "IN_REVIEW",
                "title": "National ID Tier-2 Limit Verification",
                "subject": "National ID Tier-2 Limit Verification",
                "description": "Submitting Egyptian National ID document (front and back) to upgrade account limits and verify identity.",
                "customer_message": "Submitting Egyptian National ID document (front and back) to upgrade account limits and verify identity.",
                "opened_by": "CUSTOMER",
                "assigned_user_id": admin_uid,
                "requires_identity_verification": True,
                "identity_verification_status": "SUBMITTED",
                "requires_compliance_review": False,
                "escalated_to_compliance": False,
                "customer_restoration_count_at_creation": 0,
                "created_at": _days_ago(2),
                "messages": [
                    {
                        "sender_user_id": user_ext_map.get("USR-CUST-2"),
                        "sender_role": "CUSTOMER",
                        "sender_name": "Layla Hassan",
                        "message_text": "Hello, I have submitted my official Egyptian National ID card for verification.",
                        "attachments": [{"filename": "national_id_front.jpg", "url": "/uploads/demo/national_id_front.jpg"}],
                    },
                    {
                        "sender_user_id": admin_uid,
                        "sender_role": "ADMINISTRATOR",
                        "sender_name": "Dr. Sarah Al-Rashid",
                        "message_text": "Thank you Layla. We are reviewing your document against national identity databases.",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000003",
                "customer_id": cust_ext_map["CUST-2001"],  # Layla Hassan
                "ticket_type": "TRANSFER_PASSWORD_LOCK",
                "category": "TRANSFER_SECURITY",
                "priority": "HIGH",
                "status": "RESOLVED",
                "title": "Transfer Access Restoration (Tier 1)",
                "subject": "Transfer Access Restoration (Tier 1)",
                "description": "Lockout after mistyped transfer password. National ID submitted and verified.",
                "customer_message": "Lockout after mistyped transfer password. National ID submitted and verified.",
                "opened_by": "SYSTEM",
                "assigned_user_id": admin_uid,
                "requires_identity_verification": True,
                "identity_verification_status": "VERIFIED",
                "restoration_requested": True,
                "restoration_approved": True,
                "restoration_approved_by": "admin@omerta.ai",
                "restoration_approved_at": _days_ago(3),
                "resolution_reason": "National ID verified. Transfer privileges restored successfully under Tier 1 standard administrative protocol.",
                "customer_restoration_count_at_creation": 0,
                "created_at": _days_ago(4),
                "resolved_at": _days_ago(3),
                "messages": [
                    {
                        "sender_role": "SYSTEM",
                        "sender_name": "Omerta Active Defense",
                        "message_text": "Transfer privileges locked following 3 failed password attempts.",
                    },
                    {
                        "sender_user_id": admin_uid,
                        "sender_role": "ADMINISTRATOR",
                        "sender_name": "Dr. Sarah Al-Rashid",
                        "message_text": "Identity document verified. Transfer privileges restored under Tier 1 protocol.",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000004",
                "customer_id": cust_ext_map["CUST-3001"],  # Amira El-Sayed
                "ticket_type": "TRANSFER_DISPUTE",
                "category": "TRANSACTION_DISPUTE",
                "priority": "HIGH",
                "status": "WAITING_FOR_CUSTOMER",
                "title": "Disputed Transfer Settlement Delay",
                "subject": "Disputed Transfer Settlement Delay",
                "description": "Transfer executed on Monday; recipient institution reported network routing delay. Requesting confirmation of double-entry ledger settlement.",
                "customer_message": "Transfer executed on Monday; recipient institution reported network routing delay. Requesting confirmation of double-entry ledger settlement.",
                "opened_by": "CUSTOMER",
                "assigned_analyst_id": analyst_uid,
                "requires_identity_verification": False,
                "identity_verification_status": "NOT_REQUIRED",
                "requires_compliance_review": False,
                "customer_restoration_count_at_creation": 0,
                "created_at": _days_ago(5),
                "messages": [
                    {
                        "sender_user_id": user_ext_map.get("USR-CUST-3"),
                        "sender_role": "CUSTOMER",
                        "sender_name": "Amira El-Sayed",
                        "message_text": "The recipient has not received the transfer yet despite my balance being deducted.",
                    },
                    {
                        "sender_user_id": analyst_uid,
                        "sender_role": "FRAUD_ANALYST",
                        "sender_name": "Tariq Mansour",
                        "message_text": "We verified that ledger debit LED-DB-001 completed. Could you confirm recipient bank reference number?",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000005",
                "customer_id": cust_ext_map["CUST-4001"],  # Omar Farouk
                "ticket_type": "ACCOUNT_TAKEOVER",
                "category": "ACCOUNT_SECURITY",
                "priority": "CRITICAL",
                "status": "ESCALATED",
                "title": "Urgent: Unrecognized Login Anomaly & Takeover Attempt",
                "subject": "Urgent: Unrecognized Login Anomaly & Takeover Attempt",
                "description": "Customer received security alert regarding impossible travel from Frankfurt ASN. Immediate security freeze of funds movement and forensic analysis required.",
                "customer_message": "Customer received security alert regarding impossible travel from Frankfurt ASN. Immediate security freeze of funds movement and forensic analysis required.",
                "opened_by": "CUSTOMER",
                "assigned_analyst_id": analyst_uid,
                "requires_identity_verification": True,
                "identity_verification_status": "PENDING",
                "requires_compliance_review": True,
                "escalated_to_compliance": True,
                "admin_notes": "Critical security incident. Standard restoration disabled. Case escalated to Senior Compliance & Fraud Analytics.",
                "customer_restoration_count_at_creation": 0,
                "created_at": _days_ago(1),
                "messages": [
                    {
                        "sender_user_id": user_ext_map.get("USR-CUST-4"),
                        "sender_role": "CUSTOMER",
                        "sender_name": "Omar Farouk",
                        "message_text": "Someone tried to log in to my account from Frankfurt! I am currently in Cairo.",
                    },
                    {
                        "sender_user_id": analyst_uid,
                        "sender_role": "FRAUD_ANALYST",
                        "sender_name": "Tariq Mansour",
                        "message_text": "Immediate security containment engaged. Outbound transfers frozen. Case escalated to Senior Compliance.",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000006",
                "customer_id": cust_ext_map["CUST-5001"],  # Nour Mansour
                "ticket_type": "RISK_REVIEW",
                "category": "RISK_REVIEW",
                "priority": "HIGH",
                "status": "IN_REVIEW",
                "title": "Automated Risk Review: High Value Outbound Transfer",
                "subject": "Automated Risk Review: High Value Outbound Transfer",
                "description": "Transaction TRF-0004 triggered automated risk score 82.50% (HIGH). Structuring & round-figure rules observed.",
                "customer_message": "Transaction TRF-0004 triggered automated risk score 82.50% (HIGH). Structuring & round-figure rules observed.",
                "opened_by": "SYSTEM",
                "assigned_analyst_id": analyst_uid,
                "requires_identity_verification": False,
                "identity_verification_status": "NOT_REQUIRED",
                "requires_compliance_review": True,
                "related_risk_assessment_id": "RA-TXN-1004",
                "customer_restoration_count_at_creation": 3,
                "created_at": _days_ago(2),
                "messages": [
                    {
                        "sender_role": "SYSTEM",
                        "sender_name": "Omerta Risk Engine",
                        "message_text": "Risk assessment completed with score 82.50% (HIGH). Human review workflow initiated.",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000007",
                "customer_id": cust_ext_map["CUST-4001"],  # Omar Farouk
                "ticket_type": "VPN_LOCATION_ISSUE",
                "category": "ACCOUNT_SECURITY",
                "priority": "LOW",
                "status": "WAITING_FOR_DOCUMENT",
                "title": "Corporate VPN Location Flag",
                "subject": "Corporate VPN Location Flag",
                "description": "Logging in through enterprise VPN in Zurich triggered geographical mismatch warning.",
                "customer_message": "Logging in through enterprise VPN in Zurich triggered geographical mismatch warning.",
                "opened_by": "CUSTOMER",
                "requires_identity_verification": True,
                "identity_verification_status": "PENDING",
                "customer_restoration_count_at_creation": 0,
                "created_at": _days_ago(6),
                "messages": [
                    {
                        "sender_user_id": user_ext_map.get("USR-CUST-4"),
                        "sender_role": "CUSTOMER",
                        "sender_name": "Omar Farouk",
                        "message_text": "I was using my company's VPN which routed traffic through Switzerland.",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000008",
                "customer_id": cust_ext_map["CUST-1001"],  # Ziad Karim
                "ticket_type": "BALANCE_DISPUTE",
                "category": "TRANSACTION_DISPUTE",
                "priority": "MEDIUM",
                "status": "RESOLVED",
                "title": "Ledger Inquiry for Merchant Settlement",
                "subject": "Ledger Inquiry for Merchant Settlement",
                "description": "Discrepancy noted between ledger balance and pending authorization.",
                "customer_message": "Discrepancy noted between ledger balance and pending authorization.",
                "opened_by": "CUSTOMER",
                "requires_identity_verification": False,
                "identity_verification_status": "NOT_REQUIRED",
                "resolution_reason": "Verified double-entry ledger entries LED-DB-001 and LED-CR-001. All entries reconciled.",
                "customer_restoration_count_at_creation": 0,
                "created_at": _days_ago(8),
                "resolved_at": _days_ago(7),
                "messages": [
                    {
                        "sender_user_id": user_ext_map.get("USR-CUST-1"),
                        "sender_role": "CUSTOMER",
                        "sender_name": "Ziad Karim",
                        "message_text": "Balance showed pending hold on merchant transfer.",
                    },
                    {
                        "sender_user_id": admin_uid,
                        "sender_role": "ADMINISTRATOR",
                        "sender_name": "Dr. Sarah Al-Rashid",
                        "message_text": "Hold released and reconciled against core ledger.",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000009",
                "customer_id": cust_ext_map["CUST-2001"],  # Layla Hassan
                "ticket_type": "GENERAL_SUPPORT",
                "category": "GENERAL_SUPPORT",
                "priority": "LOW",
                "status": "CLOSED",
                "title": "Inquiry: Daily Transfer Limits & Scheduled Maintenance",
                "subject": "Inquiry: Daily Transfer Limits & Scheduled Maintenance",
                "description": "General question about weekend instant clearing windows in Egypt.",
                "customer_message": "General question about weekend instant clearing windows in Egypt.",
                "opened_by": "CUSTOMER",
                "requires_identity_verification": False,
                "identity_verification_status": "NOT_REQUIRED",
                "resolution_reason": "Provided standard schedule documentation.",
                "customer_restoration_count_at_creation": 0,
                "created_at": _days_ago(12),
                "resolved_at": _days_ago(11),
                "closed_at": _days_ago(10),
                "messages": [
                    {
                        "sender_user_id": user_ext_map.get("USR-CUST-2"),
                        "sender_role": "CUSTOMER",
                        "sender_name": "Layla Hassan",
                        "message_text": "What are the daily instant transfer limits for individual accounts?",
                    },
                    {
                        "sender_user_id": admin_uid,
                        "sender_role": "ADMINISTRATOR",
                        "sender_name": "Dr. Sarah Al-Rashid",
                        "message_text": "Daily limit is 100,000 EGP per day for verified accounts with instant IPN settlement.",
                    },
                ],
            },
            {
                "external_id": "OMR-TKT-000010",
                "customer_id": cust_ext_map["CUST-5001"],  # Nour Mansour
                "ticket_type": "TRANSFER_PASSWORD_LOCK",
                "category": "TRANSFER_SECURITY",
                "priority": "CRITICAL",
                "status": "ESCALATED",
                "title": "Fourth Security Lockout — Mandatory Senior Compliance Review",
                "subject": "Fourth Security Lockout — Mandatory Senior Compliance Review",
                "description": "Repeated 3-strikes transfer password lockouts. Customer has reached the 3 standard administrative restoration limit. Ordinary admin restoration is restricted; requires Senior Compliance authorization.",
                "customer_message": "My transfer password failed again. Please unlock my account.",
                "opened_by": "SYSTEM",
                "requires_identity_verification": True,
                "identity_verification_status": "SUBMITTED",
                "requires_compliance_review": True,
                "escalated_to_compliance": True,
                "customer_restoration_count_at_creation": 3,
                "admin_notes": "POLICY ENFORCEMENT: 3 prior restorations on file. 4th restoration attempt requires Senior Compliance / Fraud Architect review before transfer access can be unlocked.",
                "created_at": _days_ago(1),
                "messages": [
                    {
                        "sender_role": "SYSTEM",
                        "sender_name": "Omerta Active Defense",
                        "message_text": "🚨 Security Event: 3 failed transfer password attempts. Transfer status locked.",
                    },
                    {
                        "sender_user_id": user_ext_map.get("USR-CUST-5"),
                        "sender_role": "CUSTOMER",
                        "sender_name": "Nour Mansour",
                        "message_text": "I got locked out again. I submitted my company registration and National ID.",
                        "attachments": [{"filename": "national_id_nour.jpg", "url": "/uploads/demo/national_id_nour.jpg"}],
                    },
                    {
                        "sender_user_id": admin_uid,
                        "sender_role": "ADMINISTRATOR",
                        "sender_name": "Dr. Sarah Al-Rashid",
                        "message_text": "⚠️ Escalation Notice: Account has reached 3 prior administrative restorations. Standard admin unlocking is restricted by policy. Case escalated to Senior Compliance.",
                    },
                ],
            },
        ]

        ticket_model_map = {}
        for t_data in seed_tickets_data:
            t_copy = dict(t_data)
            msgs_to_add = t_copy.pop("messages", [])
            existing_t = await session.scalar(select(SupportTicket).where(SupportTicket.external_id == t_copy["external_id"]))
            if not existing_t:
                new_t = SupportTicket(**t_copy)
                session.add(new_t)
                await session.flush()
                ticket_model_map[t_copy["external_id"]] = new_t.id
                for m in msgs_to_add:
                    att_list = m.get("attachments", [])
                    att_url = att_list[0]["url"] if att_list else None
                    att_name = att_list[0]["filename"] if att_list else None
                    att_type = "IMAGE" if att_url else "NONE"
                    session.add(
                        SupportMessage(
                            external_id=f"MSG-{secrets.token_hex(4).upper()}",
                            ticket_id=new_t.id,
                            sender_user_id=m.get("sender_user_id"),
                            sender_role=m.get("sender_role", "SYSTEM"),
                            sender_name=m.get("sender_name", "Omerta System"),
                            message_text=m.get("message_text", ""),
                            attachment_url=att_url,
                            attachment_name=att_name,
                            attachment_type=att_type,
                            created_at=t_copy["created_at"],
                        )
                    )
            else:
                ticket_model_map[t_copy["external_id"]] = existing_t.id

        # 8. Historical TransferRestorations (Layla Hassan: 1, Nour Mansour: 3)
        restorations_to_seed = [
            # Layla Hassan - 1 prior restoration
            {
                "external_id": "RST-SEED-0001",
                "customer_id": cust_ext_map["CUST-2001"],
                "ticket_id": ticket_model_map.get("OMR-TKT-000003"),
                "actor_id": str(admin_uid or 2),
                "actor_name": "Dr. Sarah Al-Rashid",
                "actor_role": "ADMINISTRATOR",
                "restoration_number": 1,
                "previous_state": "BLOCKED",
                "new_state": "ACTIVE",
                "reason": "Tier 1: National ID verified. Transfer privileges restored successfully.",
                "verification_reference": "IDV-NAT-29902022345678",
                "created_at": _days_ago(3),
            },
            # Nour Mansour - 3 prior restorations (so current ticket is 4th)
            {
                "external_id": "RST-SEED-0002",
                "customer_id": cust_ext_map["CUST-5001"],
                "ticket_id": None,
                "actor_id": str(admin_uid or 2),
                "actor_name": "Dr. Sarah Al-Rashid",
                "actor_role": "ADMINISTRATOR",
                "restoration_number": 1,
                "previous_state": "BLOCKED",
                "new_state": "ACTIVE",
                "reason": "Tier 1: Verified Egyptian National ID 29505055678901 and confirmed user identity.",
                "verification_reference": "IDV-NAT-29505055678901-T1",
                "created_at": _days_ago(30),
            },
            {
                "external_id": "RST-SEED-0003",
                "customer_id": cust_ext_map["CUST-5001"],
                "ticket_id": None,
                "actor_id": str(admin_uid or 2),
                "actor_name": "Dr. Sarah Al-Rashid",
                "actor_role": "ADMINISTRATOR",
                "restoration_number": 2,
                "previous_state": "BLOCKED",
                "new_state": "ACTIVE",
                "reason": "Tier 2: Re-verified National ID + verified registered phone OTP (+201055556666).",
                "verification_reference": "IDV-NAT-29505055678901-T2",
                "created_at": _days_ago(20),
            },
            {
                "external_id": "RST-SEED-0004",
                "customer_id": cust_ext_map["CUST-5001"],
                "ticket_id": None,
                "actor_id": str(admin_uid or 2),
                "actor_name": "Dr. Sarah Al-Rashid",
                "actor_role": "ADMINISTRATOR",
                "restoration_number": 3,
                "previous_state": "BLOCKED",
                "new_state": "ACTIVE",
                "reason": "Tier 3: Verified ID + compliance review recorded. Customer warned that subsequent lockouts require senior escalation.",
                "verification_reference": "IDV-NAT-29505055678901-T3",
                "created_at": _days_ago(10),
            },
        ]

        for r_data in restorations_to_seed:
            existing_r = await session.scalar(
                select(TransferRestoration).where(
                    TransferRestoration.customer_id == r_data["customer_id"],
                    TransferRestoration.restoration_number == r_data["restoration_number"],
                )
            )
            if not existing_r:
                session.add(TransferRestoration(**r_data))

        await session.flush()
        print("Deterministic seed complete! All demo customers, ledger entries, synthetic tickets, and restorations ready.")


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
