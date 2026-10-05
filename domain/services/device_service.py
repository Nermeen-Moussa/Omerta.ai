"""Device Application Service for Omerta.ai.

Manages device intelligence, hardware fingerprinting, emulator risk flags, and account links.
"""

from typing import Any

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import (
    Account,
    Alert,
    Customer,
    Device,
    Session,
    Transaction,
)


class DeviceService:
    """Service layer for device intelligence and association tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_devices(
        self,
        *,
        search: str | None = None,
        device_type: str | None = None,
        platform: str | None = None,
        risk_level: str | None = None,
        is_emulator: bool | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """Paginated list of pseudonymous devices."""
        query = select(Device).options(selectinload(Device.sessions))

        conditions = []
        if search:
            clean = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Device.external_id.ilike(clean),
                    Device.platform.ilike(clean),
                    Device.user_agent.ilike(clean),
                )
            )
        if device_type:
            conditions.append(Device.device_type == device_type.upper())
        if platform:
            conditions.append(Device.platform == platform)
        if risk_level:
            conditions.append(Device.risk_level == risk_level.upper())
        if is_emulator is not None:
            conditions.append(Device.is_emulator == is_emulator)

        if conditions:
            query = query.where(*conditions)

        count_q = select(func.count(Device.id))
        if conditions:
            count_q = count_q.where(*conditions)
        total = await self.session.scalar(count_q) or 0

        offset = (max(1, page) - 1) * page_size
        query = query.order_by(Device.id).offset(offset).limit(page_size)

        devices = (await self.session.scalars(query)).all()

        items = []
        for d in devices:
            items.append({
                "id": d.id,
                "external_id": d.external_id,
                "device_type": d.device_type,
                "platform": d.platform,
                "user_agent": d.user_agent,
                "is_emulator": d.is_emulator,
                "is_rooted": d.is_rooted,
                "risk_level": d.risk_level,
                "session_count": len(d.sessions),
                "first_seen_at": d.first_seen_at.isoformat(),
                "last_seen_at": d.last_seen_at.isoformat(),
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }

    async def get_device_detail(self, identifier: str) -> dict[str, Any] | None:
        """Fetch detail view of a device and associated accounts & transactions."""
        query = select(Device).options(
            selectinload(Device.sessions).selectinload(Session.account),
            selectinload(Device.sessions).selectinload(Session.customer),
            selectinload(Device.sessions).selectinload(Session.ip_address),
        )

        if identifier.isdigit():
            query = query.where(or_(Device.id == int(identifier), Device.external_id == identifier))
        else:
            query = query.where(Device.external_id == identifier)

        device = await self.session.scalar(query)
        if not device:
            return None

        # Associated unique accounts
        associated_accounts = {}
        for s in device.sessions:
            if s.account and s.account.external_id not in associated_accounts:
                associated_accounts[s.account.external_id] = {
                    "id": s.account.id,
                    "external_id": s.account.external_id,
                    "customer_name": s.account.customer_name,
                    "currency": s.account.currency,
                    "risk_level": s.account.risk_level,
                }

        # Fetch recent transactions on this device
        txns_q = (
            select(Transaction)
            .where(Transaction.device_id == device.id)
            .order_by(desc(Transaction.timestamp))
            .limit(10)
        )
        txns = (await self.session.scalars(txns_q)).all()

        return {
            "device": {
                "id": device.id,
                "external_id": device.external_id,
                "device_type": device.device_type,
                "platform": device.platform,
                "user_agent": device.user_agent,
                "is_emulator": device.is_emulator,
                "is_rooted": device.is_rooted,
                "risk_level": device.risk_level,
                "first_seen_at": device.first_seen_at.isoformat(),
                "last_seen_at": device.last_seen_at.isoformat(),
            },
            "associated_accounts": list(associated_accounts.values()),
            "recent_sessions": [
                {
                    "id": s.id,
                    "external_id": s.external_id,
                    "customer": s.customer.name if s.customer else "N/A",
                    "account": s.account.external_id if s.account else "N/A",
                    "ip_address": s.ip_address.address if s.ip_address else "N/A",
                    "country": s.ip_address.country if s.ip_address else "EG",
                    "is_vpn": s.is_vpn,
                    "started_at": s.started_at.isoformat(),
                }
                for s in device.sessions[:10]
            ],
            "recent_transactions": [
                {
                    "id": t.id,
                    "external_id": t.external_id,
                    "amount": float(t.amount),
                    "currency": t.currency,
                    "type": t.transaction_type,
                    "status": t.status,
                    "risk_score": float(t.risk_score) if t.risk_score is not None else 0.0,
                    "risk_level": t.risk_level,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in txns
            ],
        }
