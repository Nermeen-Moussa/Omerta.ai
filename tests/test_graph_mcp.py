"""MCP protocol tests for the graph server (in-memory transport, private loops).

Same approach as Phase 5: each test is synchronous, seeds PostgreSQL, and
talks to the shared ``MCPServer`` through a real MCP ``Client`` - proving the
full path MCP -> graph service -> Neo4j -> projected seed data.
"""

import asyncio
import json
from typing import Any

import pytest
from infrastructure.config import get_settings
from infrastructure.database.seed import SAFE_DOC_IP, reset_all, seed
from infrastructure.neo4j import client as graph_client
from infrastructure.neo4j.projection import project_all
from mcp.client.client import Client
from mcp_servers.graph_server.server import server
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(autouse=True)
def seeded_graph_sync(test_engine: AsyncEngine, graph_test_projection: str) -> None:
    """Seed PostgreSQL and project to Neo4j before each MCP graph test.

    The Neo4j driver is created and closed inside this ephemeral loop, leaving
    the module-level cache empty so each test's MCP loop creates its own.
    """
    from neo4j import AsyncGraphDatabase

    settings = get_settings()

    async def _seed_and_project() -> None:
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        graph_client.set_driver(driver)
        try:
            await reset_all(test_engine)
            await seed(test_engine)
            await project_all(test_engine)
        finally:
            await driver.close()
            graph_client.set_driver(None)

    asyncio.run(_seed_and_project())


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a graph tool over the MCP protocol and validate its payload."""

    async def _runner() -> dict[str, Any]:
        async with Client(server) as client:
            result = await client.call_tool(name, arguments)
            assert result.is_error is False
            payload = result.structured_content
            json.dumps(payload)  # must be JSON-serializable
            assert isinstance(payload, dict)
            return payload

    return asyncio.run(_runner())


def test_list_tools_exposes_six_graph_tools() -> None:
    async def _runner() -> set[str]:
        async with Client(server) as client:
            listed = await client.list_tools()
            tools = listed.tools if hasattr(listed, "tools") else listed
            return {t.name for t in tools}

    names = asyncio.run(_runner())
    assert names == {
        "get_account_neighbors",
        "find_connected_accounts",
        "find_shared_devices",
        "find_shared_ips",
        "find_transaction_paths",
        "find_fraud_ring",
    }


def test_get_account_neighbors_smoke() -> None:
    payload = _call_tool("get_account_neighbors", {"account_id": "ACC-1001"})

    assert payload["account_id"] == "ACC-1001"
    ids = {n["id"] for n in payload["neighbors"]}
    assert "TXN-001" in ids and "DEV-123" in ids
    types = {n["type"] for n in payload["neighbors"]}
    assert {"ACCOUNT", "TRANSACTION", "DEVICE", "IP"}.issubset(types)


def test_get_account_neighbors_not_found() -> None:
    payload = _call_tool("get_account_neighbors", {"account_id": "ACC-999"})

    assert payload["error"] == "NOT_FOUND"
    assert payload["resource"] == "account"
    assert payload["id"] == "ACC-999"


def test_find_connected_accounts_smoke() -> None:
    payload = _call_tool("find_connected_accounts", {"account_id": "ACC-1001"})

    pairs = {(c["account_id"], c["via"]) for c in payload["connections"]}
    assert ("ACC-9001", "DIRECT_TRANSACTION") in pairs
    assert ("ACC-3001", "SHARED_DEVICE") in pairs
    assert ("ACC-3001", "SHARED_IP") in pairs


def test_find_connected_accounts_not_found() -> None:
    payload = _call_tool("find_connected_accounts", {"account_id": "ACC-999"})

    assert payload["error"] == "NOT_FOUND"


def test_find_shared_devices_smoke() -> None:
    payload = _call_tool("find_shared_devices", {"account_id": "ACC-1001"})

    by_device = {d["device_id"]: d["other_accounts"] for d in payload["shared_devices"]}
    assert by_device["DEV-123"] == ["ACC-3001"]


def test_find_shared_ips_smoke() -> None:
    payload = _call_tool("find_shared_ips", {"account_id": "ACC-1001"})

    by_ip = {i["ip_address"]: i["other_accounts"] for i in payload["shared_ips"]}
    assert by_ip[SAFE_DOC_IP] == ["ACC-3001"]


def test_find_transaction_paths_smoke() -> None:
    payload = _call_tool(
        "find_transaction_paths",
        {"source_account_id": "ACC-1001", "target_account_id": "ACC-9001"},
    )

    assert payload["count"] >= 1
    first = payload["paths"][0]
    assert first["edges"] == 2
    assert [n["id"] for n in first["nodes"]] == ["ACC-1001", "TXN-001", "ACC-9001"]


def test_find_transaction_paths_depth_validation() -> None:
    payload = _call_tool(
        "find_transaction_paths",
        {
            "source_account_id": "ACC-1001",
            "target_account_id": "ACC-9001",
            "max_depth": 99,
        },
    )

    assert payload["error"] == "VALIDATION_ERROR"
    assert payload["field"] == "max_depth"


def test_find_transaction_paths_not_found() -> None:
    payload = _call_tool(
        "find_transaction_paths",
        {"source_account_id": "ACC-1001", "target_account_id": "ACC-999"},
    )

    assert payload["error"] == "NOT_FOUND"


def test_find_fraud_ring_smoke() -> None:
    payload = _call_tool("find_fraud_ring", {"account_id": "ACC-9001"})

    types = {s["type"] for s in payload["signals"]}
    assert "SHARED_DEVICE" in types
    assert "SHARED_IP" in types
    assert "PASS_THROUGH" in types
    assert "not a fraud determination" in payload["note"]


def test_find_fraud_ring_not_found() -> None:
    payload = _call_tool("find_fraud_ring", {"account_id": "ACC-999"})

    assert payload["error"] == "NOT_FOUND"


def test_empty_id_returns_validation_error() -> None:
    payload = _call_tool("find_shared_devices", {"account_id": " "})

    assert payload["error"] == "VALIDATION_ERROR"
    assert payload["field"] == "account_id"


def test_missing_required_argument_fails_cleanly() -> None:
    async def _runner() -> Any:
        async with Client(server) as client:
            result = await client.call_tool("get_account_neighbors", {})
            return [block.model_dump(mode="json") for block in result.content]

    blocks = asyncio.run(_runner())
    assert blocks  # protocol error surfaced as content, no internal details
