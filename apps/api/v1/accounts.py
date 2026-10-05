"""Bank Accounts Management Router for Omerta.ai."""

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from domain.services.account_service import AccountService
from infrastructure.database.session import get_engine

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("")
async def list_accounts(
    search: str | None = Query(default=None),
    account_type: str | None = Query(default=None),
    currency: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """List and search bank accounts with balances and risk levels."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        return await AccountService(session).list_accounts(
            search=search,
            account_type=account_type,
            currency=currency,
            risk_level=risk_level,
            status=status_filter,
            page=page,
            page_size=page_size,
        )


@router.get("/{account_id}")
async def get_account_detail(account_id: str) -> dict[str, Any]:
    """Retrieve bank account detail with frequent counterparties and transaction stream."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        detail = await AccountService(session).get_account_detail(account_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Account {account_id} not found"},
            )
        return detail
