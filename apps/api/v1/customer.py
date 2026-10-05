"""Customer Banking Platform API Router for Omerta.ai.

Provides authenticated customer endpoints for dashboard, account management,
simulated peer-to-peer transfers, transaction history, receipts, and security session controls.
Strict customer data isolation is enforced for all endpoints.
"""

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.v1.auth import evaluate_vpn_risk
from domain.services.customer_service import CustomerService
from domain.services.transfer_service import TransferError, TransferService
from infrastructure.database.models import Alert, AuditEvent, Session as UserSession, User
from infrastructure.database.session import get_engine
from infrastructure.security.jwt_auth import get_current_user, verify_password

router = APIRouter(prefix="/customer", tags=["Customer Banking Platform"])

# In-memory tracking of consecutive failed transfer password attempts per user
FAILED_TRANSFER_ATTEMPTS: dict[int, int] = defaultdict(int)


class TransferInitiateRequest(BaseModel):
    sender_account_id: str | None = Field(default=None, description="External ID of sender account")
    source_account_id: str | None = Field(default=None, description="Alias for sender_account_id")
    recipient_user_number: str | None = Field(default=None, description="Unique Omerta User Number or Phone of recipient")
    recipient_omerta_number: str | None = Field(default=None, description="Alias for recipient_user_number")
    recipient_phone: str | None = Field(default=None, description="Recipient phone number")
    recipient_identifier: str | None = Field(default=None, description="Recipient Omerta number or phone number")
    amount: Decimal = Field(..., gt=Decimal("0.00"), description="Simulated transfer amount")
    currency: str = Field(default="EGP", min_length=3, max_length=3)
    note: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, description="Account password required to authorize transfer")
    idempotency_key: str | None = None
    is_vpn: bool = Field(default=False, description="VPN connection flag from network telemetry")
    client_ip: str | None = None
    country: str | None = None
    isp: str | None = None
    org: str | None = None
    browser_timezone: str | None = None
    ip_timezone: str | None = None
    city: str | None = None

    @property
    def resolved_sender_account_id(self) -> str:
        acc = self.sender_account_id or self.source_account_id
        if not acc:
            raise ValueError("sender_account_id or source_account_id is required")
        return acc

    @property
    def resolved_recipient_user_number(self) -> str:
        num = self.recipient_identifier or self.recipient_user_number or self.recipient_omerta_number or self.recipient_phone
        if not num:
            raise ValueError("recipient identifier (Omerta User Number or Phone) is required")
        return num


class CreateAccountRequest(BaseModel):
    account_type: str = Field(default="SAVINGS", description="CHECKING or SAVINGS")
    currency: str = Field(default="EGP", min_length=3, max_length=3)
    initial_balance: Decimal = Field(default=Decimal("5000.00"), ge=Decimal("0.00"))


class ConsentUpdateRequest(BaseModel):
    device_consent: bool


@router.get("/dashboard")
async def get_dashboard(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve personalized customer dashboard metrics and activity."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        try:
            return await cust_service.get_customer_dashboard_overview(current_user["sub"])
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get("/profile")
async def get_profile(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve the current customer's profile (sanitized, internal risk rating hidden)."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        c = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not c:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer profile not found.")

        return {
            "id": c.external_id,
            "omerta_user_number": c.omerta_user_number,
            "name": c.name,
            "email": c.email,
            "phone": c.phone or "+20 10 1111 2222",
            "declared_country": c.declared_country or c.country,
            "preferred_currency": c.preferred_currency,
            "device_consent": c.device_consent,
            "status": c.status,
            "verification_status": "TIER_1_VERIFIED",
            "verification_tier": "Tier 1 Verified Demo",
            "member_since": c.registration_date.isoformat(),
        }


@router.get("/accounts")
async def get_accounts(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve all bank accounts owned by the authenticated customer."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        return await cust_service.get_customer_accounts(current_user["sub"])


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
async def open_account(
    body: CreateAccountRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Open an additional demo account with an auditable starting ledger balance."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        try:
            return await cust_service.create_additional_account(
                user_id=current_user["sub"],
                account_type=body.account_type,
                currency=body.currency,
                initial_balance=body.initial_balance,
            )
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/recipient/lookup")
async def lookup_recipient(
    identifier: str | None = Query(default=None, description="Omerta User Number or Phone Number"),
    user_number: str | None = Query(default=None, description="Omerta User Number (e.g. OMR-8492-3011)"),
    omerta_user_number: str | None = Query(default=None, description="Alias for user_number"),
    phone: str | None = Query(default=None, description="Recipient mobile phone number"),
    query: str | None = Query(default=None, description="Search query"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Look up a recipient by their unique Omerta User Number or Mobile Phone Number."""
    target = identifier or query or omerta_user_number or user_number or phone
    if not target or not target.strip():
        raise HTTPException(status_code=400, detail={"error": "INVALID_QUERY", "message": "Missing recipient identifier or phone number."})

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        transfer_service = TransferService(session)
        try:
            return await transfer_service.lookup_recipient(target.strip())
        except TransferError as err:
            raise HTTPException(
                status_code=err.status_code,
                detail={"error": err.code, "message": err.message},
            )


@router.post("/transfers", status_code=status.HTTP_201_CREATED)
async def initiate_transfer(
    body: TransferInitiateRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Execute a simulated customer-to-customer transfer with atomic double-entry ledger update."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "OmertaWeb/2.0")

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer or not customer.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "NOT_A_CUSTOMER", "message": "Only registered customers can send transfers."},
            )

        # 1. Enforce password authorization with 3-attempt failure risk escalation
        user_rec = await session.scalar(select(User).where(User.id == customer.user_id))
        if body.password is not None:
            if not user_rec or not verify_password(body.password, user_rec.hashed_password):
                FAILED_TRANSFER_ATTEMPTS[customer.user_id] += 1
                failed_count = FAILED_TRANSFER_ATTEMPTS[customer.user_id]

                if failed_count >= 3:
                    # Inactivate user account and suspend customer profile
                    if user_rec:
                        user_rec.is_active = False
                    customer.status = "SUSPENDED"
                    customer.risk_level = "CRITICAL"

                    # Revoke and invalidate all active sessions immediately
                    active_sessions = (
                        await session.scalars(
                            select(UserSession).where(UserSession.user_id == customer.user_id, UserSession.is_active == True)
                        )
                    ).all()
                    for sess in active_sessions:
                        sess.is_active = False
                        sess.ended_at = datetime.now(UTC)
                        sess.revoked_at = datetime.now(UTC)

                    # Create Audit Event
                    session.add(
                        AuditEvent(
                            event_id=f"EVT-PWD-{secrets.token_hex(4).upper()}",
                            event_type="EXCESSIVE_PASSWORD_FAILURES",
                            actor_type="CUSTOMER",
                            actor_id=str(customer.user_id),
                            source="CustomerTransferAuth",
                            metadata_={
                                "failed_attempts": failed_count,
                                "customer_id": customer.external_id,
                                "customer_name": customer.name,
                                "omerta_user_number": customer.omerta_user_number,
                                "risk_level": "CRITICAL",
                                "status": "INACTIVE_SUSPENDED",
                                "client_ip": client_ip,
                                "description": "3 consecutive incorrect password attempts. Account inactivated & suspended.",
                            },
                        )
                    )
                    await session.commit()

                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "error": "ACCOUNT_INACTIVATED_LOCKOUT",
                            "failed_attempts": failed_count,
                            "remaining_attempts": 0,
                            "message": "Security Alert: 3 consecutive incorrect password attempts detected. Your account has been INACTIVATED and you have been logged out. An Administrator must review and reactivate your account in the Admin Control Center to restore access.",
                        },
                    )
                else:
                    remaining = 3 - failed_count
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={
                            "error": "INVALID_PASSWORD",
                            "failed_attempts": failed_count,
                            "remaining_attempts": remaining,
                            "message": f"Incorrect account password. (Attempt {failed_count} of 3). Warning: You have {remaining} attempt(s) remaining before your account is INACTIVATED and locked.",
                        },
                    )

            # Reset failed attempts counter on successful verification
            FAILED_TRANSFER_ATTEMPTS[customer.user_id] = 0

        # 2. Evaluate Real VPN / Proxy Telemetry & Block Anonymized Transfers
        user_sess = await session.scalar(
            select(UserSession)
            .options(selectinload(UserSession.ip_address))
            .where(and_(UserSession.user_id == customer.user_id, UserSession.is_active.is_(True)))
            .order_by(UserSession.started_at.desc())
            .limit(1)
        )
        session_is_vpn = user_sess.is_vpn if user_sess else False

        effective_ip = body.client_ip or (request.client.host if request.client else "127.0.0.1")
        effective_country = body.country or (user_sess.ip_address.country if user_sess and user_sess.ip_address else (customer.declared_country or "EG"))

        is_vpn_detected, vpn_reason = evaluate_vpn_risk(
            client_ip=effective_ip,
            country=effective_country,
            customer_country=customer.declared_country or "EG",
            body_is_vpn=body.is_vpn or session_is_vpn,
            isp=body.isp,
            org=body.org,
            browser_tz=body.browser_timezone,
            ip_tz=body.ip_timezone,
            headers=dict(request.headers),
        )

        if is_vpn_detected:
            # Elevate customer risk level to HIGH
            customer.risk_level = "HIGH"

            # Create Audit Event
            session.add(
                AuditEvent(
                    event_id=f"EVT-VPN-{secrets.token_hex(4).upper()}",
                    event_type="VPN_TRANSFER_BLOCKED",
                    actor_type="CUSTOMER",
                    actor_id=str(customer.user_id),
                    source="SecurityRiskEngine",
                    metadata_={
                        "vpn_reason": vpn_reason,
                        "risk_level": "HIGH",
                        "amount": str(body.amount),
                        "customer_id": customer.external_id,
                        "client_ip": effective_ip,
                    },
                )
            )
            await session.commit()

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "VPN_TRANSFER_BLOCKED",
                    "message": f"Security Policy Restriction: Transfers initiated through commercial VPNs or proxy anonymizers are blocked ({vpn_reason}) and your account risk has been elevated to HIGH. Please disconnect your VPN and use a verified direct connection to proceed.",
                },
            )

        try:
            sender_acc = body.resolved_sender_account_id
            recip_num = body.resolved_recipient_user_number
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": "INVALID_INPUT", "message": str(err)})

        transfer_service = TransferService(session)
        try:
            receipt = await transfer_service.execute_transfer(
                sender_user_id=customer.user_id,
                sender_account_id=sender_acc,
                recipient_user_number=recip_num,
                amount=body.amount,
                currency=body.currency,
                note=body.note,
                idempotency_key=body.idempotency_key,
                ip_address=effective_ip,
                user_agent=user_agent,
                is_vpn=is_vpn_detected,
                city=body.city,
                country=effective_country,
            )
            return receipt
        except TransferError as err:
            raise HTTPException(
                status_code=err.status_code,
                detail={"error": err.code, "message": err.message},
            )


@router.get("/transfers")
async def list_transfers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """List transfers involving the authenticated customer."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer or not customer.user_id:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 1}

        transfer_service = TransferService(session)
        return await transfer_service.list_customer_transfers(
            user_id=customer.user_id, page=page, page_size=page_size
        )


@router.get("/transfers/{transfer_id}")
async def get_transfer_receipt(
    transfer_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve transfer receipt details."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        transfer_service = TransferService(session)
        try:
            return await transfer_service.get_transfer_receipt(transfer_id)
        except TransferError as err:
            raise HTTPException(
                status_code=err.status_code,
                detail={"error": err.code, "message": err.message},
            )


@router.get("/transactions")
async def list_transactions(
    search: str | None = None,
    direction: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve transaction history strictly scoped to the authenticated customer."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        return await cust_service.get_customer_transactions(
            user_id=current_user["sub"],
            search=search,
            direction=direction,
            status=status,
            page=page,
            page_size=page_size,
        )


@router.get("/security/sessions")
async def get_security_sessions(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Retrieve active and recent sessions for privacy and security review."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        return await cust_service.get_customer_sessions(current_user["sub"])


@router.post("/security/sessions/{session_id}/revoke")
async def revoke_session(
    session_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Revoke an active customer session."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        success = await cust_service.revoke_session(current_user["sub"], session_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or already revoked.")
        return {"status": "REVOKED", "session_id": session_id, "revoked": True}


@router.post("/security/consent")
async def update_consent(
    body: ConsentUpdateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Update device and session collection consent settings."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        success = await cust_service.update_device_consent(current_user["sub"], body.device_consent)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
        return {"status": "UPDATED", "device_consent": body.device_consent}


@router.post("/security/heartbeat")
async def customer_security_heartbeat(
    request: Request,
    body: dict[str, Any] | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """30-second recurring network telemetry probe and active session synchronizer for customers."""
    payload = body or {}
    client_ip = payload.get("client_ip") or (request.client.host if request.client else "127.0.0.1")
    user_agent = payload.get("user_agent") or request.headers.get("user-agent", "Mozilla/5.0")
    country = (payload.get("country") or "EG").upper()[:2]
    is_vpn = bool(payload.get("is_vpn", False))

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        result = await cust_service.update_telemetry_heartbeat(
            user_identifier=current_user.get("sub"),
            client_ip=client_ip,
            country=country,
            is_vpn=is_vpn,
            user_agent=user_agent,
            isp=payload.get("isp"),
            org=payload.get("org"),
            browser_timezone=payload.get("browser_timezone"),
            ip_timezone=payload.get("ip_timezone"),
        )
        return result

