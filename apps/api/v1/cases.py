"""Investigation Cases & Analyst Dispositions Router for Omerta.ai."""

from datetime import UTC, datetime
from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import (
    Alert,
    AuditEvent,
    CaseDisposition,
    CaseNote,
    Evidence,
    InvestigationCase,
    Transaction,
)
from infrastructure.database.session import get_engine
from infrastructure.security.jwt_auth import get_current_user

router = APIRouter(prefix="/cases", tags=["Investigation Cases"])


class AddNoteRequest(BaseModel):
    note_text: str


class RecordDispositionRequest(BaseModel):
    disposition: str  # SUSPICIOUS_FURTHER_INVESTIGATION | NO_SUSPICIOUS_ACTIVITY | LEGITIMATE_ACTIVITY | INSUFFICIENT_EVIDENCE | ESCALATED_SPECIALIST
    rationale: str
    new_status: str = "RESOLVED"


class UpdateCaseStatusRequest(BaseModel):
    status: str
    assigned_to: str | None = None


@router.get("")
async def list_cases(
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """List investigation cases with status and severity filters."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        query = select(InvestigationCase).options(
            selectinload(InvestigationCase.alert),
            selectinload(InvestigationCase.transaction),
        )

        conditions = []
        if status_filter:
            conditions.append(InvestigationCase.status == status_filter.upper())
        if severity:
            conditions.append(InvestigationCase.severity == severity.upper())
        if assigned_to:
            conditions.append(InvestigationCase.assigned_to == assigned_to)

        if conditions:
            query = query.where(*conditions)

        count_q = select(func.count(InvestigationCase.id))
        if conditions:
            count_q = count_q.where(*conditions)
        total = await session.scalar(count_q) or 0

        offset = (max(1, page) - 1) * page_size
        query = query.order_by(desc(InvestigationCase.id)).offset(offset).limit(page_size)
        cases = (await session.scalars(query)).all()

        items = []
        for c in cases:
            items.append({
                "id": c.id,
                "external_id": c.external_id,
                "title": c.title,
                "status": c.status,
                "severity": c.severity,
                "assigned_to": c.assigned_to,
                "alert_id": c.alert.external_id if c.alert else None,
                "transaction_id": c.transaction.external_id if c.transaction else None,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }


@router.get("/{case_id}")
async def get_case_detail(case_id: str) -> dict[str, Any]:
    """Retrieve full investigation case details, evidence, notes, and dispositions."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        query = (
            select(InvestigationCase)
            .options(
                selectinload(InvestigationCase.alert),
                selectinload(InvestigationCase.transaction),
                selectinload(InvestigationCase.evidence),
                selectinload(InvestigationCase.notes),
                selectinload(InvestigationCase.dispositions),
                selectinload(InvestigationCase.audit_events),
            )
        )
        if case_id.isdigit():
            query = query.where(or_(InvestigationCase.id == int(case_id), InvestigationCase.external_id == case_id))
        else:
            query = query.where(InvestigationCase.external_id == case_id)

        case = await session.scalar(query)
        if not case:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": f"Case {case_id} not found"})

        return {
            "case": {
                "id": case.id,
                "external_id": case.external_id,
                "title": case.title,
                "status": case.status,
                "severity": case.severity,
                "assigned_to": case.assigned_to,
                "created_at": case.created_at.isoformat(),
                "updated_at": case.updated_at.isoformat(),
                "report": case.report or {},
            },
            "alert": {
                "id": case.alert.id,
                "external_id": case.alert.external_id,
                "alert_type": case.alert.alert_type,
                "risk_score": float(case.alert.risk_score),
                "risk_level": case.alert.risk_level,
                "status": case.alert.status,
            } if case.alert else None,
            "transaction": {
                "id": case.transaction.id,
                "external_id": case.transaction.external_id,
                "amount": float(case.transaction.amount),
                "currency": case.transaction.currency,
                "risk_score": float(case.transaction.risk_score) if case.transaction.risk_score is not None else 0.0,
            } if case.transaction else None,
            "evidence": [
                {
                    "id": e.id,
                    "evidence_id": e.evidence_id,
                    "tier": e.tier,
                    "evidence_type": e.evidence_type,
                    "source": e.source,
                    "description": e.description,
                    "data": e.data,
                }
                for e in case.evidence
            ],
            "notes": [
                {
                    "id": n.id,
                    "author": n.author,
                    "note_text": n.note_text,
                    "created_at": n.created_at.isoformat(),
                }
                for n in case.notes
            ],
            "dispositions": [
                {
                    "id": d.id,
                    "analyst_id": d.analyst_id,
                    "disposition": d.disposition,
                    "rationale": d.rationale,
                    "recorded_at": d.recorded_at.isoformat(),
                }
                for d in case.dispositions
            ],
            "audit_events": [
                {
                    "id": ev.id,
                    "event_type": ev.event_type,
                    "actor_type": ev.actor_type,
                    "actor_id": ev.actor_id,
                    "created_at": ev.created_at.isoformat(),
                }
                for ev in case.audit_events
            ],
        }


