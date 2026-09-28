"""Graph projection tests: PostgreSQL -> Neo4j, idempotency, constraints.

Uses the dedicated ``test`` projection namespace so dev/other data in the same
Neo4j instance is never touched (community-edition-safe isolation).
"""

import pytest
from infrastructure.database.seed import SAFE_DOC_IP
from infrastructure.neo4j import client as graph_client
from infrastructure.neo4j.projection import project_all

pytestmark = pytest.mark.graph

EXPECTED_NODES = {"Account": 5, "Device": 3, "IP": 2, "Transaction": 7}
EXPECTED_RELS = {"RECEIVED_BY": 7, "SENT": 7, "USED_DEVICE": 7, "USED_IP": 7}


async def _count_nodes() -> dict[str, int]:
    rows = await graph_client.read_query(
        "MATCH (n) WHERE n.projection = $projection "
        "UNWIND labels(n) AS label RETURN label, count(*) AS count",
        {"projection": "test"},
    )
    return {row["label"]: row["count"] for row in rows}


async def _count_rels() -> dict[str, int]:
    rows = await graph_client.read_query(
        "MATCH (a)-[r]->() WHERE a.projection = $projection "
        "RETURN type(r) AS rel, count(r) AS count",
        {"projection": "test"},
    )
    return {row["rel"]: row["count"] for row in rows}


def test_projection_creates_expected_graph(graph_seeded: None) -> None:
    async def _check() -> None:
        nodes = await _count_nodes()
        rels = await _count_rels()
        assert nodes == EXPECTED_NODES
        assert rels == EXPECTED_RELS

    from tests.conftest import run_with_graph

    run_with_graph(_check)


def test_projection_is_idempotent(graph_seeded: None) -> None:
    """Running the projection twice must not duplicate nodes or edges."""

    async def _run_twice() -> None:
        # graph_seeded already ran the projection once; run it again.
        await project_all(_engine())

    from tests.conftest import run_with_graph

    def _engine():
        from infrastructure.config import get_settings
        from infrastructure.database.session import create_engine

        engine = create_engine(get_settings().test_database_url)
        return engine

    async def _full() -> None:
        engine = _engine()
        try:
            await project_all(engine)
            nodes = await _count_nodes()
            rels = await _count_rels()
            assert nodes == EXPECTED_NODES
            assert rels == EXPECTED_RELS
        finally:
            await engine.dispose()

    run_with_graph(_full)


def test_tx001_relationship_chain_in_graph(graph_seeded: None) -> None:
    """TXN-001: ACC-1001 -[:SENT]-> TXN-001 -[:RECEIVED_BY]-> ACC-9001,
    with device and IP attached."""

    async def _check() -> None:
        rows = await graph_client.read_query(
            """
            MATCH (a:Account {projection: $projection, external_id: 'ACC-1001'})
                  -[:SENT]->(t:Transaction {external_id: 'TXN-001'})
                  -[:RECEIVED_BY]->(b:Account {external_id: 'ACC-9001'})
            OPTIONAL MATCH (t)-[:USED_DEVICE]->(d:Device)
            OPTIONAL MATCH (t)-[:USED_IP]->(i:IP)
            RETURN a.external_id AS sender, t.external_id AS txn,
                   b.external_id AS recipient,
                   d.external_id AS device, i.address AS ip
            """,
            {"projection": "test"},
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["sender"] == "ACC-1001"
        assert row["txn"] == "TXN-001"
        assert row["recipient"] == "ACC-9001"
        assert row["device"] == "DEV-123"
        assert row["ip"] == SAFE_DOC_IP

    from tests.conftest import run_with_graph

    run_with_graph(_check)


def test_shared_device_edge_exists(graph_seeded: None) -> None:
    """DEV-123 is used by senders ACC-1001 and ACC-3001 (TXN-1006 scenario)."""

    async def _check() -> None:
        rows = await graph_client.read_query(
            """
            MATCH (d:Device {projection: $projection, external_id: 'DEV-123'})
                  <-[:USED_DEVICE]-(t:Transaction)<-[:SENT]-(a:Account)
            RETURN collect(DISTINCT a.external_id) AS senders
            """,
            {"projection": "test"},
        )
        senders = set(rows[0]["senders"])
        assert {"ACC-1001", "ACC-3001"}.issubset(senders)

    from tests.conftest import run_with_graph

    run_with_graph(_check)


def test_constraints_exist(graph_seeded: None) -> None:
    """Uniqueness constraints for the four node keys are in place."""

    async def _check() -> None:
        rows = await graph_client.read_query("SHOW CONSTRAINTS", {})
        names = {row.get("name", "") for row in rows}
        for expected in (
            "omerta_account_external_id",
            "omerta_transaction_external_id",
            "omerta_device_external_id",
            "omerta_ip_address",
        ):
            assert expected in names, f"missing constraint {expected}"

    from tests.conftest import run_with_graph

    run_with_graph(_check)
