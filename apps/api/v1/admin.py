"""Admin Control Center API Router for Omerta.ai.

Provides administrative controls, platform oversight, customer status management,
auditable ledger demo balance adjustments, review queue decisions, and configuration inspection.
Protected by role-based authorization (ADMINISTRATOR, FRAUD_ANALYST, SENIOR_INVESTIGATOR).
"""

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.services.account_service import AccountService
from domain.services.customer_service import CustomerService
from domain.services.email_service import EmailService
from infrastructure.database.models import (
    Account,
    Alert,
    AuditEvent,
    Customer,
    IdentityVerification,
    InvestigationCase,
    RiskAssessment,
    SupportTicket,
    Transaction,
    User,
)
from infrastructure.database.session import get_engine
from infrastructure.security.jwt_auth import get_current_user, require_role

router = APIRouter(prefix="/admin", tags=["Admin Control Center"])

ADMIN_ROLES = ["ADMINISTRATOR", "FRAUD_ANALYST", "SENIOR_INVESTIGATOR", "AUDITOR"]


class UserStatusUpdateRequest(BaseModel):
    is_active: bool
    reason: str = Field(..., min_length=3, description="Mandatory audit reason for status change")


class BalanceAdjustmentRequest(BaseModel):
    adjustment_amount: Decimal = Field(..., description="Positive to credit, negative to debit")
    reason: str = Field(..., min_length=5, description="Mandatory compliance reason for demo adjustment")


class TransactionReviewDecision(BaseModel):
    disposition: str = Field(..., description="APPROVE | FLAG_INVESTIGATION | DISMISS")
    rationale: str = Field(..., min_length=5, description="Detailed review rationale")


@router.get("/dashboard")
async def get_admin_dashboard(
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> dict[str, Any]:
    """Provide high-level operational overview for the admin control center."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        # Total and active customers
        total_cust = await session.scalar(select(func.count(Customer.id))) or 0
        active_cust = await session.scalar(select(func.count(Customer.id)).where(Customer.status == "ACTIVE")) or 0

        # Accounts
        total_accounts = await session.scalar(select(func.count(Account.id))) or 0

        # Transactions
        total_txns = await session.scalar(select(func.count(Transaction.id))) or 0
        total_volume = await session.scalar(select(func.sum(Transaction.amount))) or Decimal("0.00")

        # Review Queue (strictly risk_score > 40.00 or review_status == 'REQUIRES_REVIEW')
        review_count = await session.scalar(
            select(func.count(Transaction.id)).where(
                (Transaction.risk_score > Decimal("40.00")) | (Transaction.review_status == "REQUIRES_REVIEW")
            )
        ) or 0

        # Open investigations
        open_cases = await session.scalar(
            select(func.count(InvestigationCase.id)).where(InvestigationCase.status != "RESOLVED")
        ) or 0

        # Risk distribution
        low_risk = await session.scalar(select(func.count(Transaction.id)).where(Transaction.risk_score <= Decimal("20.00"))) or 0
        mod_risk = await session.scalar(select(func.count(Transaction.id)).where(Transaction.risk_score > Decimal("20.00"), Transaction.risk_score <= Decimal("40.00"))) or 0
        high_risk = await session.scalar(select(func.count(Transaction.id)).where(Transaction.risk_score > Decimal("40.00"), Transaction.risk_score <= Decimal("70.00"))) or 0
        crit_risk = await session.scalar(select(func.count(Transaction.id)).where(Transaction.risk_score > Decimal("70.00"))) or 0

        return {
            "summary": {
                "total_customers": total_cust,
                "active_customers": active_cust,
                "total_accounts": total_accounts,
                "total_transactions": total_txns,
                "total_demo_volume": float(total_volume),
                "transactions_requiring_review": review_count,
                "open_investigations": open_cases,
                "human_review_threshold": 40.0,
            },
            "risk_distribution": {
                "low": low_risk,
                "moderate": mod_risk,
                "high": high_risk,
                "critical": crit_risk,
            },
            "is_synthetic": True,
            "demo_notice": "Omerta.ai Admin Intelligence Platform — Simulated Demo Environment",
        }


@router.get("/users")
async def list_admin_users(
    search: str | None = None,
    customer_type: str | None = None,
    risk_level: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> dict[str, Any]:
    """Search and manage registered customers and system users."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        return await cust_service.list_customers(
            search=search,
            customer_type=customer_type,
            risk_level=risk_level,
            page=page,
            page_size=page_size,
        )


