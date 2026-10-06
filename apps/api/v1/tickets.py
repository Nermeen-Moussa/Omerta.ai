"""Customer & Admin Tickets API Router for Omerta.ai.

Exposes RESTful endpoints conforming to the Master Specification:
- /api/v1/customer/tickets
- /api/v1/admin/tickets
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domain.services.customer_service import CustomerService
from domain.services.ticket_service import TicketService
from domain.ticket_policy import TicketPriority, TicketType
from infrastructure.database.session import get_engine
from infrastructure.security.jwt_auth import get_current_user, require_role

customer_tickets_router = APIRouter(prefix="/customer/tickets", tags=["Customer Support & Security Tickets"])
admin_tickets_router = APIRouter(prefix="/admin/tickets", tags=["Admin Ticket Center"])

ADMIN_AUDITOR_ROLES = [
    "ADMINISTRATOR",
    "SUB_ADMINISTRATOR",
    "FRAUD_ANALYST",
    "INVESTIGATOR",
    "SENIOR_INVESTIGATOR",
    "AUDITOR",
    "COMPLIANCE_AUDITOR",
    "SENIOR_COMPLIANCE",
]


# ==============================================================================
# Pydantic Request Schemas
# ==============================================================================

class CreateTicketPayload(BaseModel):
    ticket_type: str = Field(default="GENERAL_SUPPORT", description="16 standardized ticket types")
    issue_type: str | None = Field(default=None, description="Alias for ticket_type")
    title: str | None = Field(default=None, min_length=3, max_length=255)
    subject: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, min_length=3)
    customer_message: str | None = Field(default=None, min_length=3)
    related_transaction_id: int | str | None = None
    related_account_id: int | str | None = None
    priority: str | None = None


class SendMessagePayload(BaseModel):
    message_text: str = Field(..., min_length=1)
    attachment_url: str | None = None
    attachment_name: str | None = None
    attachment_type: str = Field(default="NONE", description="NONE | IMAGE | PDF | DOCUMENT")


class SubmitVerificationPayload(BaseModel):
    national_id_number: str = Field(..., min_length=6, max_length=64)
    document_type: str = Field(default="NATIONAL_ID", description="NATIONAL_ID | PASSPORT | DRIVERS_LICENSE")
    document_front_url: str = Field(..., min_length=5)
    document_back_url: str | None = None


class VerifyIdentityPayload(BaseModel):
    decision: str = Field(..., description="VERIFIED | REJECTED")
    reviewer_notes: str = Field(..., min_length=3)


class RestoreTransferPayload(BaseModel):
    confirmation: bool = Field(..., description="Must be true to confirm restoration")
    reason: str = Field(..., min_length=5, description="Mandatory audit justification for restoration")


class ResolveTicketPayload(BaseModel):
    resolution_reason: str = Field(..., min_length=3)
    admin_notes: str | None = None


class EscalateTicketPayload(BaseModel):
    reason: str = Field(..., min_length=3)


class AssignTicketPayload(BaseModel):
    assigned_user_id: int | None = None
    assigned_analyst_id: int | None = None


class RequestDocumentPayload(BaseModel):
    document_type: str = Field(default="NATIONAL_ID")
    instructions: str = Field(default="Please upload clear photos of your National ID or Passport.")


# ==============================================================================
# Helper Serializer
# ==============================================================================

def serialize_ticket(t: Any, is_admin: bool = False) -> dict[str, Any]:
    """Serialize SupportTicket into safe response format without triggering greenlet I/O."""
    t_dict = t.__dict__ if hasattr(t, "__dict__") else {}

    msgs_raw = t_dict.get("messages") or getattr(t, "_messages", []) or []
    messages = [
        {
            "id": m.id,
            "message_id": m.external_id,
            "sender_role": m.sender_role,
            "sender_name": m.sender_name,
            "message_text": m.message_text,
            "attachment_url": m.attachment_url,
            "attachment_name": m.attachment_name,
            "attachment_type": m.attachment_type,
            "is_read": m.is_read_by_recipient,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs_raw
    ]

    idvs_raw = t_dict.get("identity_verifications") or []
    idvs = [
        {
            "id": v.id,
            "verification_id": v.external_id,
            "document_type": v.document_type,
            "national_id_number": v.national_id_number,
            "document_front_url": v.document_front_url,
            "document_back_url": v.document_back_url,
            "verification_status": v.verification_status,
            "status": v.verification_status,
            "reviewer_notes": v.reviewer_notes,
            "reviewed_at": v.reviewed_at.isoformat() if v.reviewed_at else None,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in idvs_raw
    ]

    restorations_raw = t_dict.get("transfer_restorations") or []
    restorations = [
        {
            "id": r.id,
            "external_id": r.external_id,
            "actor_id": r.actor_id,
            "actor_name": r.actor_name,
            "actor_role": r.actor_role,
            "restoration_number": r.restoration_number,
            "previous_state": r.previous_state,
            "new_state": r.new_state,
            "reason": r.reason,
            "verification_reference": r.verification_reference,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in restorations_raw
    ]

    cust = t_dict.get("customer")
    latest_idv = idvs[-1] if idvs else None
    registered_nat_id = cust.national_id_number if cust else None
    is_transfer_blocked = (cust.transfer_status == "BLOCKED" if cust else False)

    out: dict[str, Any] = {
        "id": t.id,
        "ticket_id": t.external_id,
        "ticket_number": t.external_id,
        "ticket_type": t.ticket_type,
        "issue_type": t.ticket_type,
        "category": t.category,
        "priority": t.priority,
        "status": t.status,
        "title": t.title or t.subject,
        "subject": t.subject or t.title,
        "description": t.description or t.customer_message,
        "customer_message": t.customer_message or t.description,
        "opened_by": t.opened_by,
        "requires_identity_verification": t.requires_identity_verification,
        "identity_verification_status": t.identity_verification_status,
        "identity_status": cust.identity_status if cust else "NOT_VERIFIED",
        "requires_compliance_review": t.requires_compliance_review,
        "escalated_to_compliance": t.escalated_to_compliance,
        "related_transaction_id": t.related_transaction_id,
        "related_account_id": t.related_account_id,
        "restoration_requested": t.restoration_requested,
        "restoration_approved": t.restoration_approved,
        "restoration_approved_by": t.restoration_approved_by,
        "restoration_approved_at": t.restoration_approved_at.isoformat() if t.restoration_approved_at else None,
        "customer_restoration_count_at_creation": t.customer_restoration_count_at_creation,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "resolution_reason": t.resolution_reason,
        "messages": messages,
        "identity_verifications": idvs,
        "identity_verification": latest_idv,
        "transfer_blocked": is_transfer_blocked,
        "customer": {
            "id": cust.external_id if cust else None,
            "name": cust.name if cust else "Customer",
            "omerta_user_number": cust.omerta_user_number if cust else None,
            "email": cust.email if cust else None,
            "phone": cust.phone if cust else None,
            "transfer_status": cust.transfer_status if cust else "ACTIVE",
            "identity_status": cust.identity_status if cust else "NOT_VERIFIED",
            "national_id_number": registered_nat_id,
            "require_transfer_password_change": getattr(cust, "require_transfer_password_change", False) if cust else False,
        } if cust else None,
        "customer_name": cust.name if cust else "Customer",
        "customer_email": cust.email if cust else "",
        "omerta_user_number": cust.omerta_user_number if cust else "",
        "national_id_number": registered_nat_id,
    }

    if is_admin:
        out["admin_notes"] = t.admin_notes
        out["related_risk_assessment_id"] = t.related_risk_assessment_id
        out["transfer_restorations"] = restorations
        out["context_data"] = t.context_data

    return out


# ==============================================================================
# Customer Endpoints
# ==============================================================================

@customer_tickets_router.post("", status_code=status.HTTP_201_CREATED)
async def create_customer_ticket(
    body: CreateTicketPayload,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new support/security ticket for authenticated customer with IDOR validation."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer:
            raise HTTPException(status_code=404, detail="Customer profile not found.")

        ticket_service = TicketService(session)
        resolved_title = body.title or body.subject or f"{body.ticket_type.replace('_', ' ').title()} Request"
        resolved_desc = body.description or body.customer_message or resolved_title
        resolved_type = body.ticket_type or body.issue_type or "GENERAL_SUPPORT"

        try:
            ticket = await ticket_service.create_ticket(
                customer=customer,
                title=resolved_title,
                description=resolved_desc,
                ticket_type=resolved_type,
                related_transaction_id=body.related_transaction_id,
                related_account_id=body.related_account_id,
                priority_override=body.priority,
                client_ip=client_ip,
                opened_by="CUSTOMER",
            )
            await session.commit()
            return serialize_ticket(ticket, is_admin=False)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))


@customer_tickets_router.get("")
async def list_customer_tickets(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """List customer tickets with pagination."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer:
            raise HTTPException(status_code=404, detail="Customer profile not found.")

        ticket_service = TicketService(session)
        tickets, total = await ticket_service.list_customer_tickets(customer.id, status, page, page_size)
        return {
            "items": [serialize_ticket(t, is_admin=False) for t in tickets],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@customer_tickets_router.get("/{ticket_id}")
async def get_customer_ticket(
    ticket_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve ticket details with customer isolation (IDOR protected)."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer:
            raise HTTPException(status_code=404, detail="Customer profile not found.")

        ticket_service = TicketService(session)
        try:
            ticket = await ticket_service.get_ticket_by_identifier(ticket_id, customer_id=customer.id)
            if not ticket:
                raise HTTPException(status_code=404, detail="Support ticket not found.")
            return serialize_ticket(ticket, is_admin=False)
        except PermissionError as err:
            raise HTTPException(status_code=403, detail=str(err))


@customer_tickets_router.post("/{ticket_id}/verification", status_code=status.HTTP_201_CREATED)
async def submit_customer_verification(
    ticket_id: str,
    body: SubmitVerificationPayload,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit National ID / Passport documents for compliance verification."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer:
            raise HTTPException(status_code=404, detail="Customer profile not found.")

        ticket_service = TicketService(session)
        try:
            ticket = await ticket_service.get_ticket_by_identifier(ticket_id, customer_id=customer.id)
            if not ticket:
                raise HTTPException(status_code=404, detail="Support ticket not found.")

            idv = await ticket_service.submit_identity_verification(
                ticket=ticket,
                customer=customer,
                national_id_number=body.national_id_number,
                document_type=body.document_type,
                document_front_url=body.document_front_url,
                document_back_url=body.document_back_url,
            )
            await session.commit()
            return {
                "success": True,
                "verification_id": idv.external_id,
                "status": "PENDING_REVIEW",
                "message": "National ID documents submitted successfully for compliance review.",
            }
        except PermissionError as err:
            raise HTTPException(status_code=403, detail=str(err))


@customer_tickets_router.post("/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_customer_message(
    ticket_id: str,
    body: SendMessagePayload,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Send customer message in ticket conversation."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer:
            raise HTTPException(status_code=404, detail="Customer profile not found.")

        ticket_service = TicketService(session)
        ticket = await ticket_service.get_ticket_by_identifier(ticket_id, customer_id=customer.id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        msg = SupportMessage(
            external_id=f"MSG-{secrets.token_hex(4).upper()}",
            ticket_id=ticket.id,
            sender_user_id=customer.user_id,
            sender_role="CUSTOMER",
            sender_name=customer.name,
            message_text=body.message_text.strip(),
            attachment_url=body.attachment_url,
            attachment_name=body.attachment_name,
            attachment_type=body.attachment_type,
        )
        session.add(msg)
        if ticket.status in ("RESOLVED", "WAITING_FOR_CUSTOMER", "OPEN"):
            ticket.status = "IN_REVIEW"
        ticket.updated_at = datetime.now(UTC)
        await session.commit()

        return {
            "success": True,
            "message_id": msg.external_id,
            "sender_name": msg.sender_name,
            "sender_role": msg.sender_role,
            "message_text": msg.message_text,
            "created_at": msg.created_at.isoformat(),
        }


# ==============================================================================
# Admin & Staff Endpoints
# ==============================================================================

@admin_tickets_router.get("")
async def list_admin_tickets(
    status: str | None = None,
    ticket_type: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    restoration_required: bool | None = None,
    escalated: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """List operational support & security cases with rich multi-dimensional filtering."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket_service = TicketService(session)
        tickets, total = await ticket_service.list_admin_tickets(
            status_filter=status,
            ticket_type=ticket_type,
            priority=priority,
            search=search,
            restoration_required=restoration_required,
            escalated=escalated,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [serialize_ticket(t, is_admin=True) for t in tickets],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@admin_tickets_router.get("/stats")
async def get_admin_ticket_stats(
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Retrieve aggregate ticket and restoration KPIs for the Admin Control Center."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket_service = TicketService(session)
        return await ticket_service.get_ticket_stats()


@admin_tickets_router.get("/{ticket_id}")
async def get_admin_ticket(
    ticket_id: str,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Retrieve full operational ticket intelligence and conversation thread."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_ticket_by_identifier(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")
        return serialize_ticket(ticket, is_admin=True)


@admin_tickets_router.post("/{ticket_id}/verify")
async def verify_ticket_identity(
    ticket_id: str,
    body: VerifyIdentityPayload,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Approve or reject customer National ID verification."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_ticket_by_identifier(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        actor_name = current_user.get("full_name") or current_user.get("username", "Staff")
        actor_role = current_user.get("role", "ADMINISTRATOR")

        try:
            idv = await ticket_service.review_identity_verification(
                ticket=ticket,
                decision=body.decision,
                reviewer_notes=body.reviewer_notes,
                actor_id=str(current_user.get("sub", "")),
                actor_name=actor_name,
                actor_role=actor_role,
            )
            await session.commit()
            return {
                "success": True,
                "decision": body.decision,
                "identity_status": body.decision,
                "message": f"Identity verification successfully recorded as {body.decision}.",
            }
        except PermissionError as err:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))


@admin_tickets_router.post("/{ticket_id}/reject-verification")
async def reject_ticket_identity(
    ticket_id: str,
    body: VerifyIdentityPayload,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Explicit endpoint for rejecting National ID verification."""
    body.decision = "REJECTED"
    return await verify_ticket_identity(ticket_id, body, current_user)


@admin_tickets_router.post("/{ticket_id}/restore-transfer")
async def restore_ticket_transfer(
    ticket_id: str,
    body: RestoreTransferPayload,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Restore customer transfer privileges under the progressive 4-tier security policy.

    CRITICAL RULE:
    Restoration is distinct from Ticket Resolution.
    """
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_ticket_by_identifier(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        actor_name = current_user.get("full_name") or current_user.get("username", "Administrator")
        actor_role = current_user.get("role", "ADMINISTRATOR")

        try:
            restoration = await ticket_service.restore_transfer_privileges(
                ticket=ticket,
                reason=body.reason,
                actor_id=str(current_user.get("sub", "")),
                actor_name=actor_name,
                actor_role=actor_role,
                confirmation=body.confirmation,
            )
            await session.commit()
            return {
                "success": True,
                "restoration_id": restoration.external_id,
                "restoration_number": restoration.restoration_number,
                "transfer_status": "ACTIVE",
                "message": f"Customer transfer privileges successfully restored (Tier #{restoration.restoration_number}).",
            }
        except PermissionError as err:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))


@admin_tickets_router.post("/{ticket_id}/resolve")
async def resolve_admin_ticket(
    ticket_id: str,
    body: ResolveTicketPayload,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Resolve a support ticket without automatically altering transfer restriction state."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_ticket_by_identifier(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        actor_name = current_user.get("full_name") or current_user.get("username", "Staff")
        actor_role = current_user.get("role", "ADMINISTRATOR")

        if actor_role in ("AUDITOR", "COMPLIANCE_AUDITOR"):
            raise HTTPException(status_code=403, detail="Audit Admins have observation and messaging responsibility only.")

        try:
            ticket = await ticket_service.resolve_ticket(
                ticket=ticket,
                resolution_reason=body.resolution_reason,
                admin_notes=body.admin_notes,
                actor_id=str(current_user.get("sub", "")),
                actor_name=actor_name,
                actor_role=actor_role,
            )
            await session.commit()
            return {
                "success": True,
                "status": "RESOLVED",
                "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
                "message": "Ticket successfully marked as RESOLVED.",
            }
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))


@admin_tickets_router.post("/{ticket_id}/escalate")
async def escalate_admin_ticket(
    ticket_id: str,
    body: EscalateTicketPayload,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Escalate a ticket to Senior Compliance or Fraud Analyst review."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_ticket_by_identifier(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        actor_name = current_user.get("full_name") or current_user.get("username", "Staff")
        actor_role = current_user.get("role", "ADMINISTRATOR")

        try:
            ticket = await ticket_service.escalate_ticket(
                ticket=ticket,
                reason=body.reason,
                actor_id=str(current_user.get("sub", "")),
                actor_name=actor_name,
                actor_role=actor_role,
            )
            await session.commit()
            return {
                "success": True,
                "status": "ESCALATED",
                "escalated_to_compliance": True,
                "message": "Ticket successfully escalated for compliance investigation.",
            }
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))


@admin_tickets_router.post("/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_admin_message(
    ticket_id: str,
    body: SendMessagePayload,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Send admin / auditor message in ticket conversation thread."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket_service = TicketService(session)
        ticket = await ticket_service.get_ticket_by_identifier(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        actor_name = current_user.get("full_name") or current_user.get("username", "Staff")
        actor_role = current_user.get("role", "ADMINISTRATOR")

        msg = SupportMessage(
            external_id=f"MSG-{secrets.token_hex(4).upper()}",
            ticket_id=ticket.id,
            sender_user_id=int(current_user.get("sub", 0)) if str(current_user.get("sub", "")).isdigit() else None,
            sender_role=actor_role,
            sender_name=f"{actor_name} ({actor_role.replace('_', ' ').title()})",
            message_text=body.message_text.strip(),
            attachment_url=body.attachment_url,
            attachment_name=body.attachment_name,
            attachment_type=body.attachment_type,
        )
        session.add(msg)
        ticket.status = "WAITING_FOR_CUSTOMER"
        ticket.updated_at = datetime.now(UTC)
        await session.commit()

        return {
            "success": True,
            "message_id": msg.external_id,
            "sender_name": msg.sender_name,
            "sender_role": msg.sender_role,
            "message_text": msg.message_text,
            "created_at": msg.created_at.isoformat(),
        }
