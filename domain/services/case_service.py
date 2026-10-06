"""Case service (Phase 13): read-only case/investigation queries.

Reads through the existing Phase 11 reconstruction service (fail-closed) for
detail views and queries cases/evidence/audit rows directly for list views.
No business logic is duplicated; no SQL ever reaches the API routes.
"""

import logging
from typing import Any

from infrastructure.database.models import (
    Alert,
    AuditEvent,
    Evidence,
    InvestigationCase,
    Transaction,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.errors import NotFoundError
from domain.services.audit_service import get_investigation_audit

logger = logging.getLogger(__name__)

MAX_LIMIT = 100


class CaseService:
    """Read-only case/investigation access for the Case Management API."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_cases(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        transaction_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Paginated case summaries (newest first) with optional filters."""
        limit = max(1, min(int(limit), MAX_LIMIT))
        offset = max(0, int(offset))

        conditions = []
        if status:
            conditions.append(InvestigationCase.status == status.strip().upper())
        if severity:
            conditions.append(InvestigationCase.severity == severity.strip().upper())
        if transaction_id:
            conditions.append(
                InvestigationCase.alert.has(
                    Alert.transaction.has(Transaction.external_id == transaction_id.strip())
                )
            )

        base = select(InvestigationCase).options(
            selectinload(InvestigationCase.alert).selectinload(Alert.transaction)
        )
        if conditions:
            base = base.where(*conditions)
        total = await self.session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            (
                await self.session.execute(
                    base.order_by(InvestigationCase.created_at.desc(), InvestigationCase.id.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )

        items = []
        for case in rows:
            evidence_count = await self.session.scalar(
                select(func.count()).select_from(Evidence).where(Evidence.case_id == case.id)
            )
            event_count = await self.session.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.case_id == case.id)
            )
            items.append(
                {
                    "case_id": case.external_id,
                    "investigation_id": case.external_id,
                    "alert_id": case.alert.external_id if case.alert else None,
                    "transaction_id": (case.alert.transaction.external_id if case.alert else None),
                    "status": case.status,
                    "severity": case.severity,
                    "assigned_to": case.assigned_to,
                    "created_at": case.created_at.isoformat() if case.created_at else None,
                    "evidence_count": evidence_count or 0,
                    "audit_event_count": event_count or 0,
                }
            )
        return {"items": items, "total": total or 0, "limit": limit, "offset": offset}

    async def get_investigation_detail(self, investigation_id: str) -> dict[str, Any]:
        """Fail-closed reconstruction via the Phase 11 service.

        Raises NotFoundError for unknown investigations; ReconstructionError
        (from the domain service) propagates untouched so integrity failures
        are never presented as success.
        """
        from infrastructure.database.session import get_engine

        exists = await self.session.scalar(
            select(InvestigationCase.external_id).where(
                InvestigationCase.external_id == investigation_id.strip()
            )
        )
        if exists is None:
            raise NotFoundError("investigation", investigation_id)
        return await get_investigation_audit(get_engine(), investigation_id.strip())
