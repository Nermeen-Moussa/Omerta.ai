"""Development smoke test for the Risk MCP server over real stdio.

Spawns the server as a subprocess (as an MCP host would) and exercises all
four tools, verifying the explicit MOCK provenance contract.

Usage (requires migrations + seed data, see README):
    uv run python scripts/smoke_risk_mcp.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

from mcp.client.client import Client, StdioServerParameters

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# (tool, arguments, expected_outcome)
TOOLS: list[tuple[str, dict[str, Any], str]] = [
    ("get_risk_score", {"transaction_id": "TXN-001"}, "ok"),
    ("get_risk_features", {"transaction_id": "TXN-001"}, "ok"),
    ("get_feature_importance", {"transaction_id": "TXN-001"}, "ok"),
    ("get_previous_risk_events", {"account_id": "ACC-1001"}, "ok"),
    ("get_previous_risk_events", {"account_id": "ACC-9001"}, "ok_empty"),
    ("get_risk_score", {"transaction_id": "TXN-999"}, "not_found"),
]


async def _smoke() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_servers.risk_server.server"],
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
            elif expected == "ok_empty":
                status = "OK" if payload.get("count") == 0 else "UNEXPECTED"
            else:
                status = "OK" if not result.is_error and "error" not in payload else "ERROR"
            # MOCK provenance contract: any payload carrying a `source` field
            # must declare MOCK (never an ML model name).
            if status == "OK" and payload.get("source") not in (None, "MOCK"):
                status = "MOCK_VIOLATION"
            if status != "OK":
                failures += 1
            print(f"[{status}] {name}({arguments}) -> {str(payload)[:110]}")
    return failures


def main() -> None:
    failures = asyncio.run(_smoke())
    if failures:
        print(f"\n{failures} tool call(s) failed expectations")
        raise SystemExit(1)
    print("\nAll risk tool calls behaved as expected (source=MOCK verified).")


if __name__ == "__main__":
    main()
