"""Customers Management Router for Omerta.ai."""

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from domain.services.customer_service import CustomerService
from infrastructure.database.session import get_engine

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("")
async def list_customers(
    search: str | None = Query(default=None),
    customer_type: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    country: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """List and search banking customer profiles."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        return await CustomerService(session).list_customers(
            search=search,
            customer_type=customer_type,
            risk_level=risk_level,
            country=country,
            page=page,
            page_size=page_size,
        )


@router.get("/{customer_id}")
async def get_customer_360(customer_id: str) -> dict[str, Any]:
    """Retrieve 360-degree customer view with linked accounts, sessions, and transactions."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        detail = await CustomerService(session).get_customer_360(customer_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Customer {customer_id} does not exist"},
            )
        return detail
