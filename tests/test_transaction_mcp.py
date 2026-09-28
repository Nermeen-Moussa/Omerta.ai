"""MCP-layer tests: real protocol round-trips against the seeded test database.

These tests are deliberately *synchronous*: each one seeds the database, then
opens an MCP ``Client`` on a private event loop via ``asyncio.run``. The v2
MCP client is anyio-based and must enter and exit its transport in the same
task, which pytest-asyncio fixture finalization cannot guarantee.

Proven path under test:
MCP Client -> Transaction MCPServer -> tools -> service -> PostgreSQL seed.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import pytest
from infrastructure.database.seed import SAFE_DOC_IP, reset_all, seed
from mcp.client.client import Client
from mcp_servers.transaction_server.server import server
from sqlalchemy.ext.asyncio import AsyncEngine

T = TypeVar("T")


@pytest.fixture(autouse=True)
def seeded_sync(test_engine: AsyncEngine) -> None:
    """Reset and seed the test database before each MCP test."""

    async def _seed() -> None:
        await reset_all(test_engine)
        await seed(test_engine)

    asyncio.run(_seed())


def _with_client[T](coro_fn: Callable[[Client], Awaitable[T]]) -> T:
    """Run ``coro_fn(client)`` with a connected client on a private loop."""

    async def _runner() -> T:
        async with Client(server) as client:
            return await coro_fn(client)

    return asyncio.run(_runner())


def _call_tool_raw(name: str, arguments: dict[str, Any]):
    """Invoke a tool over the MCP protocol and return the raw result."""

    async def _call(client: Client):
        return await client.call_tool(name, arguments)

    return _with_client(_call)


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a tool and return its validated JSON-serializable payload."""
    result = _call_tool_raw(name, arguments)
    assert result.is_error is False
    payload = result.structured_content
    json.dumps(payload)  # must be JSON-serializable
    assert isinstance(payload, dict)
    return payload


def test_list_tools_exposes_six_tools() -> None:
    async def _call(client: Client) -> set[str]:
        result = await client.list_tools()
        tools = result.tools if hasattr(result, "tools") else result
        return {t.name for t in tools}

    names = _with_client(_call)
    assert names == {
        "get_transaction",
        "get_account",
        "get_account_transactions",
        "get_recipient_history",
        "get_device_history",
        "get_ip_history",
    }


def test_get_transaction_smoke() -> None:
    """TXN-001 retrieved from PostgreSQL through the MCP protocol path."""
    payload = _call_tool("get_transaction", {"transaction_id": "TXN-001"})

    assert payload["transaction_id"] == "TXN-001"
    assert payload["amount"] == "8400.00"
    assert payload["currency"] == "USD"
    assert payload["transaction_type"] == "WIRE"
    assert payload["sender"]["external_id"] == "ACC-1001"
    assert payload["recipient"]["external_id"] == "ACC-9001"
    assert payload["device"]["external_id"] == "DEV-123"
    assert payload["ip"]["address"] == SAFE_DOC_IP
    assert payload["is_new_device"] is True
    assert payload["is_new_ip"] is True
    assert payload["data_source"] == "POSTGRES"
    assert payload["metadata"] == {"channel": "mobile", "reference": "SEED-CASE-001"}


def test_get_transaction_not_found_payload() -> None:
    payload = _call_tool("get_transaction", {"transaction_id": "TXN-999"})

    assert payload == {"error": "NOT_FOUND", "resource": "transaction", "id": "TXN-999"}


def test_get_account_smoke() -> None:
    payload = _call_tool("get_account", {"account_id": "ACC-1001"})

    assert payload["account_id"] == "ACC-1001"
    assert payload["customer_name"] == "John Anderson"
    assert payload["account_type"] == "CHECKING"
    assert payload["country"] == "US"
    assert payload["status"] == "ACTIVE"
    assert payload["risk_level"] == "HIGH"


def test_get_account_not_found_payload() -> None:
    payload = _call_tool("get_account", {"account_id": "ACC-999"})

    assert payload["error"] == "NOT_FOUND"
    assert payload["resource"] == "account"
    assert payload["id"] == "ACC-999"


def test_get_account_transactions_smoke() -> None:
    payload = _call_tool("get_account_transactions", {"account_id": "ACC-1001", "limit": 2})

    assert payload["count"] == 2
    assert payload["limit"] == 2
    assert payload["truncated"] is True
    assert payload["items"][0]["transaction_id"] == "TXN-001"  # newest first


def test_get_account_transactions_limit_validation() -> None:
    for bad_limit in (0, -3, 1000):  # below min, negative, above max
        payload = _call_tool(
            "get_account_transactions", {"account_id": "ACC-1001", "limit": bad_limit}
        )
        assert payload["error"] == "VALIDATION_ERROR"
        assert payload["field"] == "limit"


def test_get_account_transactions_nonexistent_account() -> None:
    payload = _call_tool("get_account_transactions", {"account_id": "ACC-999"})

    assert payload["error"] == "NOT_FOUND"
    assert payload["resource"] == "account"


def test_get_recipient_history_smoke() -> None:
    payload = _call_tool("get_recipient_history", {"recipient_account_id": "ACC-9001"})

    assert {item["transaction_id"] for item in payload["items"]} == {
        "TXN-001",
        "TXN-1004",
        "TXN-1006",
    }
    assert all(item["recipient_account_id"] == "ACC-9001" for item in payload["items"])


def test_get_recipient_history_nonexistent() -> None:
    payload = _call_tool("get_recipient_history", {"recipient_account_id": "ACC-999"})

    assert payload["error"] == "NOT_FOUND"


def test_get_device_history_smoke() -> None:
    payload = _call_tool("get_device_history", {"device_id": "DEV-123"})

    assert payload["device"]["external_id"] == "DEV-123"
    assert {item["transaction_id"] for item in payload["items"]} == {
        "TXN-001",
        "TXN-1003",
        "TXN-1006",
    }


def test_get_device_history_nonexistent() -> None:
    payload = _call_tool("get_device_history", {"device_id": "DEV-999"})

    assert payload["error"] == "NOT_FOUND"
    assert payload["resource"] == "device"


def test_get_ip_history_smoke() -> None:
    payload = _call_tool("get_ip_history", {"ip_address": SAFE_DOC_IP})

    assert payload["ip"]["address"] == SAFE_DOC_IP
    assert {item["transaction_id"] for item in payload["items"]} == {
        "TXN-001",
        "TXN-1003",
        "TXN-1006",
    }


def test_get_ip_history_nonexistent() -> None:
    payload = _call_tool("get_ip_history", {"ip_address": "203.0.113.1"})

    assert payload["error"] == "NOT_FOUND"
    assert payload["resource"] == "ip"


def test_unknown_tool_is_protocol_error() -> None:
    """Unknown tools produce protocol-level error results, never fake data."""
    result = _call_tool_raw("no_such_tool", {})

    assert result.is_error is True
    text = " ".join(getattr(block, "text", "") for block in result.content)
    assert "Unknown tool" in text or "no_such_tool" in text


def test_empty_id_returns_validation_error() -> None:
    payload = _call_tool("get_transaction", {"transaction_id": "   "})

    assert payload["error"] == "VALIDATION_ERROR"
    assert payload["field"] == "transaction_id"


def test_missing_required_argument_fails_cleanly() -> None:
    """Schema-invalid calls fail as tool errors without leaking internals."""
    result = _call_tool_raw("get_transaction", {})

    assert result.is_error is True
    json.dumps([block.model_dump(mode="json") for block in result.content])