@router.post("/{case_id}/notes", status_code=status.HTTP_201_CREATED)
async def add_case_note(
    case_id: str,
    body: AddNoteRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Attach an analyst note to the investigation case."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        case = await session.scalar(
            select(InvestigationCase).where(
                (InvestigationCase.external_id == case_id) | (InvestigationCase.id == (int(case_id) if case_id.isdigit() else -1))
            )
        )
        if not case:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Case not found"})

        note = CaseNote(
            case_id=case.id,
            author=current_user.get("username", "analyst@omerta.ai"),
            note_text=body.note_text,
        )
        session.add(note)

        # Log audit event
        session.add(AuditEvent(
            case_id=case.id,
            investigation_id=case.external_id,
            transaction_id=case.external_id,
            event_type="ANALYST_NOTE_ADDED",
            actor_type="ANALYST",
            actor_id=current_user.get("username", "analyst@omerta.ai"),
            source="case_management_api",
            metadata_={"note_length": len(body.note_text)},
            event_id=f"EVT-{uuid.uuid4().hex[:12]}",
        ))
        await session.commit()
        return {"status": "ok", "message": "Note added successfully"}


@router.post("/{case_id}/disposition", status_code=status.HTTP_200_OK)
async def record_case_disposition(
    case_id: str,
    body: RecordDispositionRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Record a formal compliance review disposition and update case lifecycle."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        case = await session.scalar(
            select(InvestigationCase).where(
                (InvestigationCase.external_id == case_id) | (InvestigationCase.id == (int(case_id) if case_id.isdigit() else -1))
            )
        )
        if not case:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": "Case not found"})

        disposition = CaseDisposition(
            case_id=case.id,
            analyst_id=current_user.get("username", "analyst@omerta.ai"),
            disposition=body.disposition,
            rationale=body.rationale,
            recorded_at=datetime.now(UTC),
        )
        session.add(disposition)

        # Transition case status
        case.status = body.new_status
        if case.alert_id:
            alert = await session.get(Alert, case.alert_id)
            if alert:
                alert.status = "RESOLVED"

        # Log durable audit event
        session.add(AuditEvent(
            case_id=case.id,
            investigation_id=case.external_id,
            transaction_id=case.external_id,
            event_type="DISPOSITION_RECORDED",
            actor_type="ANALYST",
            actor_id=current_user.get("username", "analyst@omerta.ai"),
            source="compliance_review_workflow",
            metadata_={
                "disposition": body.disposition,
                "rationale": body.rationale,
                "new_status": body.new_status,
            },
            event_id=f"EVT-{uuid.uuid4().hex[:12]}",
        ))
        await session.commit()

        return {
            "status": "ok",
            "case_id": case.external_id,
            "disposition": body.disposition,
            "case_status": case.status,
            "message": "Disposition recorded and immutable audit trail updated.",
        }
