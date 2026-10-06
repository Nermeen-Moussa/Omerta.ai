"""Phase 12 - Knowledge MCP protocol tests (in-memory transport).

Same approach as Phases 5/6/7: synchronous tests that talk to the shared
``MCPServer`` through a real MCP ``Client`` over seeded omerta_test data,
proving MCP -> knowledge service -> PostgreSQL. Document content is data.
"""

import asyncio
import json
from typing import Any

import pytest
from infrastructure.database.seed import reset_all, seed
from mcp.client.client import Client
from mcp_servers.knowledge_server.server import server
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(autouse=True)
def seeded_db_sync(test_engine: AsyncEngine) -> None:
    """Reset, seed (including knowledge ingestion) before each test."""

    async def _seed() -> None:
        await reset_all(test_engine)
        await seed(test_engine)

    asyncio.run(_seed())


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a knowledge tool over the MCP protocol and validate its payload."""

    async def _runner() -> dict[str, Any]:
        async with Client(server) as client:
            result = await client.call_tool(name, arguments)
            assert result.is_error is False
            payload = result.structured_content
            json.dumps(payload)  # must be JSON-serializable
            assert isinstance(payload, dict)
            return payload

    return asyncio.run(_runner())


def test_list_tools_exposes_three_knowledge_tools() -> None:
    async def _runner() -> list[str]:
        async with Client(server) as client:
            listing = await client.list_tools()
            tools = listing.tools if hasattr(listing, "tools") else listing
            return sorted(tool.name for tool in tools)

    names = asyncio.run(_runner())
    assert names == ["get_document", "get_document_section", "search_knowledge"]


def test_search_knowledge_returns_provenance() -> None:
    payload = _call_tool("search_knowledge", {"query": "shared device ring", "top_k": 2})
    assert payload["count"] == len(payload["results"])
    assert 1 <= payload["count"] <= 2
    top = payload["results"][0]
    # Full provenance on every chunk.
    for field in (
        "chunk_id",
        "document_id",
        "document_title",
        "document_type",
        "section",
        "jurisdiction",
        "effective_date",
        "version",
        "content",
        "score",
    ):
        assert field in top, f"missing provenance field: {field}"
    assert top["score"] > 0
    assert payload["note"].lower().startswith("stored policy")


def test_search_knowledge_mule_query_ranks_mule_section_first() -> None:
    payload = _call_tool("search_knowledge", {"query": "mule account pass through"})
    assert payload["count"] >= 1
    assert payload["results"][0]["section"] == "Mule Accounts"
    assert payload["results"][0]["document_id"] == "DOC-FATF-TYPOLOGIES"


def test_search_knowledge_empty_result_is_explicit() -> None:
    payload = _call_tool("search_knowledge", {"query": "zzzqqqxyzzy gibberishonlytoken qqqwwwwxyz"})
    assert payload["count"] == 0
    assert payload["results"] == []


def test_search_knowledge_rejects_invalid_input() -> None:
    payload = _call_tool("search_knowledge", {"query": ""})
    assert payload["error"] == "VALIDATION_ERROR"
    payload = _call_tool("search_knowledge", {"query": "x" * 600})
    assert payload["error"] == "VALIDATION_ERROR"
    payload = _call_tool("search_knowledge", {"query": "mule", "top_k": 99})
    assert payload["error"] == "VALIDATION_ERROR"


def test_search_knowledge_deterministic_ranking() -> None:
    args = {"query": "structuring deposits below threshold", "top_k": 3}
    first = _call_tool("search_knowledge", args)
    second = _call_tool("search_knowledge", args)
    assert first == second


def test_get_document_full_and_missing() -> None:
    payload = _call_tool("get_document", {"document_id": "DOC-THRESHOLD-POLICY"})
    assert payload["document_id"] == "DOC-THRESHOLD-POLICY"
    assert payload["document_type"] == "POLICY"
    assert payload["version"] == 2
    assert len(payload["sections"]) == 2
    assert payload["source"]

    missing = _call_tool("get_document", {"document_id": "DOC-NOPE"})
    assert missing["error"] == "NOT_FOUND"
    assert missing["resource"] == "knowledge_document"


def test_get_document_section_ok_and_missing() -> None:
    payload = _call_tool(
        "get_document_section",
        {"document_id": "DOC-FATF-TYPOLOGIES", "section": "Account Takeover"},
    )
    assert payload["section"] == "Account Takeover"
    assert "takeover" in payload["content"].lower()

    missing = _call_tool(
        "get_document_section",
        {"document_id": "DOC-FATF-TYPOLOGIES", "section": "No Such Section"},
    )
    assert missing["error"] == "NOT_FOUND"
    assert missing["resource"] == "knowledge_section"


def test_tool_payloads_leak_no_secrets() -> None:
    payload = _call_tool("search_knowledge", {"query": "mule accounts"})
    dumped = json.dumps(payload).lower()
    for forbidden in ("password", "api_key", "authorization", "postgresql", "bolt://"):
        assert forbidden not in dumped, f"leaked: {forbidden}"
