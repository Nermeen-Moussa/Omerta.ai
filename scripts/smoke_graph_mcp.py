"""Development smoke test for the Graph MCP server over real stdio.

Spawns the server as a subprocess (as an MCP host would) and exercises all
six graph tools against the projected Neo4j graph (dev projection namespace).

Usage (requires PostgreSQL seed + graph projection, see README):
    uv run python scripts/smoke_graph_mcp.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

from mcp.client.client import Client, StdioServerParameters

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# (tool, arguments, expected_outcome)
TOOLS: list[tuple[str, dict[str, Any], str]] = [
    ("get_account_neighbors", {"account_id": "ACC-1001"}, "ok"),
    ("find_connected_accounts", {"account_id": "ACC-1001"}, "ok"),
    ("find_shared_devices", {"account_id": "ACC-1001"}, "ok"),
    ("find_shared_ips", {"account_id": "ACC-1001"}, "ok"),
    (
        "find_transaction_paths",
        {"source_account_id": "ACC-1001", "target_account_id": "ACC-9001"},
        "ok",
    ),
    ("find_fraud_ring", {"account_id": "ACC-9001"}, "ok"),
    ("find_shared_devices", {"account_id": "ACC-999"}, "not_found"),
]


async def _smoke() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_servers.graph_server.server"],
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
    print("\nAll graph tool calls behaved as expected.")


if __name__ == "__main__":
    main()
