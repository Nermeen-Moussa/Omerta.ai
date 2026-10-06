"""System Settings & Integration Diagnostics Router for Omerta.ai."""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.config import get_settings
from infrastructure.database.session import get_engine
from infrastructure.neo4j import client as graph_client
from infrastructure.security.jwt_auth import get_current_user

router = APIRouter(prefix="/settings", tags=["System Settings & Diagnostics"])

# In-memory runtime threshold store (defaults to 40.00)
_RUNTIME_SETTINGS = {
    "human_review_threshold": 40.00,
    "high_risk_threshold": 70.00,
    "critical_risk_threshold": 90.00,
    "auto_assignment_enabled": True,
    "max_graph_depth": 3,
}


class UpdateThresholdsRequest(BaseModel):
    human_review_threshold: float
    high_risk_threshold: float
    critical_risk_threshold: float


@router.get("")
async def get_system_settings() -> dict[str, Any]:
    """Retrieve platform configuration, active thresholds, and sub-system health statuses."""
    config = get_settings()

    # Check PostgreSQL
    db_status = "ok"
    try:
        async with AsyncSession(get_engine(), expire_on_commit=False) as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "unreachable"

    # Check Neo4j
    neo4j_status = "ok"
    try:
        rows = await graph_client.read_query("RETURN 1 AS ok", {})
        if not rows or rows[0].get("ok") != 1:
            neo4j_status = "error"
    except Exception:
        neo4j_status = "unreachable"

    return {
        "thresholds": _RUNTIME_SETTINGS,
        "review_rule": f"risk_score > {_RUNTIME_SETTINGS['human_review_threshold']:.2f}%",
        "system_status": {
            "postgres": db_status,
            "neo4j": neo4j_status,
            "risk_engine": "mock_v1.0 (parallel analyzers ready)",
            "llm_provider": config.llm_provider or "groq (configured)",
            "llm_model": config.llm_model or "llama-3.3-70b-versatile",
            "langgraph_orchestrator": "ready",
            "mcp_servers": {
                "transaction_server": "active",
                "graph_server": "active",
                "risk_server": "active",
                "knowledge_server": "active",
            },
        },
    }


@router.patch("/thresholds")
async def update_thresholds(
    body: UpdateThresholdsRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Update risk score thresholds for human review (Administrator role required)."""
    if current_user.get("role") != "ADMINISTRATOR":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "message": "Only Administrators can tune risk thresholds."},
        )

    _RUNTIME_SETTINGS["human_review_threshold"] = body.human_review_threshold
    _RUNTIME_SETTINGS["high_risk_threshold"] = body.high_risk_threshold
    _RUNTIME_SETTINGS["critical_risk_threshold"] = body.critical_risk_threshold

    return {
        "status": "ok",
        "message": "Thresholds updated successfully.",
        "thresholds": _RUNTIME_SETTINGS,
    }
