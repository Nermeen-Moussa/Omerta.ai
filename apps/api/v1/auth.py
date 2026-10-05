"""Authentication & Registration Router for Omerta.ai.

Supports customer self-registration with initial demo balance and Omerta User Number,
multi-role login (CUSTOMER, ADMINISTRATOR, FRAUD_ANALYST, SENIOR_INVESTIGATOR, AUDITOR),
and authenticated user payload resolution.
"""

from decimal import Decimal
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.services.customer_service import CustomerService
from domain.services.email_service import EmailService
from infrastructure.database.models import AuditEvent, Customer, Session as UserSession, User
from infrastructure.database.session import get_engine
from infrastructure.security.jwt_auth import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication & Registration"])


KNOWN_VPN_PROVIDERS = (
    "vpn", "proxy", "hosting", "datacenter", "data center", "cloud",
    "m247", "datacamp", "leaseweb", "digitalocean", "linode", "ovh",
    "hetzner", "proton", "nord", "expressvpn", "surfshark", "mullvad",
    "cloudflare", "fastly", "akamai", "tzulo", "choopa", "vultr",
    "cogent", "packethub", "ipvanish", "cyberghost", "windscribe",
)


def evaluate_vpn_risk(
    *,
    client_ip: str,
    country: str,
    customer_country: str = "EG",
    body_is_vpn: bool = False,
    isp: str | None = None,
    org: str | None = None,
    browser_tz: str | None = None,
    ip_tz: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Evaluate real network signals to detect if a connection is routed through a VPN / Proxy."""
    if body_is_vpn:
        return True, "VPN signal identified from client network telemetry"

    if headers:
        for h in ("x-vpn", "via", "x-proxy"):
            if headers.get(h):
                return True, f"Proxy/VPN routing header present in request ({h})"

    org_combined = f"{isp or ''} {org or ''}".lower()
    for kw in KNOWN_VPN_PROVIDERS:
        if kw in org_combined:
            return True, f"Datacenter / VPN network provider detected: {isp or org}"

    clean_country = (country or "EG").upper()[:2]
    clean_cust_country = (customer_country or "EG").upper()[:2]
    if clean_country and clean_cust_country == "EG" and clean_country != "EG":
        return True, f"International exit node ({clean_country}) observed for Egyptian customer"

    if browser_tz and ip_tz:
        b_tz = browser_tz.lower()
        i_tz = ip_tz.lower()
        if ("cairo" in b_tz or "africa" in b_tz) and ("america" in i_tz or "europe" in i_tz or "tokyo" in i_tz):
            return True, f"Timezone mismatch between system clock ({browser_tz}) and egress IP ({ip_tz})"

    return False, "Direct connection verified"


class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=120)
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8, description="Account Password for login/logout")
    confirm_password: str = Field(..., min_length=8)
    transfer_password: str | None = Field(default=None, description="Transfer Password strictly for authorizing money transfers")
    confirm_transfer_password: str | None = Field(default=None)
    national_id_number: str | None = Field(default=None, description="National Identification Number")
    phone: str = Field(default="", max_length=35)
    country: str = Field(default="EG", min_length=2, max_length=2)
    preferred_currency: str = Field(default="EGP", min_length=3, max_length=3)
    initial_balance: Decimal = Field(default=Decimal("10000.00"), ge=Decimal("100.00"), le=Decimal("1000000.00"))
    device_consent: bool = Field(default=True)
    client_ip: str | None = None
    observed_country: str | None = None
    is_vpn: bool = False
    isp: str | None = None
    org: str | None = None
    browser_timezone: str | None = None
    ip_timezone: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
    force_login: bool = Field(default=False, description="Terminate existing active sessions if set to True")
    is_vpn: bool = Field(default=False, description="VPN detection signal")
    client_ip: str | None = None
    country: str | None = None
    isp: str | None = None
    org: str | None = None
    browser_timezone: str | None = None
    ip_timezone: str | None = None


class TelemetryHeartbeatRequest(BaseModel):
    client_ip: str | None = None
    is_vpn: bool = Field(default=False)
    country: str | None = Field(default="EG")
    isp: str | None = None
    org: str | None = None
    browser_timezone: str | None = None
    ip_timezone: str | None = None
    user_agent: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=120)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]
    customer: dict[str, Any] | None = None
    session: dict[str, Any] | None = None


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request) -> AuthResponse:
    """Register a new customer with distinct account and transfer passwords, National ID, and opening balance."""
    # 1. Validate Account Password confirmation
    if body.password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "PASSWORD_MISMATCH", "message": "Account password and confirmation do not match."},
        )

    # 2. Validate Transfer Password confirmation & Separation if provided
    effective_transfer_password = body.transfer_password
    if effective_transfer_password is not None:
        if body.confirm_transfer_password and effective_transfer_password != body.confirm_transfer_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "TRANSFER_PASSWORD_MISMATCH", "message": "Transfer password and confirmation do not match."},
            )

        # 3. Strictly Enforce Password Separation (Account Password != Transfer Password)
        if body.password == effective_transfer_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "TRANSFER_PASSWORD_CANNOT_MATCH_ACCOUNT_PASSWORD",
                    "message": "For your financial security, your Transfer Password must be completely different from your Account Login Password.",
                },
            )
    else:
        # Generate random distinct transfer password for legacy payloads
        effective_transfer_password = f"TxPass_{secrets.token_hex(4)}!"

    effective_nat_id = body.national_id_number or f"2900101{secrets.randbelow(8999999) + 1000000}"

    user_agent = request.headers.get("user-agent", "Mozilla/5.0 (X11; Linux x86_64)")
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    header_ip = forwarded.split(",")[0].strip() if forwarded else None
    
    if header_ip and header_ip not in ("127.0.0.1", "::1", "localhost"):
        client_ip = header_ip
    elif body.client_ip and body.client_ip not in ("127.0.0.1", "::1", "localhost"):
        client_ip = body.client_ip
    elif request.client and request.client.host not in ("127.0.0.1", "::1", "localhost"):
        client_ip = request.client.host
    elif body.client_ip:
        client_ip = body.client_ip
    else:
        client_ip = "197.58.84.25"

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        try:
            res = await cust_service.register_customer(
                full_name=body.full_name,
                email=body.email,
                username=body.username,
                password=body.password,
                transfer_password=effective_transfer_password,
                national_id_number=effective_nat_id,
                phone=body.phone,
                country=body.country,
                preferred_currency=body.preferred_currency,
                initial_balance=body.initial_balance,
                device_consent=body.device_consent,
                user_agent=user_agent,
                ip_address=client_ip,
            )
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "REGISTRATION_FAILED", "message": str(err)},
            )

        token = create_access_token(
            user_id=res["user"]["id"],
            username=res["user"]["username"],
            role="CUSTOMER",
            full_name=res["user"]["full_name"],
            session_id=res.get("session_id"),
        )

        return AuthResponse(
            access_token=token,
            user=res["user"],
            customer=res["customer"],
            session={"session_id": res.get("session_id")},
        )


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest, request: Request) -> AuthResponse:
    """Authenticate with username or email, record device/IP telemetry, enforce single active session, and issue JWT."""
    user_agent = request.headers.get("user-agent", "Mozilla/5.0 (X11; Linux x86_64)")
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    header_ip = forwarded.split(",")[0].strip() if forwarded else None

    # Resolve effective IP address
    if header_ip and header_ip not in ("127.0.0.1", "::1", "localhost"):
        effective_ip = header_ip
    elif body.client_ip and body.client_ip not in ("127.0.0.1", "::1", "localhost"):
        effective_ip = body.client_ip
    elif request.client and request.client.host not in ("127.0.0.1", "::1", "localhost"):
        effective_ip = request.client.host
    elif body.client_ip:
        effective_ip = body.client_ip
    else:
        effective_ip = "197.58.84.25"

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        user = await session.scalar(
            select(User)
            .options(selectinload(User.customer).selectinload(Customer.accounts))
            .where((User.username == body.username.strip().lower()) | (User.email == body.username.strip().lower()))
        )
        if not user or not verify_password(body.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "INVALID_CREDENTIALS", "message": "Invalid username or password."},
            )

        # Country resolution
        country_header = request.headers.get("cf-ipcountry") or request.headers.get("x-country-code")
        declared_country = user.customer.declared_country if (user and user.customer) else "EG"
        observed_country = country_header or body.country or declared_country or "EG"

        # Evaluate VPN / Proxy Telemetry
        is_vpn_detected, vpn_reason = evaluate_vpn_risk(
            client_ip=effective_ip,
            country=observed_country,
            customer_country=declared_country,
            body_is_vpn=body.is_vpn,
            isp=body.isp,
            org=body.org,
            browser_tz=body.browser_timezone,
            ip_tz=body.ip_timezone,
            headers=dict(request.headers),
        )

        is_staff_or_admin = user.role in [
            "ADMINISTRATOR",
            "SUB_ADMINISTRATOR",
            "FRAUD_ANALYST",
            "INVESTIGATOR",
            "SENIOR_INVESTIGATOR",
            "AUDITOR",
            "COMPLIANCE_AUDITOR",
        ]

        if is_staff_or_admin:
            if is_vpn_detected:
                # Instantly lock admin user account and invalidate any active sessions
                user.is_active = False
                active_sessions = (
                    await session.scalars(
                        select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active == True)
                    )
                ).all()
                for sess in active_sessions:
                    sess.is_active = False

                session.add(
                    AuditEvent(
                        event_id=f"EVT-ADM-VPNLOCK-{user.id}",
                        event_type="ADMIN_VPN_SECURITY_LOCKOUT",
                        actor_type=user.role,
                        actor_id=user.external_id,
                        source="AdminSecurityGateway",
                        metadata_={
                            "user_id": user.external_id,
                            "role": user.role,
                            "client_ip": effective_ip,
                            "vpn_reason": vpn_reason,
                            "status": "LOCKED",
                        },
                    )
                )
                await session.commit()

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "ADMIN_VPN_SECURITY_LOCK",
                        "message": f"Admin Security Policy Violation: Administrative access via VPN, proxy, or anonymizer tunnels ({vpn_reason}) is strictly prohibited. Your administrative account has been locked. You must connect from a verified standard ISP network without VPN to unlock access.",
                        "vpn_reason": vpn_reason,
                    },
                )
            else:
                # If admin was locked due to VPN, automatically unlock on clean non-VPN connection
                if not user.is_active:
                    user.is_active = True
                    session.add(
                        AuditEvent(
                            event_id=f"EVT-ADM-UNLOCK-{user.id}",
                            event_type="ADMIN_ACCOUNT_UNLOCKED_CLEAN_IP",
                            actor_type=user.role,
                            actor_id=user.external_id,
                            source="AdminSecurityGateway",
                            metadata_={
                                "user_id": user.external_id,
                                "role": user.role,
                                "client_ip": effective_ip,
                                "status": "UNLOCKED",
                            },
                        )
                    )
                    await session.commit()

        if not user.is_active or (user.customer and user.customer.status in ["SUSPENDED", "LOCKED"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "ACCOUNT_INACTIVE_LOCKED",
                    "message": "Account Inactive: Your account has been suspended due to security policy flags (3 failed password attempts or security lockout). An Administrator must review and reactivate your account in the Admin Control Center to restore access.",
                },
            )

        # Record login telemetry and enforce single active session
        cust_service = CustomerService(session)
        ok, err_msg, session_meta = await cust_service.record_login_session(
            user=user,
            client_ip=effective_ip,
            user_agent=user_agent,
            country=observed_country,
            is_vpn=is_vpn_detected,
            force_login=body.force_login,
        )

        if not ok:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "CONCURRENT_SESSION_DENIED", "message": err_msg},
            )

        session_id = session_meta.get("session_id") if session_meta else None
        token = create_access_token(
            user_id=user.external_id,
            username=user.username,
            role=user.role,
            full_name=user.full_name,
            session_id=session_id,
        )

        cust_payload = None
        if user.customer:
            cust_payload = {
                "id": user.customer.external_id,
                "name": user.customer.name,
                "omerta_user_number": user.customer.omerta_user_number,
                "declared_country": user.customer.declared_country,
                "preferred_currency": user.customer.preferred_currency,
                "device_consent": user.customer.device_consent,
            }

        return AuthResponse(
            access_token=token,
            user={
                "id": user.external_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
            },
            customer=cust_payload,
            session=session_meta,
        )


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, request: Request) -> dict[str, Any]:
    """Initiate a secure password reset request, issuing a signed reset link token."""
    email_clean = body.email.strip().lower()

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        user = await session.scalar(
            select(User).where((User.email == email_clean) | (User.username == email_clean))
        )

        if not user:
            # Generic response to prevent user enumeration
            return {
                "success": True,
                "message": "If an account matches this email or username, a password reset link has been dispatched.",
                "simulated_email": None,
            }

        # Generate signed reset token
        reset_token = create_password_reset_token(user_id=user.external_id, email=user.email, expires_minutes=15)
        reset_url = f"http://localhost:5173/reset-password?token={reset_token}"
        client_ip = request.client.host if request.client else "127.0.0.1"

        # Transmit real email from abdomostafa13571234@gmail.com
        delivery_result = await EmailService.send_password_reset_email(
            to_email=user.email,
            recipient_name=user.full_name or user.username,
            reset_url=reset_url,
            reset_token=reset_token,
            client_ip=client_ip,
        )

        # Audit log the reset request
        audit = AuditEvent(
            event_id=f"EVT-PWDRST-REQ-{user.id}",
            event_type="PASSWORD_RESET_REQUESTED",
            actor_type=user.role,
            actor_id=user.external_id,
            source="AuthenticationSecurity",
            metadata_={
                "user_id": user.external_id,
                "email": user.email,
                "sender_email": "abdomostafa13571234@gmail.com",
                "client_ip": client_ip,
                "delivery_success": delivery_result.success,
                "delivery_message": delivery_result.message,
                "delivery_details": delivery_result.details,
            },
        )
        session.add(audit)
        await session.commit()

        return {
            "success": True,
            "message": f"A secure password reset email has been dispatched from abdomostafa13571234@gmail.com to {user.email}.",
            "sender_email": "abdomostafa13571234@gmail.com",
            "recipient_email": user.email,
            "delivery_result": delivery_result.to_dict(),
            "simulated_email": {
                "from": "abdomostafa13571234@gmail.com",
                "to": user.email,
                "recipient_name": user.full_name,
                "subject": "🔐 Omerta.ai Security — Reset Your Account Password",
                "reset_url": reset_url,
                "token": reset_token,
                "expires_in": "15 minutes",
            },
        }


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, request: Request) -> dict[str, Any]:
    """Verify reset token and update account password."""
    if body.new_password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "PASSWORD_MISMATCH", "message": "New password and confirmation do not match."},
        )

    payload = decode_password_reset_token(body.token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_OR_EXPIRED_TOKEN", "message": "The password reset token is invalid or has expired. Please request a new link."},
        )

    user_external_id = payload.get("sub")
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        user = await session.scalar(
            select(User).where(User.external_id == user_external_id)
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "USER_NOT_FOUND", "message": "User associated with this reset token was not found."},
            )

        # Update password hash
        user.hashed_password = hash_password(body.new_password)

        # Terminate all active sessions for security
        active_sessions = (
            await session.scalars(
                select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active == True)
            )
        ).all()
        for sess in active_sessions:
            sess.is_active = False

        # Audit log the reset completion
        audit = AuditEvent(
            event_id=f"EVT-PWDRST-CMP-{user.id}",
            event_type="PASSWORD_RESET_COMPLETED",
            actor_type=user.role,
            actor_id=user.external_id,
            source="AuthenticationSecurity",
            metadata_={
                "user_id": user.external_id,
                "client_ip": request.client.host if request.client else "127.0.0.1",
            },
        )
        session.add(audit)
        await session.commit()

        return {
            "success": True,
            "message": "Password updated successfully! All previous sessions have been invalidated. Please log in with your new password.",
        }


@router.get("/me")
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Retrieve the currently authenticated user profile, customer context, and active permissions."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        user = await session.scalar(
            select(User)
            .options(selectinload(User.customer))
            .where(User.external_id == current_user.get("sub"))
        )

        customer_data = None
        if user and user.customer:
            customer_data = {
                "id": user.customer.external_id,
                "omerta_user_number": user.customer.omerta_user_number,
                "name": user.customer.name,
                "declared_country": user.customer.declared_country,
                "preferred_currency": user.customer.preferred_currency,
                "device_consent": user.customer.device_consent,
                "status": user.customer.status,
                "transfer_status": getattr(user.customer, "transfer_status", "ACTIVE"),
                "identity_status": getattr(user.customer, "identity_status", "NOT_VERIFIED"),
            }

        role = current_user.get("role", "CUSTOMER")
        is_admin = role in ["ADMINISTRATOR", "FRAUD_ANALYST", "SENIOR_INVESTIGATOR", "AUDITOR"]

        return {
            "user": {
                "id": current_user.get("sub"),
                "username": current_user.get("username"),
                "full_name": current_user.get("full_name"),
                "role": role,
                "is_active": user.is_active if user else True,
            },
            "customer": customer_data,
            "permissions": {
                "is_admin": is_admin,
                "can_transfer": role == "CUSTOMER",
                "can_review_cases": role in ["ADMINISTRATOR", "SENIOR_INVESTIGATOR", "FRAUD_ANALYST"],
                "can_record_dispositions": role in ["ADMINISTRATOR", "SENIOR_INVESTIGATOR", "FRAUD_ANALYST"],
                "can_manage_users": role == "ADMINISTRATOR",
                "can_tune_thresholds": role == "ADMINISTRATOR",
            },
        }


@router.post("/telemetry/heartbeat")
async def process_telemetry_heartbeat(
    body: TelemetryHeartbeatRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """30-second recurring network telemetry probe and active session synchronizer.
    
    Dynamically checks live client IP, VPN/proxy tunnels, ISP/datacenter ASN,
    updates active database session state, and executes instant admin lockouts if VPN is detected.
    """
    client_ip = body.client_ip or request.client.host if request.client else "127.0.0.1"
    user_agent = body.user_agent or request.headers.get("user-agent", "Mozilla/5.0")
    country = (body.country or "EG").upper()[:2]

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        result = await cust_service.update_telemetry_heartbeat(
            user_identifier=current_user.get("sub"),
            client_ip=client_ip,
            country=country,
            is_vpn=body.is_vpn,
            user_agent=user_agent,
            isp=body.isp,
            org=body.org,
            browser_timezone=body.browser_timezone,
            ip_timezone=body.ip_timezone,
        )
        return result

