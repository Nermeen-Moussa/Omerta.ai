"""Omerta.ai API entrypoint.

Health endpoints, the investigation run endpoint (Phase 10), and the
Case Management API (Phase 13). Routes stay thin: typed schemas in, domain
services out; no SQL, no investigation logic, no Neo4j access in routes.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from infrastructure.database.session import get_engine
from infrastructure.neo4j import client as graph_client
from sqlalchemy import text

from apps.api.schemas import (
    AuditEventOut,
    CaseListOut,
    CaseSummaryOut,
    EvidenceOut,
    FindingOut,
    InvestigationDetailOut,
    ReportOut,
)
from apps.investigator.state import InvestigationRunRequest

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Omerta.ai API",
    version="0.1.0",
    description="Agentic AI financial-crime investigation platform",
)

# --------------------------------------------------------------------------- #
# Security middleware (Phase 17): API-key auth + rate limiting.
# Both are OFF by default in development/test (no keys configured, limit 0)
# and activate purely through environment configuration.
# --------------------------------------------------------------------------- #

_OPEN_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def security_middleware(request, call_next):
    from infrastructure.security.auth import API_KEY_HEADER, auth_enabled, resolve_role
    from infrastructure.security.ratelimit import get_limiter

    path = request.url.path
    # Static dashboard and health probes stay open.
    if path in _OPEN_PATHS or path.startswith("/static") or path.startswith("/health"):
        return await call_next(request)

    if auth_enabled():
        role = resolve_role(request.headers.get(API_KEY_HEADER))
        if role is None:
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "missing or invalid API key"},
            )
        request.state.role = role

    limiter = get_limiter()
    if limiter.rate_per_minute > 0:
        identity = request.headers.get(API_KEY_HEADER) or (
            request.client.host if request.client else "unknown"
        )
        if not limiter.allow(identity):
            return JSONResponse(
                status_code=429,
                content={"error": "RATE_LIMITED", "message": "too many requests"},
            )
    return await call_next(request)


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
    """Risk subsystem health: reports the configured provider (mock/ML)."""
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


# --------------------------------------------------------------------------- #
# Case Management API (Phase 13) - read-only, typed, structured errors
# --------------------------------------------------------------------------- #


def _to_http_error(exc: Exception) -> HTTPException:
    """Map one exception to a structured HTTP error (never internals)."""
    from domain.errors import ConflictError, DomainError, NotFoundError, ValidationError
    from domain.services.audit_service import ReconstructionError

    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=exc.payload)
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=422, detail=exc.payload)
    if isinstance(exc, (ConflictError, ReconstructionError)):
        return HTTPException(
            status_code=409,
            detail={"error": "CONFLICT", "message": "persisted state failed validation"},
        )
    if isinstance(exc, DomainError):
        return HTTPException(status_code=503, detail=exc.payload)
    logger.exception("case api failure")
    return HTTPException(
        status_code=503,
        detail={"error": "DEPENDENCY_ERROR", "message": "upstream store unavailable"},
    )


def _report_out(payload: dict[str, Any] | None) -> ReportOut | None:
    """Convert a stored report snapshot into the typed schema (or None)."""
    if not payload:
        return None
    return ReportOut(
        investigation_id=str(payload.get("investigation_id", "")),
        transaction_id=str(payload.get("transaction_id", "")),
        risk_level=str(payload.get("risk_level", "")),
        summary=str(payload.get("summary", "")),
        typologies=[str(t) for t in payload.get("typologies", [])],
        findings=[FindingOut.model_validate(f) for f in payload.get("findings", [])],
        recommended_action=str(payload.get("recommended_action", "")),
        confidence=float(payload.get("confidence", 0)),
        provenance=dict(payload.get("provenance", {})),
        generated_at=payload.get("generated_at"),
    )


@app.get("/investigations")
async def list_investigations(
    status: str | None = Query(default=None, max_length=32),
    severity: str | None = Query(default=None, max_length=16),
    transaction_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CaseListOut:
    """Paginated case/investigation list (newest first) with filters."""
    from domain.services.case_service import CaseService
    from sqlalchemy.ext.asyncio import AsyncSession

    try:
        async with AsyncSession(get_engine(), expire_on_commit=False) as session:
            result = await CaseService(session).list_cases(
                status=status,
                severity=severity,
                transaction_id=transaction_id,
                limit=limit,
                offset=offset,
            )
    except Exception as exc:  # noqa: BLE001
        raise _to_http_error(exc) from None
    return CaseListOut(
        items=[CaseSummaryOut(**item) for item in result["items"]],
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
    )


async def _load_detail(investigation_id: str) -> dict[str, Any]:
    """Fail-closed detail via the domain service (shared by detail routes)."""
    from domain.services.case_service import CaseService
    from sqlalchemy.ext.asyncio import AsyncSession

    # Path-parameter hardening: reject control characters / NUL / separators
    # before anything reaches the database (422, never a 503).
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in investigation_id) or any(
        sep in investigation_id for sep in ("/", "\\")
    ):
        raise HTTPException(
            status_code=422,
            detail={"error": "VALIDATION_ERROR", "message": "invalid identifier"},
        )
    try:
        async with AsyncSession(get_engine(), expire_on_commit=False) as session:
            return await CaseService(session).get_investigation_detail(investigation_id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _to_http_error(exc) from None


@app.get("/investigations/{investigation_id}")
async def get_investigation(investigation_id: str) -> InvestigationDetailOut:
    """Full fail-closed reconstruction of one investigation."""
    detail = await _load_detail(investigation_id)
    return InvestigationDetailOut(
        investigation=detail["investigation"],
        case=detail["case"],
        report=_report_out(detail.get("report")),
        findings=detail["findings"],
        evidence=[EvidenceOut(**e) for e in detail["evidence"]],
        audit_events=[AuditEventOut(**e) for e in detail["audit_events"]],
    )


@app.get("/investigations/{investigation_id}/report")
async def get_investigation_report(investigation_id: str) -> ReportOut:
    """The stored, validated report snapshot for one investigation."""
    detail = await _load_detail(investigation_id)
    report = _report_out(detail.get("report"))
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "resource": "report", "id": investigation_id},
        )
    return report


@app.get("/investigations/{investigation_id}/evidence")
async def get_investigation_evidence(
    investigation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    tier: str | None = Query(default=None, max_length=32),
    category: str | None = Query(default=None, max_length=32),
) -> dict[str, Any]:
    """Evidence for one investigation, filtered and paginated.

    KNOWLEDGE evidence is identifiable via ``tier=KNOWLEDGE`` /
    ``category=KNOWLEDGE`` and carries document/section provenance in ``data``.
    """
    detail = await _load_detail(investigation_id)
    rows = detail["evidence"]
    if tier:
        rows = [e for e in rows if e["tier"] == tier.strip().upper()]
    if category:
        rows = [e for e in rows if e["category"] == category.strip().upper()]
    return {
        "items": [EvidenceOut(**e).model_dump(mode="json") for e in rows[offset : offset + limit]],
        "total": len(rows),
        "limit": limit,
        "offset": offset,
    }


@app.get("/investigations/{investigation_id}/audit")
async def get_investigation_audit_events(investigation_id: str) -> list[AuditEventOut]:
    """Durable audit events for one investigation (chronological)."""
    detail = await _load_detail(investigation_id)
    return [AuditEventOut(**e) for e in detail["audit_events"]]


@app.get("/cases")
async def list_cases(
    status: str | None = Query(default=None, max_length=32),
    severity: str | None = Query(default=None, max_length=16),
    transaction_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CaseListOut:
    """Alias of GET /investigations (case-centric naming)."""
    return await list_investigations(
        status=status,
        severity=severity,
        transaction_id=transaction_id,
        limit=limit,
        offset=offset,
    )


@app.get("/cases/{case_id}")
async def get_case(case_id: str) -> InvestigationDetailOut:
    """Alias of GET /investigations/{id} (case id == investigation id)."""
    return await get_investigation(case_id)


# --------------------------------------------------------------------------- #
# Frontend dashboard (Phase 16) - static SPA consuming only the Case API
# --------------------------------------------------------------------------- #

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
async def index() -> RedirectResponse:
    """Serve the investigation dashboard."""
    return RedirectResponse(url="/static/index.html")
