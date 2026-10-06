"""Risk MCP server: read-only risk information over a deterministic mock
provider. PostgreSQL supplies the facts; the provider supplies mock scoring.

Run locally over stdio:
    uv run python -m mcp_servers.risk_server.server
"""

from typing import Any

from mcp.server.mcpserver import MCPServer

from mcp_servers.risk_server import tools

server: MCPServer = MCPServer(
    name="omerta-risk-server",
    title="Omerta.ai Risk MCP Server",
    description=(
        "Read-only transaction risk information. Phase 7 uses a deterministic "
        "MOCK provider (mock-risk-v1) - this is NOT a trained ML fraud model. "
        "The schema is stable for a future ML engine."
    ),
    version="0.1.0",
)


@server.tool(
    name="get_risk_score",
    description="Deterministic mock risk score (source=MOCK, model_version=mock-risk-v1).",
)
async def get_risk_score(transaction_id: str) -> dict[str, Any]:
    return await tools.get_risk_score(transaction_id)


@server.tool(
    name="get_risk_features",
    description="Risk features derived strictly from PostgreSQL facts (nothing fabricated).",
)
async def get_risk_features(transaction_id: str) -> dict[str, Any]:
    return await tools.get_risk_features(transaction_id)


@server.tool(
    name="get_feature_importance",
    description="Mock feature contributions behind the score - not SHAP, not a trained model.",
)
async def get_feature_importance(transaction_id: str) -> dict[str, Any]:
    return await tools.get_feature_importance(transaction_id)


@server.tool(
    name="get_previous_risk_events",
    description="Stored (seeded) alert facts for an account; empty result when none.",
)
async def get_previous_risk_events(account_id: str) -> dict[str, Any]:
    return await tools.get_previous_risk_events(account_id)


def main() -> None:
    """Stdio entrypoint for local development."""
    server.run()


if __name__ == "__main__":
    main()
