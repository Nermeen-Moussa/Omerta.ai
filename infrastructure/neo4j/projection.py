"""PostgreSQL → Neo4j graph projection.

Neo4j is a derived, disposable projection of PostgreSQL facts (the source of
truth). The projection is deterministic and idempotent: every entity is keyed
by its PostgreSQL business identifier plus a ``projection`` namespace property,
and every write is a MERGE - running it twice never duplicates nodes or
relationships.

Graph model (all nodes carry ``projection`` + business key):

    (:Account {external_id, customer_name, country, risk_level})
    (:Transaction {external_id, amount, currency, transaction_type, status, timestamp})
    (:Device {external_id, device_type, risk_level})
    (:IP {address, country, risk_level})

    (:Account)-[:SENT]->(:Transaction)
    (:Transaction)-[:RECEIVED_BY]->(:Account)
    (:Transaction)-[:USED_DEVICE]->(:Device)
    (:Transaction)-[:USED_IP]->(:IP)
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.config import get_settings
from infrastructure.database.models import Account, Device, IPAddress, Transaction
from infrastructure.neo4j import client as graph_client

logger = logging.getLogger(__name__)

_CONSTRAINT_QUERIES: list[str] = [
    "CREATE CONSTRAINT omerta_account_external_id IF NOT EXISTS "
    "FOR (n:Account) REQUIRE (n.projection, n.external_id) IS UNIQUE",
    "CREATE CONSTRAINT omerta_transaction_external_id IF NOT EXISTS "
    "FOR (n:Transaction) REQUIRE (n.projection, n.external_id) IS UNIQUE",
    "CREATE CONSTRAINT omerta_device_external_id IF NOT EXISTS "
    "FOR (n:Device) REQUIRE (n.projection, n.external_id) IS UNIQUE",
    "CREATE CONSTRAINT omerta_ip_address IF NOT EXISTS "
    "FOR (n:IP) REQUIRE (n.projection, n.address) IS UNIQUE",
]


def _bolt_safe(value: Any) -> Any:
    """Convert Python values the Bolt protocol does not accept."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _bolt_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_bolt_safe(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


async def _read_source(
    engine: AsyncEngine,
) -> tuple[list[Account], list[Device], list[IPAddress], list[Transaction]]:
    """Read all entities from PostgreSQL (the source of truth)."""
    from sqlalchemy.orm import joinedload

    async with AsyncSession(engine) as session:
        accounts = (await session.scalars(select(Account).order_by(Account.id))).all()
        devices = (await session.scalars(select(Device).order_by(Device.id))).all()
        ips = (await session.scalars(select(IPAddress).order_by(IPAddress.id))).all()
        txns = (
            await session.scalars(
                select(Transaction)
                .order_by(Transaction.id)
                .options(
                    joinedload(Transaction.account),
                    joinedload(Transaction.recipient_account),
                    joinedload(Transaction.device),
                    joinedload(Transaction.ip_address),
                )
            )
        ).all()
    return list(accounts), list(devices), list(ips), list(txns)


