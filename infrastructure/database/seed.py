"""Deterministic seed data for local development and testing.

Idempotent by design: every row is upserted on its natural business key
(``external_id`` / ``address``), so running the seed twice never creates
duplicates. Optional ``--reset`` truncates all tables first.

All risk scores are SEEDED/MOCK values for development - they are NOT
predictions from a trained ML model (the ML risk engine arrives in a later
phase). The database stores facts only; AI conclusions are never seeded.

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
    Alert,
    Device,
    Evidence,
    InvestigationCase,
    IPAddress,
    Transaction,
)
from infrastructure.database.session import create_engine, session_scope

# 202.0.113.0/24 is IANA TEST-NET-3 and 198.51.100.0/24 is TEST-NET-2:
# documentation-only ranges, never routed to a real host.
SAFE_DOC_IP = "202.0.113.77"
SAFE_DOC_IP_2 = "198.51.100.23"

_SEED_NOW = datetime.now(UTC)


def _days_ago(days: float) -> datetime:
    return _SEED_NOW - timedelta(days=days)


# --------------------------------------------------------------------------- #
# Seed definitions (plain data -> deterministic, easy to review)
# --------------------------------------------------------------------------- #

DEVICES: list[dict[str, Any]] = [
    {
        "external_id": "DEV-123",
        "device_type": "MOBILE",
        "first_seen_at": _days_ago(1),
        "last_seen_at": _SEED_NOW,
        "risk_level": "HIGH",  # brand-new device used for high-value transfers
    },
    {
        "external_id": "DEV-456",
        "device_type": "DESKTOP",
        "first_seen_at": _days_ago(400),
        "last_seen_at": _days_ago(2),
        "risk_level": "LOW",
    },
    {
        "external_id": "DEV-789",
        "device_type": "TABLET",
        "first_seen_at": _days_ago(180),
        "last_seen_at": _days_ago(10),
        "risk_level": "LOW",
    },
]

IPS: list[dict[str, Any]] = [
    {
        "address": SAFE_DOC_IP,
        "country": "US",
        "first_seen_at": _days_ago(1),
        "last_seen_at": _SEED_NOW,
        "risk_level": "MEDIUM",  # first appearance, unverified reputation
    },
    {
        "address": SAFE_DOC_IP_2,
        "country": "US",
        "first_seen_at": _days_ago(365),
        "last_seen_at": _days_ago(2),
        "risk_level": "LOW",
    },
]

ACCOUNTS: list[dict[str, Any]] = [
    {
        "external_id": "ACC-1001",
        "customer_name": "John Anderson",
        "account_type": "CHECKING",
        "country": "US",
        "status": "ACTIVE",
        "risk_level": "HIGH",  # seeded: prior suspicious association
        "created_at": _days_ago(900),
    },
    {
        "external_id": "ACC-2001",
        "customer_name": "Maria Rossi",
        "account_type": "SAVINGS",
        "country": "IT",
        "status": "ACTIVE",
        "risk_level": "MEDIUM",
        "created_at": _days_ago(650),
    },
    {
        "external_id": "ACC-3001",
        "customer_name": "Chen Wei",
        "account_type": "CHECKING",
        "country": "SG",
        "status": "ACTIVE",
        "risk_level": "LOW",
        "created_at": _days_ago(1200),
    },
    {
        "external_id": "ACC-4001",
        "customer_name": "Ahmed Hassan",
        "account_type": "CHECKING",
        "country": "AE",
        "status": "ACTIVE",
        "risk_level": "MEDIUM",  # rapid pass-through hub (layering signal)
        "created_at": _days_ago(210),
    },
    {
        "external_id": "ACC-9001",
        "customer_name": "Elena Petrova",
        "account_type": "CHECKING",
        "country": "CY",
        "status": "ACTIVE",
        "risk_level": "HIGH",  # seeded: previously flagged recipient
        "created_at": _days_ago(30),  # young account: mule-typology indicator
    },
]

TRANSACTIONS: list[dict[str, Any]] = [
    # --- Baseline history for ACC-1001 (normal small transfers) ---
    {
        "external_id": "TXN-1001",
        "account": "ACC-1001",
        "recipient": "ACC-3001",
        "amount": Decimal("125.00"),
        "currency": "USD",
        "transaction_type": "TRANSFER",
        "status": "COMPLETED",
        "timestamp": _days_ago(45),
        "device": "DEV-456",
        "ip": SAFE_DOC_IP_2,
        "is_new_device": False,
        "is_new_ip": False,
        "metadata": {"channel": "web"},
    },
    {
        "external_id": "TXN-1002",
        "account": "ACC-1001",
        "recipient": "ACC-3001",
        "amount": Decimal("89.99"),
        "currency": "USD",
        "transaction_type": "TRANSFER",
        "status": "COMPLETED",
        "timestamp": _days_ago(20),
        "device": "DEV-456",
        "ip": SAFE_DOC_IP_2,
        "is_new_device": False,
        "is_new_ip": False,
        "metadata": {"channel": "web"},
    },
    # --- Suspicious history: ACC-1001 -> ACC-2001 from the NEW device/IP ---
    {
        "external_id": "TXN-1003",
        "account": "ACC-1001",
        "recipient": "ACC-2001",
        "amount": Decimal("7200.00"),
        "currency": "USD",
        "transaction_type": "TRANSFER",
        "status": "COMPLETED",
        "timestamp": _days_ago(3),
        "device": "DEV-123",
        "ip": SAFE_DOC_IP,
        "is_new_device": True,
        "is_new_ip": True,
        "metadata": {"channel": "mobile"},
    },
    # --- Layering pattern: ACC-4001 passes funds in and out within hours ---
    {
        "external_id": "TXN-1004",
        "account": "ACC-4001",
        "recipient": "ACC-9001",
        "amount": Decimal("6500.00"),
        "currency": "USD",
        "transaction_type": "TRANSFER",
        "status": "COMPLETED",
        "timestamp": _days_ago(2),
        "device": "DEV-789",
        "ip": SAFE_DOC_IP_2,
        "is_new_device": False,
        "is_new_ip": False,
        "metadata": {"channel": "web"},
    },
    {
        "external_id": "TXN-1005",
        "account": "ACC-9001",
        "recipient": "ACC-4001",
        "amount": Decimal("6350.00"),
        "currency": "USD",
        "transaction_type": "TRANSFER",
        "status": "COMPLETED",
        "timestamp": _days_ago(2) + timedelta(hours=4),
        "device": "DEV-789",
        "ip": SAFE_DOC_IP_2,
        "is_new_device": False,
        "is_new_ip": False,
        "metadata": {"channel": "web"},
    },
    # --- Shared-infrastructure link: ACC-3001 sends from the SAME new device
    # DEV-123 and IP as ACC-1001's recent transfers, to the same recipient.
    # This makes DEV-123 / 202.0.113.77 genuinely SHARED between two senders
    # (graph evidence for Phase 6; risk interpretation is left to agents).
    {
        "external_id": "TXN-1006",
        "account": "ACC-3001",
        "recipient": "ACC-9001",
        "amount": Decimal("4250.00"),
        "currency": "USD",
        "transaction_type": "TRANSFER",
        "status": "COMPLETED",
        "timestamp": _days_ago(0) - timedelta(minutes=75),
        "device": "DEV-123",  # shared with ACC-1001's TXN-001 / TXN-1003
        "ip": SAFE_DOC_IP,  # shared infrastructure
        "is_new_device": True,
        "is_new_ip": True,
        "metadata": {"channel": "mobile"},
    },
    # --- THE suspicious transaction under investigation ---
    {
        "external_id": "TXN-001",
        "account": "ACC-1001",
        "recipient": "ACC-9001",
        "amount": Decimal("8400.00"),
        "currency": "USD",
        "transaction_type": "WIRE",
        "status": "COMPLETED",
        "timestamp": _days_ago(0) - timedelta(minutes=30),
        "device": "DEV-123",  # new device for ACC-1001
        "ip": SAFE_DOC_IP,  # new IP for ACC-1001
        "is_new_device": True,
        "is_new_ip": True,
        "metadata": {"channel": "mobile", "reference": "SEED-CASE-001"},
    },
]

ALERTS: list[dict[str, Any]] = [
    {
        "external_id": "ALERT-001",
        "transaction": "TXN-001",
        "alert_type": "HIGH_VALUE_NEW_DEVICE_NEW_IP",
        "risk_score": Decimal("0.87"),  # seeded/mock - not an ML prediction
        "risk_level": "HIGH",
        "status": "OPEN",
    },
    {
        "external_id": "ALERT-002",
        "transaction": "TXN-1006",
        "alert_type": "SHARED_DEVICE_MULTI_ACCOUNT",
        "risk_score": Decimal("0.74"),  # seeded/mock - not an ML prediction
        "risk_level": "HIGH",
        "status": "OPEN",
    },
    {
        "external_id": "ALERT-003",
        "transaction": "TXN-1001",
        "alert_type": "ROUTINE_MONITORING",
        "risk_score": Decimal("0.20"),  # seeded/mock - low-value baseline
        "risk_level": "LOW",
        "status": "CLOSED",
    },
]

CASES: list[dict[str, Any]] = [
    {
        "external_id": "CASE-001",
        "alert": "ALERT-001",
        "status": "OPEN",
        "severity": "HIGH",
        "assigned_to": None,
    },
]

EVIDENCE: list[dict[str, Any]] = [
    {
        "case": "CASE-001",
        "evidence_id": "SEED-EV-001",
        "investigation_id": "CASE-001",
        "transaction_id": "TXN-001",
        "tier": "FACT",
        "producer": "seed",
        "evidence_type": "TRANSACTION_FACT",
        "source": "POSTGRES",
        "source_reference": "transactions.external_id=TXN-001",
        "description": (
            "Wire transfer of 8400.00 USD from ACC-1001 to ACC-9001 from new "
            f"device DEV-123 and new IP {SAFE_DOC_IP}"
        ),
        "data": {
            "amount": "8400.00",
            "currency": "USD",
            "is_new_device": True,
            "is_new_ip": True,
        },
    },
    {
        "case": "CASE-001",
        "evidence_id": "SEED-EV-002",
        "investigation_id": "CASE-001",
        "transaction_id": "TXN-001",
        "tier": "FACT",
        "producer": "seed",
        "evidence_type": "ACCOUNT_HISTORY",
        "source": "POSTGRES",
        "source_reference": "transactions.external_id=TXN-1003",
        "description": (
            "ACC-1001 previously sent 7200.00 USD to ACC-2001 from the same "
            "new device DEV-123 three days earlier"
        ),
        "data": {"related_transaction": "TXN-1003"},
    },
    {
        "case": "CASE-001",
        "evidence_id": "SEED-EV-003",
        "investigation_id": "CASE-001",
        "transaction_id": "TXN-001",
        "tier": "MODEL_OUTPUT",
        "producer": "seed",
        "evidence_type": "ALERT_FACT",
        "source": "POSTGRES",
        "source_reference": "alerts.external_id=ALERT-001",
        "description": "Seeded rule-based alert with mock risk score 0.87 (HIGH)",
        "data": {"risk_score": "0.87", "origin": "seed/mock, not an ML prediction"},
    },
]


# --------------------------------------------------------------------------- #
# Upsert helpers (idempotency on natural business keys)
# --------------------------------------------------------------------------- #


async def _upsert_device(session: AsyncSession, row: dict[str, Any]) -> int:
    obj = await session.scalar(select(Device).where(Device.external_id == row["external_id"]))
    if obj is None:
        obj = Device(**row)
        session.add(obj)
        await session.flush()
    else:
        for key, value in row.items():
            setattr(obj, key, value)
    return obj.id


async def _upsert_ip(session: AsyncSession, row: dict[str, Any]) -> int:
    obj = await session.scalar(select(IPAddress).where(IPAddress.address == row["address"]))
    if obj is None:
        obj = IPAddress(**row)
        session.add(obj)
        await session.flush()
    else:
        for key, value in row.items():
            setattr(obj, key, value)
    return obj.id


async def _upsert_account(session: AsyncSession, row: dict[str, Any]) -> int:
    obj = await session.scalar(select(Account).where(Account.external_id == row["external_id"]))
    if obj is None:
        obj = Account(**row)
        session.add(obj)
        await session.flush()
    else:
        for key, value in row.items():
            setattr(obj, key, value)
    return obj.id


async def _upsert_transaction(
    session: AsyncSession,
    row: dict[str, Any],
    *,
    account_ids: dict[str, int],
    device_ids: dict[str, int],
    ip_ids: dict[str, int],
) -> int:
    values = {
        "account_id": account_ids[row["account"]],
        "recipient_account_id": account_ids[row["recipient"]],
        "amount": row["amount"],
        "currency": row["currency"],
        "transaction_type": row["transaction_type"],
        "status": row["status"],
        "timestamp": row["timestamp"],
        "device_id": device_ids[row["device"]],
        "ip_address_id": ip_ids[row["ip"]],
        "is_new_device": row["is_new_device"],
        "is_new_ip": row["is_new_ip"],
        "txn_metadata": row["metadata"],
    }
    obj = await session.scalar(
        select(Transaction).where(Transaction.external_id == row["external_id"])
    )
    if obj is None:
        obj = Transaction(external_id=row["external_id"], **values)
        session.add(obj)
        await session.flush()
    else:
        for key, value in values.items():
            setattr(obj, key, value)
    return obj.id


async def _upsert_alert(
    session: AsyncSession, row: dict[str, Any], *, transaction_ids: dict[str, int]
) -> int:
    values = {
        "transaction_id": transaction_ids[row["transaction"]],
        "alert_type": row["alert_type"],
        "risk_score": row["risk_score"],
        "risk_level": row["risk_level"],
        "status": row["status"],
    }
    obj = await session.scalar(select(Alert).where(Alert.external_id == row["external_id"]))
    if obj is None:
        obj = Alert(external_id=row["external_id"], **values)
        session.add(obj)
        await session.flush()
    else:
        for key, value in values.items():
            setattr(obj, key, value)
    return obj.id


async def _upsert_case(
    session: AsyncSession, row: dict[str, Any], *, alert_ids: dict[str, int]
) -> int:
    values = {
        "alert_id": alert_ids[row["alert"]],
        "status": row["status"],
        "severity": row["severity"],
        "assigned_to": row["assigned_to"],
    }
    obj = await session.scalar(
        select(InvestigationCase).where(InvestigationCase.external_id == row["external_id"])
    )
    if obj is None:
        obj = InvestigationCase(external_id=row["external_id"], **values)
        session.add(obj)
        await session.flush()
    else:
        for key, value in values.items():
            setattr(obj, key, value)
    return obj.id


async def _upsert_evidence(
    session: AsyncSession, row: dict[str, Any], *, case_ids: dict[str, int]
) -> int:
    values = {
        "evidence_type": row["evidence_type"],
        "source": row["source"],
        "source_reference": row["source_reference"],
        "description": row["description"],
        "data": row["data"],
        "evidence_id": row["evidence_id"],
        "investigation_id": row["investigation_id"],
        "transaction_id": row.get("transaction_id"),
        "tier": row.get("tier", "FACT"),
        "producer": row.get("producer", "seed"),
        "producer_version": row.get("producer_version", "seed-v1"),
        "content_hash": content_hash(
            {
                "evidence_id": row["evidence_id"],
                "investigation_id": row["investigation_id"],
                "transaction_id": row.get("transaction_id") or "",
                "category": row["evidence_type"],
                "source": row["source"].lower(),
                "tier": row.get("tier", "FACT"),
                "producer": row.get("producer", "seed"),
                "producer_version": row.get("producer_version", "seed-v1"),
                "reference": row["source_reference"],
                "description": row["description"],
                "data": row["data"],
            }
        ),
    }
    obj = await session.scalar(
        select(Evidence).where(
            Evidence.case_id == case_ids[row["case"]],
            Evidence.source == row["source"],
            Evidence.source_reference == row["source_reference"],
        )
    )
    if obj is None:
        obj = Evidence(case_id=case_ids[row["case"]], **values)
        session.add(obj)
        await session.flush()
    else:
        for key, value in values.items():
            setattr(obj, key, value)
    return obj.id


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #


async def reset_all(engine: AsyncEngine) -> None:
    """Delete all rows (keep schema from migrations). Order respects FKs."""
    async with engine.begin() as conn:
        await conn.execute(delete(Evidence))
        await conn.execute(delete(InvestigationCase))
        await conn.execute(delete(Alert))
        await conn.execute(delete(Transaction))
        await conn.execute(delete(Account))
        await conn.execute(delete(Device))
        await conn.execute(delete(IPAddress))


async def seed(engine: AsyncEngine) -> dict[str, int]:
    """Upsert all seed rows. Returns final per-table row counts."""
    async with session_scope(engine) as session:
        device_ids = {row["external_id"]: await _upsert_device(session, row) for row in DEVICES}
        ip_ids = {row["address"]: await _upsert_ip(session, row) for row in IPS}
        account_ids = {row["external_id"]: await _upsert_account(session, row) for row in ACCOUNTS}
        transaction_ids = {
            row["external_id"]: await _upsert_transaction(
                session, row, account_ids=account_ids, device_ids=device_ids, ip_ids=ip_ids
            )
            for row in TRANSACTIONS
        }
        alert_ids = {
            row["external_id"]: await _upsert_alert(session, row, transaction_ids=transaction_ids)
            for row in ALERTS
        }
        case_ids = {
            row["external_id"]: await _upsert_case(session, row, alert_ids=alert_ids)
            for row in CASES
        }
        for row in EVIDENCE:
            await _upsert_evidence(session, row, case_ids=case_ids)

        counts: dict[str, int] = {}
        for model in (
            Account,
            Device,
            IPAddress,
            Transaction,
            Alert,
            InvestigationCase,
            Evidence,
        ):
            counts[model.__tablename__] = len((await session.scalars(select(model))).all())
    return counts


async def main(reset: bool = False) -> None:
    engine = create_engine()
    try:
        if reset:
            await reset_all(engine)
            print("Reset complete: all rows deleted.")
        counts = await seed(engine)
        print("Seed complete. Row counts:")
        for table, count in counts.items():
            print(f"  {table}: {count}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the Omerta.ai database.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete all rows before seeding (fresh deterministic state).",
    )
    args = parser.parse_args()
    asyncio.run(main(reset=args.reset))
