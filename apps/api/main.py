"""Omerta.ai API entrypoint.

Health endpoints for the API, PostgreSQL, and Neo4j. Domain routers
(investigate, cases, alerts) will be mounted in later phases.
"""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from infrastructure.database.session import get_engine
from infrastructure.neo4j import client as graph_client
from sqlalchemy import text

from apps.investigator.state import InvestigationRunRequest

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Omerta.ai API",
    version="0.1.0",
    description="Agentic AI financial-crime investigation platform",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe for local development and container orchestration."""
    return {"status": "ok", "service": "omerta-api", "version": app.version}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    """Readiness probe: verifies PostgreSQL connectivity."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any DB failure means "not ready"
        raise HTTPException(status_code=503, detail="database unreachable") from exc
    return {"status": "ok", "service": "omerta-api", "database": "ok", "version": app.version}


@app.get("/health/neo4j")
async def health_neo4j() -> dict[str, str]:
    """Readiness probe: verifies Neo4j connectivity (no internals exposed)."""
    try:
        rows = await graph_client.read_query("RETURN 1 AS ok", {})
        if not rows or rows[0].get("ok") != 1:
            raise RuntimeError("unexpected Neo4j response")
    except Exception as exc:  # noqa: BLE001 - any failure means "not ready"
        raise HTTPException(status_code=503, detail="neo4j unreachable") from exc
    return {"status": "ok", "service": "omerta-api", "neo4j": "ok", "version": app.version}


@app.get("/health/risk")
async def health_risk() -> dict[str, str]:
    """Risk subsystem health: reports the configured provider (mock).

    Deliberately does NOT claim an ML model is healthy - none exists yet.
    """
    from infrastructure.risk.mock_provider import get_provider

    provider = get_provider()
    return {
        "status": "ok",
        "service": "risk",
        "provider": provider.source.lower(),
        "model_version": provider.model_version,
        "version": app.version,
    }


@app.post("/investigations/run")
async def run_investigation_endpoint(body: InvestigationRunRequest) -> dict[str, Any]:
    """Run one investigation (deterministic; agent report via fake provider
    unless a real LLM is configured). Optionally persists case + evidence.

    Returns 200 with the investigation state; persistence is explicit opt-in
    (``persist: true``). Failures come back as structured error payloads -
    never stack traces or credentials.
    """
    from infrastructure.database.persistence import persist_investigation
    from infrastructure.database.session import get_engine

    from apps.investigator.graph import run_investigation_async

    final = await run_investigation_async(body.transaction_id, body.alert_id)
    if not body.persist or final.get("status") != "COMPLETED":
        return final
    try:
        persisted = await persist_investigation(
            get_engine(),
            investigation_id=final["investigation_id"],
            transaction_id=body.transaction_id,
            alert_id=body.alert_id,
            report=final.get("report") or {},
            evidence=final.get("evidence", []),
            audit_events=final.get("audit_events", []),
        )
    except Exception:  # noqa: BLE001 - log internally, respond with structure
        logger.exception("investigation persistence failed")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "PERSISTENCE_ERROR",
                "message": "investigation completed but could not be persisted",
            },
        ) from None
    final["persistence"] = persisted
    return final
