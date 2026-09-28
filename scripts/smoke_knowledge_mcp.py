"""Development smoke test for the Knowledge MCP server over real stdio.

Spawns the server as a subprocess (exactly how an MCP host would launch it)
and exercises all three tools against the configured database.

Usage (requires migrations + seed data, see README):
    uv run python scripts/smoke_knowledge_mcp.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

from mcp.client.client import Client, StdioServerParameters

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# (tool, arguments, expected_outcome) where expected_outcome is
# "ok" for data results, "empty" for a valid but empty result set, or
# "not_found" for the structured NOT_FOUND payload.
TOOLS: list[tuple[str, dict[str, Any], str]] = [
    (
        "search_knowledge",
        {"query": "shared device between accounts", "top_k": 2},
        "ok",
    ),
    (
        "search_knowledge",
        {"query": "transaction threshold 10000", "top_k": 3},
        "ok",
    ),
    ("search_knowledge", {"query": "mule account pass through"}, "ok"),
    # Pure gibberish shares no corpus term -> zero scores -> explicit empty.
    (
        "search_knowledge",
        {"query": "zzzqqqxyzzy qqqwwwwxyz gibberishonlytoken"},
        "empty",
    ),
    ("get_document", {"document_id": "DOC-FATF-TYPOLOGIES"}, "ok"),
    ("get_document", {"document_id": "DOC-DOES-NOT-EXIST"}, "not_found"),
    (
        "get_document_section",
        {"document_id": "DOC-FATF-TYPOLOGIES", "section": "Mule Accounts"},
        "ok",
    ),
    (
        "get_document_section",
        {"document_id": "DOC-FATF-TYPOLOGIES", "section": "No Such Section"},
        "not_found",
    ),
]


async def _smoke() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_servers.knowledge_server.server"],
        cwd=str(PROJECT_ROOT),
    )
    failures = 0
    async with Client(params) as client:
        listed = await client.list_tools()
        tools = listed.tools if hasattr(listed, "tools") else listed
        print(f"connected: {len(tools)} tools listed")
        for name, arguments, expected in TOOLS:
            result = await client.call_tool(name, arguments)
            payload = result.structured_content or {}
            if expected == "not_found":
                status = "OK" if payload.get("error") == "NOT_FOUND" else "UNEXPECTED"
            elif expected == "empty":
                status = "OK" if not result.is_error and payload.get("count") == 0 else "UNEXPECTED"
            else:
                status = "OK" if not result.is_error and "error" not in payload else "ERROR"
            if status != "OK":
                failures += 1
            print(f"[{status}] {name}({arguments}) -> {str(payload)[:110]}")
    return failures


def main() -> None:
    failures = asyncio.run(_smoke())
    if failures:
        print(f"\n{failures} tool call(s) failed expectations")
        raise SystemExit(1)
    print("\nAll knowledge tool calls behaved as expected.")


if __name__ == "__main__":
    main()