@router.get("/users/{identifier}")
async def get_admin_user_detail(
    identifier: str,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> dict[str, Any]:
    """Retrieve complete 360-degree customer details for investigation."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        res = await cust_service.get_customer_360(identifier)
        if not res:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
        return res


@router.post("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    body: UserStatusUpdateRequest,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR"])),
) -> dict[str, Any]:
    """Suspend or reactivate a demo customer/user."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        user = await session.scalar(
            select(User).options(selectinload(User.customer)).where(User.external_id == user_id)
        )
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        old_status = user.is_active
        user.is_active = body.is_active
        if user.customer:
            user.customer.status = "ACTIVE" if body.is_active else "SUSPENDED"

        audit_event = AuditEvent(
            event_id=f"EVT-ADM-{user.id}",
            event_type="USER_STATUS_MODIFIED",
            actor_type="ADMIN",
            actor_id=current_user.get("sub"),
            source="AdminService",
            metadata_={
                "user_id": user.external_id,
                "old_status": old_status,
                "new_status": body.is_active,
                "reason": body.reason,
            },
        )
        session.add(audit_event)
        await session.commit()

        return {
            "user_id": user.external_id,
            "is_active": user.is_active,
            "customer_status": user.customer.status if user.customer else None,
            "reason": body.reason,
        }


@router.get("/accounts")
async def list_admin_accounts(
    search: str | None = None,
    account_type: str | None = None,
    currency: str | None = None,
    risk_level: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> dict[str, Any]:
    """List and inspect bank accounts across the platform."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        acc_service = AccountService(session)
        return await acc_service.list_accounts(
            search=search,
            account_type=account_type,
            currency=currency,
            risk_level=risk_level,
            status=status,
            page=page,
            page_size=page_size,
        )


@router.post("/accounts/{account_id}/adjustment")
async def apply_account_adjustment(
    account_id: str,
    body: BalanceAdjustmentRequest,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR"])),
) -> dict[str, Any]:
    """Apply an authorized demo balance adjustment through an immutable double-entry ledger record."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        acc_service = AccountService(session)
        try:
            return await acc_service.apply_admin_balance_adjustment(
                account_identifier=account_id,
                adjustment_amount=body.adjustment_amount,
                reason=body.reason,
                admin_actor_id=current_user.get("sub", "ADMIN"),
            )
        except ValueError as err:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/transactions/{transaction_id}/review")
async def record_transaction_review(
    transaction_id: str,
    body: TransactionReviewDecision,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR", "SENIOR_INVESTIGATOR", "FRAUD_ANALYST"])),
) -> dict[str, Any]:
    """Record an analyst review decision for a flagged transaction."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        txn = await session.scalar(
            select(Transaction).where(Transaction.external_id == transaction_id)
        )
        if not txn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

        old_status = txn.review_status
        txn.review_status = "COMPLETED" if body.disposition == "APPROVE" else "IN_REVIEW"

        audit_event = AuditEvent(
            event_id=f"EVT-REV-{txn.id}",
            event_type="TRANSACTION_REVIEW_DECISION",
            actor_type="ANALYST",
            actor_id=current_user.get("sub"),
            source="AdminService",
            transaction_id=txn.external_id,
            metadata_={
                "transaction_id": txn.external_id,
                "disposition": body.disposition,
                "rationale": body.rationale,
                "old_review_status": old_status,
                "new_review_status": txn.review_status,
            },
        )
        session.add(audit_event)
        await session.commit()

        return {
            "transaction_id": txn.external_id,
            "disposition": body.disposition,
            "rationale": body.rationale,
            "review_status": txn.review_status,
        }


class CreateStaffRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=120)
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    role: str = Field(default="SUB_ADMINISTRATOR")
    privileges: list[str] = Field(default_factory=list)


ROLE_DEFAULT_PRIVILEGES: dict[str, list[str]] = {
    "ADMINISTRATOR": ["manage_users", "review_flagged_transactions", "adjust_balances", "view_audit_logs", "export_reports", "manage_staff"],
    "SUB_ADMINISTRATOR": ["manage_users", "review_flagged_transactions", "view_audit_logs", "export_reports"],
    "FRAUD_ANALYST": ["review_flagged_transactions", "view_audit_logs", "export_reports"],
    "SENIOR_INVESTIGATOR": ["manage_users", "review_flagged_transactions", "view_audit_logs", "export_reports"],
    "AUDITOR": ["view_audit_logs", "export_reports"],
}


@router.get("/staff")
async def list_staff_users(
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> list[dict[str, Any]]:
    """List all administrative, sub-admin, and compliance staff users with assigned privileges."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        stmt = (
            select(User)
            .where(User.role != "CUSTOMER")
            .order_by(User.id.asc())
        )
        users = (await session.scalars(stmt)).all()

        staff_list = []
        for u in users:
            privileges = ROLE_DEFAULT_PRIVILEGES.get(u.role, ["view_audit_logs"])
            is_super_admin = (u.username == "admin" or u.email == "admin@omerta.ai" or u.id == 1)
            staff_list.append({
                "id": u.external_id,
                "user_id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "username": u.username,
                "role": u.role,
                "is_active": u.is_active,
                "is_super_admin": is_super_admin,
                "can_delete": not is_super_admin,
                "privileges": privileges,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            })
        return staff_list


