"""Devices Intelligence Router for Omerta.ai."""

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from domain.services.device_service import DeviceService
from infrastructure.database.session import get_engine

router = APIRouter(prefix="/devices", tags=["Devices"])


@router.get("")
async def list_devices(
    search: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
    platform: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    is_emulator: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict[str, Any]:
    """List pseudonymous devices with emulator/root risk indicators."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        return await DeviceService(session).list_devices(
            search=search,
            device_type=device_type,
            platform=platform,
            risk_level=risk_level,
            is_emulator=is_emulator,
            page=page,
            page_size=page_size,
        )


@router.get("/{device_id}")
async def get_device_detail(device_id: str) -> dict[str, Any]:
    """Retrieve device hardware profile and associated accounts & transactions."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        detail = await DeviceService(session).get_device_detail(device_id)
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "NOT_FOUND", "message": f"Device {device_id} not found"},
            )
        return detail
