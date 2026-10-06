"""Transaction Management Router for Omerta.ai."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.services.banking_transaction_service import BankingTransactionService
from domain.services.mock_risk_engine import MockRiskAssessmentEngine
from infrastructure.database.models import Account, Device, IPAddress, Transaction
from infrastructure.database.session import get_engine

router = APIRouter(prefix="/transactions", tags=["Transactions"])


class CreateTransactionRequest(BaseModel):
    source_account_id: str
    recipient_account_id: str
    amount: float
    currency: str = "EGP"
    transaction_type: str = "TRANSFER"
    device_id: str | None = None
    ip_address: str | None = None
    metadata: dict[str, Any] | None = None


@router.get("")
async def list_transactions(
    search: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    transaction_type: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    min_amount: float | None = Query(default=None),
    max_amount: float | None = Query(default=None),
    sort_by: str = Query(default="timestamp"),
    sort_desc: bool = Query(default=True),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """Search, filter, and paginate transactions with server-side controls."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        return await BankingTransactionService(session).list_transactions(
            search=search,
            currency=currency,
            transaction_type=transaction_type,
            risk_level=risk_level,
            review_status=review_status,
            min_amount=min_amount,
            max_amount=max_amount,
            sort_by=sort_by,
            sort_desc=sort_desc,
            page=page,
            page_size=page_size,
        )


@router.get("/export")
async def export_transactions_csv(
    search: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
) -> Response:
    """Export filtered transactions to CSV spreadsheet."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        csv_content = await BankingTransactionService(session).export_transactions_csv(
            search=search,
            currency=currency,
            risk_level=risk_level,
            review_status=review_status,
        )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=omerta_transactions_export.csv"},
    )


@router.get("/{transaction_id}")
async def get_transaction_detail(transaction_id: str) -> dict[str, Any]:
    """Retrieve full 6-section transaction detail view."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        detail = await BankingTransactionService(session).get_transaction_detail(transaction_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Transaction {transaction_id} does not exist"},
            )
        return detail


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_transaction(body: CreateTransactionRequest) -> dict[str, Any]:
    """Ingest a new transaction and trigger immediate risk assessment."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        # Resolve source account
        s_acc = await session.scalar(
            select(Account).where(
                (Account.external_id == body.source_account_id) | (Account.id == (int(body.source_account_id) if body.source_account_id.isdigit() else -1))
            )
        )
        if not s_acc:
            raise HTTPException(status_code=400, detail={"error": "INVALID_ACCOUNT", "message": "Source account not found"})

        r_acc = await session.scalar(
            select(Account).where(
                (Account.external_id == body.recipient_account_id) | (Account.id == (int(body.recipient_account_id) if body.recipient_account_id.isdigit() else -1))
            )
        )
        if not r_acc:
            raise HTTPException(status_code=400, detail={"error": "INVALID_ACCOUNT", "message": "Recipient account not found"})

        dev = None
        if body.device_id:
            dev = await session.scalar(select(Device).where(Device.external_id == body.device_id))

        ip = None
        if body.ip_address:
            ip = await session.scalar(select(IPAddress).where(IPAddress.address == body.ip_address))

        import uuid
        ext_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        txn = Transaction(
            external_id=ext_id,
            account_id=s_acc.id,
            recipient_account_id=r_acc.id,
            amount=Decimal(str(body.amount)),
            currency=body.currency.upper(),
            transaction_type=body.transaction_type.upper(),
            status="COMPLETED",
            timestamp=datetime.now(),
            device_id=dev.id if dev else None,
            ip_address_id=ip.id if ip else None,
            is_new_device=(dev is None or dev.risk_level == "HIGH"),
            is_new_ip=(ip is None or ip.risk_level == "HIGH"),
            txn_metadata=body.metadata or {},
        )
        session.add(txn)
        await session.flush()

        # Run mock risk evaluation
        engine = MockRiskAssessmentEngine(session)
        assessment = await engine.evaluate_transaction(txn.id)
        await session.commit()

        return {
            "transaction_id": txn.external_id,
            "status": txn.status,
            "risk_score": float(assessment.risk_score),
            "risk_level": assessment.risk_level,
            "requires_human_review": assessment.requires_human_review,
        }
