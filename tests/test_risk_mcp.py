"""MCP protocol tests for the risk server (in-memory transport, private loops).

Same approach as Phases 5/6: synchronous tests that talk to the shared
``MCPServer`` through a real MCP ``Client`` over seeded omerta_test data,
proving MCP -> risk service -> provider -> PostgreSQL.
"""

import asyncio
import json
from typing import Any

import pytest
from infrastructure.database.seed import reset_all, seed
from mcp.client.client import Client
from mcp_servers.risk_server.server import server
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(autouse=True)
def seeded_db_sync(test_engine: AsyncEngine) -> None:
    """Reset and seed the test database before each risk MCP test."""

    async def _seed() -> None:
        await reset_all(test_engine)
        await seed(test_engine)

    asyncio.run(_seed())


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a risk tool over the MCP protocol and validate its payload."""

    async def _runner() -> dict[str, Any]:
        async with Client(server) as client:
            result = await client.call_tool(name, arguments)
            assert result.is_error is False
            payload = result.structured_content
            json.dumps(payload)  # must be JSON-serializable
            assert isinstance(payload, dict)
            return payload

    return asyncio.run(_runner())


def test_list_tools_exposes_four_risk_tools() -> None:
    async def _runner() -> set[str]:
        async with Client(server) as client:
            listed = await client.list_tools()
            tools = listed.tools if hasattr(listed, "tools") else listed
            return {t.name for t in tools}

    names = asyncio.run(_runner())
    assert names == {
        "get_risk_score",
        "get_risk_features",
        "get_feature_importance",
        "get_previous_risk_events",
    }


def test_get_risk_score_smoke() -> None:
    payload = _call_tool("get_risk_score", {"transaction_id": "TXN-001"})

    assert payload["transaction_id"] == "TXN-001"
    assert payload["source"] == "MOCK"
    assert payload["model_version"] == "mock-risk-v1"
    assert payload["risk_level"] == "HIGH"
    assert 0.0 <= payload["risk_score"] <= 1.0
    assert payload["contributions"]  # deterministic contributions present
    assert payload["seeded_alert"]["alert_id"] == "ALERT-001"


def test_get_risk_score_not_found() -> None:
    payload = _call_tool("get_risk_score", {"transaction_id": "TXN-999"})

    assert payload == {"error": "NOT_FOUND", "resource": "transaction", "id": "TXN-999"}


def test_get_risk_score_deterministic_over_protocol() -> None:
    first = _call_tool("get_risk_score", {"transaction_id": "TXN-001"})
    second = _call_tool("get_risk_score", {"transaction_id": "TXN-001"})
    first.pop("generated_at", None)
    second.pop("generated_at", None)
    assert first == second


def test_get_risk_features_smoke() -> None:
    payload = _call_tool("get_risk_features", {"transaction_id": "TXN-001"})

    assert payload["source"] == "MOCK"
    features = payload["features"]
    assert features["transaction_amount"] == "8400.00"
    assert features["is_new_device"] is True
    assert features["is_new_ip"] is True
    assert features["previous_alert_count"] == 2  # ALERT-001 + ALERT-003 (both on TXN-1001)
    assert features["previous_suspicious_activity"] is True


def test_get_risk_features_not_found() -> None:
    payload = _call_tool("get_risk_features", {"transaction_id": "TXN-999"})

    assert payload["error"] == "NOT_FOUND"


def test_get_feature_importance_smoke() -> None:
    payload = _call_tool("get_feature_importance", {"transaction_id": "TXN-001"})

    assert payload["source"] == "MOCK"
    assert payload["model_version"] == "mock-risk-v1"
    assert "not produced by a trained model" in payload["note"]
    features = [f["feature"] for f in payload["top_features"]]
    assert features, "expected mock contributions"
    assert features[0] == "transaction_amount"


def test_get_feature_importance_not_found() -> None:
    payload = _call_tool("get_feature_importance", {"transaction_id": "TXN-999"})

    assert payload["error"] == "NOT_FOUND"


def test_get_previous_risk_events_smoke() -> None:
    payload = _call_tool("get_previous_risk_events", {"account_id": "ACC-1001"})

    assert payload["count"] == 2
    event = payload["events"][0]
    assert event["alert_id"] == "ALERT-003"
    assert event["risk_score"] == "0.20"
    assert event["origin"] == "seeded_alert_row"
    assert payload["events"][1]["alert_id"] == "ALERT-001"


def test_get_previous_risk_events_empty() -> None:
    payload = _call_tool("get_previous_risk_events", {"account_id": "ACC-9001"})

    assert payload["count"] == 0
    assert payload["events"] == []


def test_get_previous_risk_events_not_found() -> None:
    payload = _call_tool("get_previous_risk_events", {"account_id": "ACC-999"})

    assert payload["error"] == "NOT_FOUND"


def test_empty_id_returns_validation_error() -> None:
    payload = _call_tool("get_risk_score", {"transaction_id": "  "})

    assert payload["error"] == "VALIDATION_ERROR"
    assert payload["field"] == "transaction_id"


def test_missing_required_argument_fails_cleanly() -> None:
    async def _runner() -> Any:
        async with Client(server) as client:
            result = await client.call_tool("get_risk_score", {})
            return [block.model_dump(mode="json") for block in result.content]

    blocks = asyncio.run(_runner())
    assert blocks  # protocol error surfaced as content, no internal details
