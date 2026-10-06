"""Development smoke test for the Transaction MCP server over real stdio.

Spawns the server as a subprocess (exactly how an MCP host would launch it)
and exercises all six tools against the configured database.

Usage (requires migrations + seed data, see README):
    uv run python scripts/smoke_transaction_mcp.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

from mcp.client.client import Client, StdioServerParameters

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# (tool, arguments, expected_outcome) where expected_outcome is
# "ok" for data results or "not_found" for the structured NOT_FOUND payload.
TOOLS: list[tuple[str, dict[str, Any], str]] = [
    ("get_transaction", {"transaction_id": "TXN-001"}, "ok"),
    ("get_account", {"account_id": "ACC-1001"}, "ok"),
    ("get_account_transactions", {"account_id": "ACC-1001", "limit": 3}, "ok"),
    ("get_recipient_history", {"recipient_account_id": "ACC-9001"}, "ok"),
    ("get_device_history", {"device_id": "DEV-123"}, "ok"),
    ("get_ip_history", {"ip_address": "202.0.113.77"}, "ok"),
    ("get_transaction", {"transaction_id": "TXN-999"}, "not_found"),
]


async def _smoke() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_servers.transaction_server.server"],
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
    print("\nAll tool calls behaved as expected.")


if __name__ == "__main__":
    main()