@router.post("/staff", status_code=status.HTTP_201_CREATED)
async def create_staff_user(
    body: CreateStaffRequest,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR"])),
) -> dict[str, Any]:
    """Create a new administrator, investigator, fraud analyst, or compliance auditor (customers prohibited)."""
    from infrastructure.security.jwt_auth import hash_password
    import secrets

    clean_email = body.email.strip().lower()
    clean_username = body.username.strip().lower()
    target_role = body.role.upper().strip()

    ALLOWED_STAFF_ROLES = [
        "ADMINISTRATOR",
        "SUB_ADMINISTRATOR",
        "FRAUD_ANALYST",
        "SENIOR_INVESTIGATOR",
        "INVESTIGATOR",
        "AUDITOR",
        "COMPLIANCE_AUDITOR",
    ]

    # Explicitly prohibit creating CUSTOMER accounts from admin staff provisioning
    if target_role == "CUSTOMER" or target_role not in ALLOWED_STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_STAFF_ROLE",
                "message": "Staff management portal cannot create Customer accounts. Customers must be onboarded through the customer registration flow.",
            },
        )

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        # Check collision
        existing = await session.scalar(
            select(User).where((User.email == clean_email) | (User.username == clean_username)).limit(1)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "USER_EXISTS", "message": "A staff user with this email or username already exists."},
            )

        new_user = User(
            external_id=f"USR-{secrets.token_hex(4).upper()}",
            username=clean_username,
            email=clean_email,
            hashed_password=hash_password(body.password),
            full_name=body.full_name.strip(),
            role=target_role,
            is_active=True,
        )
        session.add(new_user)
        await session.flush()

        assigned_privileges = body.privileges if body.privileges else ROLE_DEFAULT_PRIVILEGES.get(target_role, ["view_audit_logs"])

        # Audit event
        audit_event = AuditEvent(
            event_id=f"EVT-STAFF-{new_user.id}",
            event_type="STAFF_ACCOUNT_CREATED",
            actor_type="ADMINISTRATOR",
            actor_id=str(current_user.get("sub", "ADMIN")),
            source="AdminService",
            metadata_={
                "created_staff_id": new_user.external_id,
                "full_name": new_user.full_name,
                "role": new_user.role,
                "privileges": assigned_privileges,
                "creator_admin": current_user.get("username"),
            },
        )
        session.add(audit_event)
        await session.commit()

        return {
            "id": new_user.external_id,
            "full_name": new_user.full_name,
            "email": new_user.email,
            "username": new_user.username,
            "role": new_user.role,
            "is_active": new_user.is_active,
            "privileges": assigned_privileges,
            "message": f"Successfully created {new_user.role} account for {new_user.full_name}.",
        }


