"""Regulatory Audit Logs Router for Omerta.ai."""

from typing import Any
from fastapi import APIRouter, Query
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import AuditEvent
from infrastructure.database.session import get_engine

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get("/logs")
async def list_audit_logs(
    event_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
) -> dict[str, Any]:
    """Retrieve immutable chronological audit trail of all compliance and system actions."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        query = select(AuditEvent)
        conditions = []

        if event_type:
            conditions.append(AuditEvent.event_type == event_type.upper())
        if actor_id:
            conditions.append(AuditEvent.actor_id.ilike(f"%{actor_id.strip()}%"))
        if actor_type:
            conditions.append(AuditEvent.actor_type == actor_type.upper())
        if search:
            clean = f"%{search.strip()}%"
            conditions.append(
                or_(
                    AuditEvent.event_id.ilike(clean),
                    AuditEvent.transaction_id.ilike(clean),
                    AuditEvent.investigation_id.ilike(clean),
                    AuditEvent.source.ilike(clean),
                )
            )

        if conditions:
            query = query.where(*conditions)

        count_q = select(func.count(AuditEvent.id))
        if conditions:
            count_q = count_q.where(*conditions)
        total = await session.scalar(count_q) or 0

        offset = (max(1, page) - 1) * page_size
        query = query.order_by(desc(AuditEvent.id)).offset(offset).limit(page_size)
        rows = (await session.scalars(query)).all()

        items = []
        for ev in rows:
            items.append({
                "id": ev.id,
                "event_id": ev.event_id,
                "event_type": ev.event_type,
                "action": ev.event_type,
                "actor_type": ev.actor_type,
                "actor_id": ev.actor_id or "SYSTEM",
                "source": ev.source,
                "case_id": ev.case_id,
                "investigation_id": ev.investigation_id,
                "transaction_id": ev.transaction_id,
                "metadata": ev.metadata_ or {},
                "created_at": ev.created_at.isoformat(),
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }
