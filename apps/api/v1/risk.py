"""Risk Monitoring & Assessment Queue Router for Omerta.ai."""

from decimal import Decimal
from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.services.mock_risk_engine import MockRiskAssessmentEngine
from infrastructure.database.models import Alert, RiskAssessment, RiskSignal, Transaction
from infrastructure.database.session import get_engine

router = APIRouter(prefix="/risk", tags=["Risk Monitoring"])


class AssessTransactionRequest(BaseModel):
    transaction_id: int


@router.get("/monitoring")
async def get_risk_monitoring_queue(
    min_score: float = Query(default=40.0),
    scenario: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """Retrieve the active Human Review Queue (strictly filtered by risk_score > 40.00)."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        query = (
            select(Transaction)
            .options(
                selectinload(Transaction.account),
                selectinload(Transaction.recipient_account),
                selectinload(Transaction.device),
                selectinload(Transaction.ip_address),
                selectinload(Transaction.risk_assessments).selectinload(RiskAssessment.signals),
            )
            .where(Transaction.risk_score > Decimal(str(min_score)))
        )

        if status_filter:
            query = query.where(Transaction.review_status == status_filter.upper())

        # Count total
        count_q = select(func.count(Transaction.id)).where(Transaction.risk_score > Decimal(str(min_score)))
        if status_filter:
            count_q = count_q.where(Transaction.review_status == status_filter.upper())
        total = await session.scalar(count_q) or 0

        offset = (max(1, page) - 1) * page_size
        query = query.order_by(desc(Transaction.risk_score)).offset(offset).limit(page_size)
        rows = (await session.scalars(query)).all()

        items = []
        for t in rows:
            latest_assess = t.risk_assessments[-1] if t.risk_assessments else None
            signals = [s.signal_name for s in latest_assess.signals] if latest_assess else []
            items.append({
                "id": t.id,
                "external_id": t.external_id,
                "amount": float(t.amount),
                "currency": t.currency,
                "transaction_type": t.transaction_type,
                "source_account": t.account.external_id if t.account else "N/A",
                "customer_name": t.account.customer_name if t.account else "N/A",
                "recipient_account": t.recipient_account.external_id if t.recipient_account else "N/A",
                "risk_score": float(t.risk_score),
                "risk_level": t.risk_level,
                "review_status": t.review_status,
                "timestamp": t.timestamp.isoformat(),
                "device": t.device.external_id if t.device else "N/A",
                "ip_country": t.ip_address.country if t.ip_address else "EG",
                "top_signals": signals[:3],
                "scenario_tag": (t.txn_metadata or {}).get("scenario"),
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "review_threshold": min_score,
            "rule": f"risk_score > {min_score:.2f}%",
        }


@router.post("/assess", status_code=status.HTTP_200_OK)
async def assess_transaction(body: AssessTransactionRequest) -> dict[str, Any]:
    """Trigger on-demand multi-tier risk evaluation for a transaction."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        engine = MockRiskAssessmentEngine(session)
        try:
            assessment = await engine.evaluate_transaction(body.transaction_id)
            await session.commit()
            return {
                "assessment_id": assessment.external_id,
                "risk_score": float(assessment.risk_score),
                "risk_level": assessment.risk_level,
                "requires_human_review": assessment.requires_human_review,
                "summary": assessment.summary,
            }
        except ValueError as exc:
            raise HTTPException(status_code=404, detail={"error": "NOT_FOUND", "message": str(exc)})