@router.delete("/staff/{user_id}")
async def delete_staff_user(
    user_id: str,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR"])),
) -> dict[str, Any]:
    """Delete or revoke a staff/admin account with permanent protection for the Root Super Administrator."""
    from infrastructure.database.models import Session as UserSession
    import secrets

    clean_id = user_id.strip()
    is_target_super_admin_alias = clean_id.lower() in ("admin", "admin@omerta.ai", "dr. sarah al-rashid")

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        target_filters = [
            User.external_id == clean_id,
            User.username == clean_id.lower(),
            User.email == clean_id.lower(),
        ]
        if clean_id.isdigit():
            target_filters.append(User.id == int(clean_id))
        if is_target_super_admin_alias:
            target_filters.extend([
                User.username == "admin",
                User.username == "admin@omerta.ai",
                User.email == "admin@omerta.ai",
                User.id == 1,
            ])

        target = await session.scalar(select(User).where(or_(*target_filters)).limit(1))
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff user not found.")

        # 1. Super Admin Permanent Protection
        is_super_admin = (
            target.username in ("admin", "admin@omerta.ai")
            or target.email == "admin@omerta.ai"
            or target.id == 1
            or is_target_super_admin_alias
        )
        if is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "SUPER_ADMIN_PROTECTED",
                    "message": "Super Administrator 'admin' is permanently protected and cannot be deleted, suspended, or revoked by any other administrator.",
                },
            )

        # 2. Self-deletion prevention
        if target.external_id == current_user.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "SELF_DELETION_PROHIBITED",
                    "message": "Administrators cannot delete their own active account session.",
                },
            )

        # Invalidate active sessions
        active_sessions = (
            await session.scalars(
                select(UserSession).where(UserSession.user_id == target.id, UserSession.is_active == True)
            )
        ).all()
        for sess in active_sessions:
            sess.is_active = False

        target.is_active = False
        staff_name = target.full_name
        staff_role = target.role

        # Audit event
        session.add(
            AuditEvent(
                event_id=f"EVT-STAFF-DEL-{secrets.token_hex(4).upper()}",
                event_type="STAFF_ACCOUNT_REVOKED",
                actor_type="ADMINISTRATOR",
                actor_id=str(current_user.get("sub", "ADMIN")),
                source="AdminStaffManagement",
                metadata_={
                    "revoked_staff_id": target.external_id,
                    "staff_name": staff_name,
                    "role": staff_role,
                    "deleted_by": current_user.get("username"),
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "id": target.external_id,
            "full_name": staff_name,
            "message": f"Staff account for {staff_name} ({staff_role}) has been successfully revoked and deactivated.",
        }


# ============================================================================
# PROBLEM CUSTOMER & RISK QUEUE MANAGEMENT
# ============================================================================

class CustomerRiskResolutionRequest(BaseModel):
    reason: str = Field(default="Identity verified via phone/email verification. Account risk cleared.", min_length=3)
    reset_risk_to: str = Field(default="LOW", description="LOW | MODERATE")


class CustomerNotifyRequest(BaseModel):
    channel: str = Field(default="EMAIL", description="EMAIL | SMS | PHONE_CALL")
    subject: str = Field(default="Omerta.ai Account Security Notice")
    message: str = Field(..., min_length=5)


@router.get("/problem-customers")
async def list_problem_customers(
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> list[dict[str, Any]]:
    """List high-risk, locked, or flagged customers requiring administrative review and direct communication."""
    from apps.api.v1.customer import FAILED_TRANSFER_ATTEMPTS

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        stmt = (
            select(Customer)
            .options(selectinload(Customer.user), selectinload(Customer.accounts))
            .join(User, Customer.user_id == User.id, isouter=True)
            .where(
                (Customer.risk_level.in_(["HIGH", "CRITICAL"]))
                | (Customer.status.in_(["SUSPENDED", "LOCKED"]))
                | (User.is_active.is_(False))
                | (Customer.transfer_status == "BLOCKED")
                | (Customer.transfer_failed_attempts >= 3)
                | (Customer.identity_status.in_(["PENDING_REVIEW", "PENDING", "REJECTED"]))
            )
            .order_by(Customer.updated_at.desc())
        )
        customers = (await session.scalars(stmt)).all()

        results = []
        for c in customers:
            user = c.user
            failed_attempts = FAILED_TRANSFER_ATTEMPTS.get(user.id, 0) if user else 0
            if getattr(c, "transfer_failed_attempts", 0) > failed_attempts:
                failed_attempts = c.transfer_failed_attempts

            # Find latest support ticket if any
            ticket_stmt = (
                select(SupportTicket)
                .options(selectinload(SupportTicket.identity_verifications))
                .where(SupportTicket.customer_id == c.id)
                .order_by(SupportTicket.updated_at.desc())
                .limit(1)
            )
            latest_ticket = await session.scalar(ticket_stmt)

            # Find recent security audit events
            recent_evts_stmt = (
                select(AuditEvent)
                .where(
                    (AuditEvent.actor_id == str(c.user_id))
                    | (AuditEvent.metadata_["customer_id"].astext == c.external_id)
                )
                .order_by(AuditEvent.created_at.desc())
                .limit(5)
            )
            evts = (await session.scalars(recent_evts_stmt)).all()

            evt_list = [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "source": e.source,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                    "metadata": e.metadata_,
                }
                for e in evts
            ]

            total_balance = sum(
                float(acc.balance)
                for acc in (c.accounts or [])
            )

            is_transfer_blocked = (c.transfer_status == "BLOCKED") or (failed_attempts >= 3)

            # Determine lock/flag primary reason based on real security telemetry
            if is_transfer_blocked:
                primary_reason = "Transfer Password Blocked (3 Failed Attempts) — Requires Identity Verification"
            elif c.identity_status == "PENDING_REVIEW":
                primary_reason = "National ID Document Uploaded — Pending Compliance Review"
            elif failed_attempts >= 3 or (user and not user.is_active and any(e.event_type == "EXCESSIVE_PASSWORD_FAILURES" for e in evts)):
                primary_reason = "Locked: 3 Failed Password Attempts (Account Inactivated)"
            elif any(e.event_type == "IMPOSSIBLE_TRAVEL_VELOCITY" for e in evts):
                primary_reason = "Flagged: Impossible Travel Velocity Anomaly"
            elif any(e.event_type == "VPN_TRANSFER_BLOCKED" for e in evts):
                primary_reason = "Flagged: Outbound Transfer Blocked on VPN/Proxy Tunnel"
            elif any(e.event_type == "EXCESSIVE_PASSWORD_FAILURES" for e in evts):
                primary_reason = "Locked: Excessive Password Failures"
            elif c.status in ("SUSPENDED", "LOCKED") or (user and not user.is_active):
                primary_reason = "Account Inactivated & Suspended"
            elif c.risk_level == "CRITICAL":
                primary_reason = "Critical Risk Anomaly Flagged"
            else:
                primary_reason = "Elevated Risk Rating"

            has_uploaded_id = False
            if latest_ticket and latest_ticket.identity_verifications:
                has_uploaded_id = any(bool(v.document_front_url) for v in latest_ticket.identity_verifications)

            results.append({
                "customer_id": c.external_id,
                "user_id": user.external_id if user else None,
                "name": c.name,
                "omerta_user_number": c.omerta_user_number,
                "email": c.email or (user.email if user else "customer@omerta.ai"),
                "phone": c.phone or "+20 10 1111 2222",
                "country": c.declared_country or "EG",
                "risk_level": c.risk_level,
                "status": c.status,
                "primary_reason": primary_reason,
                "customer_issue": latest_ticket.subject if latest_ticket else primary_reason,
                "transfer_status": getattr(c, "transfer_status", "ACTIVE"),
                "transfer_blocked": is_transfer_blocked,
                "failed_password_attempts": failed_attempts,
                "identity_status": getattr(c, "identity_status", "NOT_VERIFIED"),
                "national_id_number": getattr(c, "national_id_number", None),
                "ticket_number": latest_ticket.external_id if latest_ticket else None,
                "ticket_id": latest_ticket.id if latest_ticket else None,
                "ticket_subject": latest_ticket.subject if latest_ticket else None,
                "ticket_issue_type": latest_ticket.issue_type if latest_ticket else None,
                "ticket_status": latest_ticket.status if latest_ticket else None,
                "has_uploaded_id": has_uploaded_id,
                "is_user_active": user.is_active if user else False,
                "total_balance_egp": total_balance,
                "recent_audit_events": evt_list,
                "actions_available": ["SUPPORT_CHAT", "CALL_CUSTOMER", "SEND_EMAIL", "RESOLVE_RISK", "AGENTIC_REPORT", "VIEW_PROFILE"],
            })

        return results


@router.post("/problem-customers/{customer_id}/resolve-risk")
async def resolve_customer_risk(
    customer_id: str,
    body: CustomerRiskResolutionRequest,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR", "FRAUD_ANALYST", "SENIOR_INVESTIGATOR"])),
) -> dict[str, Any]:
    """Manually resolve customer risk, reset password failure counter, and restore active banking privileges."""
    from apps.api.v1.customer import FAILED_TRANSFER_ATTEMPTS
    import secrets

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust = await session.scalar(
            select(Customer)
            .options(selectinload(Customer.user))
            .where((Customer.external_id == customer_id) | (Customer.omerta_user_number == customer_id))
        )
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

        old_risk = cust.risk_level
        old_status = cust.status

        # Reset customer and user status
        cust.risk_level = body.reset_risk_to.upper()
        cust.status = "ACTIVE"
        if cust.user:
            cust.user.is_active = True
            FAILED_TRANSFER_ATTEMPTS[cust.user.id] = 0

        # Create formal AuditEvent
        session.add(
            AuditEvent(
                event_id=f"EVT-RESOLVE-{secrets.token_hex(4).upper()}",
                event_type="CUSTOMER_RISK_MANUALLY_RESOLVED",
                actor_type="ADMINISTRATOR" if current_user.get("role") == "ADMINISTRATOR" else "FRAUD_ANALYST",
                actor_id=str(current_user.get("sub")),
                source="AdminProblemCustomerCenter",
                metadata_={
                    "customer_id": cust.external_id,
                    "customer_name": cust.name,
                    "omerta_user_number": cust.omerta_user_number,
                    "old_risk_level": old_risk,
                    "new_risk_level": cust.risk_level,
                    "old_status": old_status,
                    "new_status": cust.status,
                    "resolution_reason": body.reason,
                    "resolver_user": current_user.get("username"),
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "customer_id": cust.external_id,
            "name": cust.name,
            "risk_level": cust.risk_level,
            "status": cust.status,
            "message": f"Customer risk successfully resolved. Account has been restored to {cust.risk_level} risk and re-activated.",
        }


@router.post("/problem-customers/{customer_id}/notify")
async def notify_customer(
    customer_id: str,
    body: CustomerNotifyRequest,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> dict[str, Any]:
    """Send security notification or direct communication (Email/SMS) to problem customer."""
    import secrets

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust = await session.scalar(
            select(Customer)
            .options(selectinload(Customer.user))
            .where((Customer.external_id == customer_id) | (Customer.omerta_user_number == customer_id))
        )
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

        recipient_contact = cust.user.email if body.channel == "EMAIL" and cust.user else (cust.phone or "+20 10 1111 2222")

        # Dispatch real email if channel is EMAIL
        delivery_res = None
        if body.channel.upper() == "EMAIL" and recipient_contact and "@" in recipient_contact:
            delivery_res = await EmailService.send_security_notice_email(
                to_email=recipient_contact,
                customer_name=cust.name,
                subject=body.subject,
                message=body.message,
            )

        # Record notification in audit log
        session.add(
            AuditEvent(
                event_id=f"EVT-NOTIFY-{secrets.token_hex(4).upper()}",
                event_type="CUSTOMER_SECURITY_NOTICE_DISPATCHED",
                actor_type="ADMIN_STAFF",
                actor_id=str(current_user.get("sub")),
                source="AdminCommunicationHub",
                metadata_={
                    "customer_id": cust.external_id,
                    "customer_name": cust.name,
                    "channel": body.channel,
                    "sender": "abdomostafa13571234@gmail.com",
                    "recipient": recipient_contact,
                    "subject": body.subject,
                    "message_preview": body.message[:100],
                    "delivery_status": delivery_res.to_dict() if delivery_res else None,
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "customer_id": cust.external_id,
            "recipient": recipient_contact,
            "sender": "abdomostafa13571234@gmail.com",
            "channel": body.channel,
            "message": f"Security communication dispatched from abdomostafa13571234@gmail.com to {cust.name} ({recipient_contact}).",
        }


@router.get("/problem-customers/{customer_id}/agentic-summary")
async def get_problem_customer_agentic_summary(
    customer_id: str,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> dict[str, Any]:
    """Autonomous Agentic Forensic Summary for high-risk problem customer investigation."""
    from apps.api.v1.customer import FAILED_TRANSFER_ATTEMPTS

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust = await session.scalar(
            select(Customer)
            .options(selectinload(Customer.user), selectinload(Customer.accounts))
            .where((Customer.external_id == customer_id) | (Customer.omerta_user_number == customer_id))
        )
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

        user = cust.user
        failed_attempts = FAILED_TRANSFER_ATTEMPTS.get(user.id, 0) if user else 0

        recent_evts_stmt = (
            select(AuditEvent)
            .where(
                (AuditEvent.actor_id == str(cust.user_id))
                | (AuditEvent.metadata_["customer_id"].astext == cust.external_id)
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(10)
        )
        evts = (await session.scalars(recent_evts_stmt)).all()

        total_balance = sum(float(acc.balance) for acc in (cust.accounts or []))

        # Synthesize Multi-Agent Forensic Findings
        findings = []
        if failed_attempts >= 3 or any(e.event_type == "EXCESSIVE_PASSWORD_FAILURES" for e in evts):
            findings.append({
                "category": "AUTHENTICATION_INTEGRITY",
                "severity": "CRITICAL",
                "finding": "3 consecutive incorrect password attempts detected during transfer confirmation.",
                "action_required": "Direct Phone Identity Verification or Out-of-Band Password Reset.",
            })
        if any(e.event_type == "IMPOSSIBLE_TRAVEL_VELOCITY" for e in evts):
            findings.append({
                "category": "GEOGRAPHIC_VELOCITY",
                "severity": "CRITICAL",
                "finding": "Impossible travel speed / rapid domestic city jump observed within minutes.",
                "action_required": "Verify current physical location and device ownership.",
            })
        if any(e.event_type == "VPN_TRANSFER_BLOCKED" for e in evts):
            findings.append({
                "category": "NETWORK_TELEMETRY",
                "severity": "HIGH",
                "finding": "Outbound transfer initiated via commercial VPN / proxy anonymization tunnel.",
                "action_required": "Instruct customer to disable VPN before executing transfers.",
            })
        if not findings:
            findings.append({
                "category": "BEHAVIORAL_ANOMALY",
                "severity": "MEDIUM",
                "finding": f"Customer risk elevated to {cust.risk_level} based on transaction patterns.",
                "action_required": "Routine compliance review.",
            })

        return {
            "customer_id": cust.external_id,
            "omerta_user_number": cust.omerta_user_number,
            "name": cust.name,
            "email": cust.email or (user.email if user else "customer@omerta.ai"),
            "phone": cust.phone or "+20 10 1111 2222",
            "risk_level": cust.risk_level,
            "status": cust.status,
            "is_user_active": user.is_active if user else False,
            "failed_password_attempts": failed_attempts,
            "total_balance_egp": total_balance,
            "forensic_findings": findings,
            "agentic_agents": [
                {"agent": "IdentityVerificationAgent", "verdict": "FLAGGED" if (failed_attempts >= 3 or not user.is_active) else "VERIFIED"},
                {"agent": "NetworkTelemetryAgent", "verdict": "VPN_RESTRICTED" if any(e.event_type == "VPN_TRANSFER_BLOCKED" for e in evts) else "DIRECT_IP"},
                {"agent": "GeographicVelocityAgent", "verdict": "ANOMALOUS_VELOCITY" if any(e.event_type == "IMPOSSIBLE_TRAVEL_VELOCITY" for e in evts) else "NORMAL_DOMESTIC"},
                {"agent": "ComplianceResolutionAgent", "verdict": "ACTION_REQUIRED" if cust.status == "SUSPENDED" else "MONITORING"},
            ],
            "recommended_resolution": "Call customer on verified phone number, confirm identity, then use 'Resolve & Unlock' to reactivate banking.",
        }


# ============================================================================
# PENDING TRANSACTIONS & HUMAN REVIEW DECISION EXECUTION
# ============================================================================

class TransactionApprovalRequest(BaseModel):
    rationale: str = Field(default="Analyst verified identity and transaction legitimacy. Hold released.", min_length=3)


@router.post("/transactions/{transaction_id}/approve")
async def approve_pending_transaction(
    transaction_id: str,
    body: TransactionApprovalRequest,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR", "FRAUD_ANALYST", "SENIOR_INVESTIGATOR"])),
) -> dict[str, Any]:
    """Approve a pending or flagged transaction, releasing human review holds and executing funds dispatch."""
    import secrets

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        txn = await session.scalar(
            select(Transaction).where(Transaction.external_id == transaction_id)
        )
        if not txn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

        old_status = txn.status
        old_review_status = txn.review_status

        # Approve and complete
        txn.review_status = "APPROVED"
        txn.status = "COMPLETED"

        session.add(
            AuditEvent(
                event_id=f"EVT-TXNAPPR-{secrets.token_hex(4).upper()}",
                event_type="TRANSACTION_APPROVED_AND_RELEASED",
                actor_type="ANALYST",
                actor_id=str(current_user.get("sub")),
                source="HumanReviewQueue",
                transaction_id=txn.external_id,
                metadata_={
                    "transaction_id": txn.external_id,
                    "amount": str(txn.amount),
                    "old_status": old_status,
                    "new_status": txn.status,
                    "old_review_status": old_review_status,
                    "new_review_status": txn.review_status,
                    "rationale": body.rationale,
                    "analyst": current_user.get("username"),
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "transaction_id": txn.external_id,
            "status": txn.status,
            "review_status": txn.review_status,
            "message": f"Transaction {txn.external_id} approved by analyst. Hold released and processing completed.",
        }


@router.post("/transactions/{transaction_id}/reject")
async def reject_pending_transaction(
    transaction_id: str,
    body: TransactionApprovalRequest,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR", "FRAUD_ANALYST", "SENIOR_INVESTIGATOR"])),
) -> dict[str, Any]:
    """Reject a flagged transaction, blocking money transfer and logging fraud detection disposition."""
    import secrets

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        txn = await session.scalar(
            select(Transaction).where(Transaction.external_id == transaction_id)
        )
        if not txn:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")

        txn.review_status = "REJECTED"
        txn.status = "BLOCKED"

        session.add(
            AuditEvent(
                event_id=f"EVT-TXNREJ-{secrets.token_hex(4).upper()}",
                event_type="TRANSACTION_REJECTED_FRAUD",
                actor_type="ANALYST",
                actor_id=str(current_user.get("sub")),
                source="HumanReviewQueue",
                transaction_id=txn.external_id,
                metadata_={
                    "transaction_id": txn.external_id,
                    "amount": str(txn.amount),
                    "new_status": txn.status,
                    "new_review_status": txn.review_status,
                    "rationale": body.rationale,
                    "analyst": current_user.get("username"),
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "transaction_id": txn.external_id,
            "status": txn.status,
            "review_status": txn.review_status,
            "message": f"Transaction {txn.external_id} rejected. Transfer cancelled and flagged as suspicious.",
        }


# ============================================================================
# AGENTIC AI WORKFLOW & SAR GENERATOR (COMING SOON PREVIEW)
# ============================================================================

@router.post("/agentic/generate-sar-report")
async def preview_agentic_sar_report(
    case_or_txn_id: str = Query(..., description="Target Case or Transaction External ID"),
    current_user: dict[str, Any] = Depends(require_role(ADMIN_ROLES)),
) -> dict[str, Any]:
    """Agentic AI SAR Workflow Generator — Preview of Autonomous Multi-Agent AML Pipeline."""
    return {
        "status": "COMING_SOON",
        "feature": "Agentic AI SAR Autonomous Report Drafter",
        "target_id": case_or_txn_id,
        "agents": [
            {"agent": "TopologyInspectorAgent", "role": "Analyzes Neo4j cyclic money flows and entity rings", "status": "Ready in Phase 3"},
            {"agent": "AnomalyClassifierAgent", "role": "Evaluates velocity spikes, VPN hops, and Mule patterns", "status": "Ready in Phase 3"},
            {"agent": "FinCEN_NarrativeAgent", "role": "Drafts formal SAR narrative complying with FinCEN guidelines", "status": "Ready in Phase 3"},
            {"agent": "RegTechComplianceAgent", "role": "Cross-references Central Bank regulations and typologies", "status": "Ready in Phase 3"},
        ],
        "preview_narrative": (
            "AUTOMATED DRAFT (COMING SOON): Multiple high-velocity transfers were initiated following rapid IP geolocation shifts. "
            "Graph topology revealed closed 3-hop cyclic fund disbursement matching structuring (smurfing) typologies."
        ),
        "message": "✨ Agentic AI SAR Report Generation will be fully autonomous in the upcoming phase.",
    }