async def project_all(engine: AsyncEngine) -> dict[str, dict[str, int]]:
    """Project all PostgreSQL facts into Neo4j (idempotent).

    Reads entities from PostgreSQL, MERGEs nodes and relationships into the
    configured projection namespace, and returns node/relationship counts.
    """
    accounts, devices, ips, txns = await _read_source(engine)

    projection = graph_client.projection()
    ns: dict[str, Any] = {"projection": projection}
    driver = graph_client.get_driver()
    database = get_settings().neo4j_database

    node_counts: dict[str, int] = {}
    rel_counts: dict[str, int] = {}

    async with driver.session(database=database) as session:
        for query in _CONSTRAINT_QUERIES:
            await session.run(query)

        # --- Nodes: MERGE on (projection, business key) -> idempotent ---
        for account in accounts:
            await session.run(
                "MERGE (a:Account {projection: $projection, external_id: $external_id}) "
                "SET a.customer_name = $customer_name, a.country = $country, "
                "    a.risk_level = $risk_level",
                external_id=account.external_id,
                customer_name=account.customer_name,
                country=account.country,
                risk_level=account.risk_level,
                **ns,
            )
        for device in devices:
            await session.run(
                "MERGE (d:Device {projection: $projection, external_id: $external_id}) "
                "SET d.device_type = $device_type, d.risk_level = $risk_level",
                external_id=device.external_id,
                device_type=device.device_type,
                risk_level=device.risk_level,
                **ns,
            )
        for ip in ips:
            await session.run(
                "MERGE (i:IP {projection: $projection, address: $address}) "
                "SET i.country = $country, i.risk_level = $risk_level",
                address=ip.address,
                country=ip.country,
                risk_level=ip.risk_level,
                **ns,
            )
        for txn in txns:
            await session.run(
                "MERGE (t:Transaction {projection: $projection, external_id: $external_id}) "
                "SET t.amount = $amount, t.currency = $currency, "
                "    t.transaction_type = $transaction_type, t.status = $status, "
                "    t.timestamp = $timestamp",
                external_id=txn.external_id,
                amount=float(txn.amount),
                currency=txn.currency,
                transaction_type=txn.transaction_type,
                status=txn.status,
                timestamp=txn.timestamp.isoformat(),
                **ns,
            )

        # --- Relationships: MATCH both endpoints, MERGE only the edge.
        # (Inlining the endpoint node inside MERGE makes Cypher create the
        # node as well when the edge is missing - a uniqueness violation.)
        for txn in txns:
            await session.run(
                "MATCH (a:Account {projection: $projection, external_id: $sender}) "
                "MATCH (t:Transaction {projection: $projection, external_id: $txn_id}) "
                "MERGE (a)-[:SENT]->(t)",
                sender=txn.account.external_id,
                txn_id=txn.external_id,
                **ns,
            )
            await session.run(
                "MATCH (t:Transaction {projection: $projection, external_id: $txn_id}) "
                "MATCH (b:Account {projection: $projection, external_id: $recipient}) "
                "MERGE (t)-[:RECEIVED_BY]->(b)",
                txn_id=txn.external_id,
                recipient=txn.recipient_account.external_id,
                **ns,
            )
            if txn.device is not None:
                await session.run(
                    "MATCH (t:Transaction {projection: $projection, external_id: $txn_id}) "
                    "MATCH (d:Device {projection: $projection, external_id: $device_id}) "
                    "MERGE (t)-[:USED_DEVICE]->(d)",
                    txn_id=txn.external_id,
                    device_id=txn.device.external_id,
                    **ns,
                )
            if txn.ip_address is not None:
                await session.run(
                    "MATCH (t:Transaction {projection: $projection, external_id: $txn_id}) "
                    "MATCH (i:IP {projection: $projection, address: $address}) "
                    "MERGE (t)-[:USED_IP]->(i)",
                    txn_id=txn.external_id,
                    address=txn.ip_address.address,
                    **ns,
                )

        # --- Report counts for this projection namespace ---
        node_rows = await graph_client.read_query(
            "MATCH (n) WHERE n.projection = $projection "
            "UNWIND labels(n) AS label "
            "RETURN label, count(*) AS count",
            {"projection": projection},
        )
        node_counts = {row["label"]: row["count"] for row in node_rows}

        rel_rows = await graph_client.read_query(
            "MATCH (a)-[r]->() WHERE a.projection = $projection "
            "RETURN type(r) AS rel, count(r) AS count",
            {"projection": projection},
        )
        rel_counts = {row["rel"]: row["count"] for row in rel_rows}

    logger.info("projection complete: %s nodes, %s relationships", node_counts, rel_counts)
    return {"nodes": node_counts, "relationships": rel_counts}


async def main() -> None:
    """CLI entrypoint: project the current PostgreSQL data into Neo4j."""
    from infrastructure.database.session import get_engine

    counts = await project_all(get_engine())
    print(f"Graph projection complete (namespace: {graph_client.projection()}).")
    print("Nodes:")
    for label, count in sorted(counts["nodes"].items()):
        print(f"  :{label}: {count}")
    print("Relationships:")
    for rel, count in sorted(counts["relationships"].items()):
        print(f"  :{rel}: {count}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
