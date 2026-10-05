"""Dashboard Analytics Router for Omerta.ai."""

from typing import Any
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from domain.services.dashboard_service import DashboardService
from infrastructure.database.session import get_engine

router = APIRouter(prefix="/dashboard", tags=["Dashboard Analytics"])


@router.get("/summary")
async def get_dashboard_summary() -> dict[str, Any]:
    """Retrieve 8 key executive summary cards for the platform dashboard."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        return await DashboardService(session).get_summary_kpis()


@router.get("/charts")
async def get_dashboard_charts() -> dict[str, Any]:
    """Retrieve chart series: risk distribution, status breakdowns, timeseries volume."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        return await DashboardService(session).get_charts_data()


@router.get("/recent-activity")
async def get_recent_activity(limit: int = 8) -> dict[str, Any]:
    """Retrieve recent transaction stream and priority review alerts."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        return await DashboardService(session).get_recent_activity(limit=limit)
