"""Support Tickets & WhatsApp-Style Chat API Router for Omerta.ai.

Provides endpoints for:
1. Customer Support Tickets (Opening tickets, sending messages, uploading National ID documentation).
2. Staff & Auditor Support Dashboard (Viewing queue, filtering transfer-blocked customers, WhatsApp-style chat).
3. Human Identity Verification (Approving / rejecting National ID submissions).
4. Administrative Transfer Access Restoration (Unblocking transfer services with audit trail).
"""

from datetime import UTC, datetime
from decimal import Decimal
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.services.customer_service import CustomerService
from infrastructure.database.models import (
    Account,
    AuditEvent,
    Customer,
    IdentityVerification,
    SupportMessage,
    SupportTicket,
    User,
)
from infrastructure.database.session import get_engine
from infrastructure.security.jwt_auth import get_current_user, require_role

router = APIRouter(prefix="/support", tags=["Support & Security Cases"])

ADMIN_AUDITOR_ROLES = [
    "ADMINISTRATOR",
    "FRAUD_ANALYST",
    "INVESTIGATOR",
    "SENIOR_INVESTIGATOR",
    "AUDITOR",
    "COMPLIANCE_AUDITOR",
]


def _ticket_condition(ticket_id: str | int):
    s = str(ticket_id)
    if s.isdigit():
        return or_(SupportTicket.id == int(s), SupportTicket.external_id == s)
    return SupportTicket.external_id == s


# ==============================================================================
# Pydantic Schemas
# ==============================================================================

class CreateTicketRequest(BaseModel):
    issue_type: str = Field(
        default="TRANSFER_BLOCKED",
        description="FORGOTTEN_TRANSFER_PASSWORD | TRANSFER_BLOCKED | IDENTITY_VERIFICATION | ACCOUNT_SECURITY | TRANSACTION_ISSUE | OTHER",
    )
    subject: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    account_id: str | None = None
    priority: str = Field(default="HIGH", description="LOW | MEDIUM | HIGH | URGENT")
    attachment_url: str | None = None
    attachment_name: str | None = None
    attachment_type: str = Field(default="NONE", description="NONE | IMAGE | PDF | DOCUMENT")


class SendMessageRequest(BaseModel):
    message_text: str = Field(..., min_length=1)
    attachment_url: str | None = None
    attachment_name: str | None = None
    attachment_type: str = Field(default="NONE", description="NONE | IMAGE | PDF | DOCUMENT")


class UploadIdDocumentRequest(BaseModel):
    national_id_number: str = Field(..., min_length=6, max_length=64)
    document_type: str = Field(default="NATIONAL_ID", description="NATIONAL_ID | PASSPORT | DRIVERS_LICENSE")
    document_front_url: str = Field(..., min_length=5, description="Image URL or base64 data URI of ID front")
    document_back_url: str | None = None


class VerifyIdentityDecisionRequest(BaseModel):
    decision: str = Field(..., description="VERIFIED | REJECTED")
    reviewer_notes: str = Field(..., min_length=3, description="Compliance notes explaining verification result")


class RestoreTransferAccessRequest(BaseModel):
    confirmation: bool = Field(..., description="Must be True to confirm restoration")
    reason: str = Field(default="Identity verified by compliance staff. Transfer access restored.", min_length=5)


# ==============================================================================
# Customer Endpoints
# ==============================================================================

@router.post("/tickets", status_code=status.HTTP_201_CREATED)
async def create_support_ticket(
    body: CreateTicketRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Open a new support/security ticket with automatic customer context."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer:
            raise HTTPException(status_code=404, detail="Customer profile not found.")

        # Resolve Account ID if provided
        acc_pk = None
        if body.account_id:
            acc = await session.scalar(select(Account).where(Account.external_id == body.account_id))
            if acc:
                acc_pk = acc.id

        ticket_ext_id = f"TCK-{secrets.token_hex(3).upper()}-{secrets.token_hex(2).upper()}"

        context_data = {
            "customer_id": customer.external_id,
            "omerta_user_number": customer.omerta_user_number,
            "transfer_status": getattr(customer, "transfer_status", "ACTIVE"),
            "failed_attempts": getattr(customer, "transfer_failed_attempts", 0),
            "identity_status": getattr(customer, "identity_status", "NOT_VERIFIED"),
            "client_ip": client_ip,
            "created_at": datetime.now(UTC).isoformat(),
        }

        ticket = SupportTicket(
            external_id=ticket_ext_id,
            customer_id=customer.id,
            account_id=acc_pk,
            issue_type=body.issue_type,
            priority=body.priority,
            status="OPEN",
            subject=body.subject.strip(),
            description=body.description.strip(),
            context_data=context_data,
        )
        session.add(ticket)
        await session.flush()

        # Add initial customer message to conversation
        msg_ext_id = f"MSG-{secrets.token_hex(4).upper()}"
        initial_msg = SupportMessage(
            external_id=msg_ext_id,
            ticket_id=ticket.id,
            sender_user_id=customer.user_id,
            sender_role="CUSTOMER",
            sender_name=customer.name,
            message_text=body.description.strip(),
            attachment_url=body.attachment_url,
            attachment_name=body.attachment_name,
            attachment_type=body.attachment_type,
        )
        session.add(initial_msg)

        # Audit Event
        session.add(
            AuditEvent(
                event_id=f"EVT-TCK-{secrets.token_hex(4).upper()}",
                event_type="SUPPORT_TICKET_CREATED",
                actor_type="CUSTOMER",
                actor_id=str(customer.user_id),
                source="SupportService",
                metadata_={
                    "ticket_id": ticket_ext_id,
                    "issue_type": body.issue_type,
                    "subject": body.subject,
                    "customer_id": customer.external_id,
                    "transfer_status": customer.transfer_status,
                },
            )
        )
        await session.commit()

        is_blocked = (customer.transfer_status == "BLOCKED") or (body.issue_type == "TRANSFER_BLOCKED")
        return {
            "success": True,
            "id": ticket.id,
            "ticket_id": ticket.external_id,
            "ticket_number": ticket.external_id,
            "issue_type": ticket.issue_type,
            "priority": ticket.priority,
            "status": ticket.status,
            "subject": ticket.subject,
            "transfer_blocked": is_blocked,
            "created_at": ticket.created_at.isoformat(),
        }


@router.get("/tickets")
async def list_customer_tickets(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all support tickets opened by the authenticated customer."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer:
            return []

        stmt = (
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages), selectinload(SupportTicket.identity_verifications))
            .where(SupportTicket.customer_id == customer.id)
            .order_by(desc(SupportTicket.updated_at))
        )
        tickets = (await session.scalars(stmt)).all()

        results = []
        for t in tickets:
            last_msg = t.messages[-1] if t.messages else None
            latest_idv = t.identity_verifications[-1] if t.identity_verifications else None
            results.append({
                "id": t.id,
                "ticket_id": t.external_id,
                "ticket_number": t.external_id,
                "customer_name": customer.name,
                "customer_email": customer.email,
                "omerta_user_number": customer.omerta_user_number,
                "national_id_number": customer.national_id_number,
                "transfer_blocked": (customer.transfer_status == "BLOCKED") or (t.issue_type == "TRANSFER_BLOCKED"),
                "identity_status": customer.identity_status,
                "identity_verification_id": latest_idv.id if latest_idv else None,
                "identity_verification": {
                    "id": latest_idv.id,
                    "verification_id": latest_idv.external_id,
                    "document_type": latest_idv.document_type,
                    "national_id_number": latest_idv.national_id_number,
                    "document_front_url": latest_idv.document_front_url,
                    "document_back_url": latest_idv.document_back_url,
                    "status": latest_idv.verification_status,
                    "reviewer_notes": latest_idv.reviewer_notes,
                } if latest_idv else None,
                "issue_type": t.issue_type,
                "priority": t.priority,
                "status": t.status,
                "subject": t.subject,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
                "last_message": {
                    "sender_name": last_msg.sender_name if last_msg else None,
                    "sender_role": last_msg.sender_role if last_msg else None,
                    "text": last_msg.message_text if last_msg else t.description,
                    "created_at": last_msg.created_at.isoformat() if last_msg else t.created_at.isoformat(),
                } if last_msg else None,
            })
        return results


@router.get("/tickets/{ticket_id}")
async def get_ticket_details(
    ticket_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Get full ticket details and complete WhatsApp-style conversation thread."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        stmt = (
            select(SupportTicket)
            .options(
                selectinload(SupportTicket.customer),
                selectinload(SupportTicket.messages),
                selectinload(SupportTicket.identity_verifications),
            )
            .where(_ticket_condition(ticket_id))
        )
        ticket = await session.scalar(stmt)
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        # Verify access authorization: Customer owns ticket OR user has staff role
        user_role = current_user.get("role", "CUSTOMER")
        if user_role == "CUSTOMER":
            cust_service = CustomerService(session)
            customer = await cust_service.get_customer_by_user_id(current_user["sub"])
            if not customer or ticket.customer_id != customer.id:
                raise HTTPException(status_code=403, detail="Access denied to this support ticket.")

        messages = []
        for m in ticket.messages:
            messages.append({
                "id": m.id,
                "message_id": m.external_id,
                "sender_role": m.sender_role,
                "sender_name": m.sender_name,
                "message_text": m.message_text,
                "attachment_url": m.attachment_url,
                "attachment_name": m.attachment_name,
                "attachment_type": m.attachment_type,
                "is_read": m.is_read_by_recipient,
                "created_at": m.created_at.isoformat(),
            })

        id_verifications = []
        for v in ticket.identity_verifications:
            id_verifications.append({
                "id": v.id,
                "verification_id": v.external_id,
                "document_type": v.document_type,
                "national_id_number": v.national_id_number,
                "document_front_url": v.document_front_url,
                "document_back_url": v.document_back_url,
                "verification_status": v.verification_status,
                "reviewer_notes": v.reviewer_notes,
                "reviewed_at": v.reviewed_at.isoformat() if v.reviewed_at else None,
                "created_at": v.created_at.isoformat(),
            })

        latest_idv = ticket.identity_verifications[-1] if ticket.identity_verifications else None

        return {
            "id": ticket.id,
            "ticket_id": ticket.external_id,
            "ticket_number": ticket.external_id,
            "customer_id": ticket.customer_id,
            "customer_name": ticket.customer.name if ticket.customer else "Customer",
            "customer_email": ticket.customer.email if ticket.customer else "",
            "omerta_user_number": ticket.customer.omerta_user_number if ticket.customer else "",
            "national_id_number": ticket.customer.national_id_number if ticket.customer else None,
            "transfer_blocked": (ticket.customer.transfer_status == "BLOCKED" if ticket.customer else False) or (ticket.issue_type == "TRANSFER_BLOCKED"),
            "identity_status": ticket.customer.identity_status if ticket.customer else "NOT_VERIFIED",
            "identity_verification_id": latest_idv.id if latest_idv else None,
            "identity_verification": {
                "id": latest_idv.id,
                "verification_id": latest_idv.external_id,
                "document_type": latest_idv.document_type,
                "national_id_number": latest_idv.national_id_number,
                "document_front_url": latest_idv.document_front_url,
                "document_back_url": latest_idv.document_back_url,
                "status": latest_idv.verification_status,
                "reviewer_notes": latest_idv.reviewer_notes,
                "reviewed_at": latest_idv.reviewed_at.isoformat() if latest_idv.reviewed_at else None,
            } if latest_idv else None,
            "customer": {
                "id": ticket.customer.external_id if ticket.customer else None,
                "name": ticket.customer.name if ticket.customer else "Customer",
                "omerta_user_number": ticket.customer.omerta_user_number if ticket.customer else None,
                "email": ticket.customer.email if ticket.customer else None,
                "phone": ticket.customer.phone if ticket.customer else None,
                "transfer_status": ticket.customer.transfer_status if ticket.customer else "ACTIVE",
                "identity_status": ticket.customer.identity_status if ticket.customer else "NOT_VERIFIED",
                "national_id_number": ticket.customer.national_id_number if ticket.customer else None,
                "require_transfer_password_change": ticket.customer.require_transfer_password_change if ticket.customer else False,
            },
            "issue_type": ticket.issue_type,
            "priority": ticket.priority,
            "status": ticket.status,
            "subject": ticket.subject,
            "description": ticket.description,
            "context_data": ticket.context_data,
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "messages": messages,
            "identity_verifications": id_verifications,
        }


@router.post("/tickets/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_ticket_message(
    ticket_id: str,
    body: SendMessageRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Send a message within a support ticket (supports Customer, Admin, Analyst, Auditor)."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket = await session.scalar(
            select(SupportTicket).options(selectinload(SupportTicket.customer)).where(_ticket_condition(ticket_id))
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        user_role = current_user.get("role", "CUSTOMER")
        user_name = current_user.get("full_name") or current_user.get("username", "User")
        sender_user_id = None

        if user_role == "CUSTOMER":
            cust_service = CustomerService(session)
            customer = await cust_service.get_customer_by_user_id(current_user["sub"])
            if not customer or ticket.customer_id != customer.id:
                raise HTTPException(status_code=403, detail="Access denied to this support ticket.")
            sender_name = customer.name
            sender_role = "CUSTOMER"
            sender_user_id = customer.user_id
            # Update ticket status to WAITING_FOR_ADMIN / IN_REVIEW
            if ticket.status in ("RESOLVED", "WAITING_FOR_CUSTOMER", "OPEN"):
                ticket.status = "IN_REVIEW"
        else:
            sender_name = f"{user_name} ({user_role.replace('_', ' ').title()})"
            sender_role = user_role
            # Update ticket status to WAITING_FOR_CUSTOMER
            ticket.status = "WAITING_FOR_CUSTOMER"

        msg = SupportMessage(
            external_id=f"MSG-{secrets.token_hex(4).upper()}",
            ticket_id=ticket.id,
            sender_user_id=sender_user_id,
            sender_role=sender_role,
            sender_name=sender_name,
            message_text=body.message_text.strip(),
            attachment_url=body.attachment_url,
            attachment_name=body.attachment_name,
            attachment_type=body.attachment_type,
        )
        session.add(msg)
        ticket.updated_at = datetime.now(UTC)

        session.add(
            AuditEvent(
                event_id=f"EVT-MSG-{secrets.token_hex(4).upper()}",
                event_type="SUPPORT_MESSAGE_SENT",
                actor_type=sender_role,
                actor_id=str(current_user.get("sub", "")),
                source="SupportService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "sender_role": sender_role,
                    "has_attachment": bool(body.attachment_url),
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "message_id": msg.external_id,
            "sender_name": msg.sender_name,
            "sender_role": msg.sender_role,
            "message_text": msg.message_text,
            "created_at": msg.created_at.isoformat(),
        }


@router.post("/tickets/{ticket_id}/upload-id", status_code=status.HTTP_201_CREATED)
async def upload_national_id_document(
    ticket_id: str,
    body: UploadIdDocumentRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload National ID document image/screenshot for human review."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket = await session.scalar(
            select(SupportTicket).options(selectinload(SupportTicket.customer)).where(_ticket_condition(ticket_id))
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        cust_service = CustomerService(session)
        customer = await cust_service.get_customer_by_user_id(current_user["sub"])
        if not customer or ticket.customer_id != customer.id:
            raise HTTPException(status_code=403, detail="Access denied to this support ticket.")

        # Update customer profile identity status to PENDING_REVIEW
        customer.national_id_number = body.national_id_number.strip()
        customer.identity_status = "PENDING_REVIEW"
        ticket.status = "IN_REVIEW"

        # Create IdentityVerification record
        idv_ext_id = f"IDV-{secrets.token_hex(4).upper()}"
        idv = IdentityVerification(
            external_id=idv_ext_id,
            customer_id=customer.id,
            ticket_id=ticket.id,
            national_id_number=body.national_id_number.strip(),
            document_type=body.document_type,
            document_front_url=body.document_front_url,
            document_back_url=body.document_back_url,
            verification_status="PENDING_REVIEW",
        )
        session.add(idv)

        # Add message to support conversation
        msg = SupportMessage(
            external_id=f"MSG-{secrets.token_hex(4).upper()}",
            ticket_id=ticket.id,
            sender_user_id=customer.user_id,
            sender_role="CUSTOMER",
            sender_name=customer.name,
            message_text="📄 [Identity Documents Uploaded] Front and back National ID / Passport photos submitted for compliance review.",
            attachment_url=body.document_front_url,
            attachment_name=f"national_id_{customer.external_id}.png",
            attachment_type="IMAGE",
        )
        session.add(msg)

        # Audit Event
        session.add(
            AuditEvent(
                event_id=f"EVT-IDV-{secrets.token_hex(4).upper()}",
                event_type="IDENTITY_DOCUMENT_UPLOADED",
                actor_type="CUSTOMER",
                actor_id=str(customer.user_id),
                source="IdentityVerificationService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "verification_id": idv_ext_id,
                    "customer_id": customer.external_id,
                    "national_id_number": body.national_id_number.strip(),
                    "document_type": body.document_type,
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "verification_id": idv_ext_id,
            "status": "PENDING",
            "identity_status": "PENDING_REVIEW",
            "message": "National ID document successfully uploaded for compliance verification.",
        }


# ==============================================================================
# Staff (Admin / Auditor) Endpoints
# ==============================================================================

@router.get("/admin/cases")
async def list_admin_support_cases(
    status_filter: str | None = Query(default=None, alias="status"),
    issue_type: str | None = None,
    priority: str | None = None,
    search: str | None = None,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> list[dict[str, Any]]:
    """List support & security cases with rich operational filtering for Admins and Auditors."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        stmt = (
            select(SupportTicket)
            .options(
                selectinload(SupportTicket.customer),
                selectinload(SupportTicket.messages),
                selectinload(SupportTicket.identity_verifications),
            )
            .order_by(desc(SupportTicket.updated_at))
        )

        if status_filter:
            stmt = stmt.where(SupportTicket.status == status_filter)
        if issue_type:
            stmt = stmt.where(SupportTicket.issue_type == issue_type)
        if priority:
            stmt = stmt.where(SupportTicket.priority == priority)

        tickets = (await session.scalars(stmt)).all()

        results = []
        for t in tickets:
            if search:
                s = search.lower()
                matches = (
                    s in t.external_id.lower()
                    or s in t.subject.lower()
                    or (t.customer and (s in t.customer.name.lower() or s in t.customer.omerta_user_number.lower() or (t.customer.national_id_number and s in t.customer.national_id_number.lower())))
                )
                if not matches:
                    continue

            last_msg = t.messages[-1] if t.messages else None
            pending_id = any(v.verification_status == "PENDING_REVIEW" for v in t.identity_verifications)
            is_transfer_blocked = (t.customer.transfer_status == "BLOCKED" if t.customer else False) or (t.issue_type == "TRANSFER_BLOCKED")
            id_status = t.customer.identity_status if t.customer else "NOT_VERIFIED"
            if pending_id:
                id_status = "PENDING"
            latest_idv = t.identity_verifications[-1] if t.identity_verifications else None

            results.append({
                "id": t.id,
                "ticket_id": t.external_id,
                "ticket_number": t.external_id,
                "customer_name": t.customer.name if t.customer else "Customer",
                "customer_email": t.customer.email if t.customer else "",
                "omerta_user_number": t.customer.omerta_user_number if t.customer else "",
                "national_id_number": t.customer.national_id_number if t.customer else "",
                "transfer_blocked": is_transfer_blocked,
                "identity_status": id_status,
                "identity_verification_id": latest_idv.id if latest_idv else None,
                "identity_verification": {
                    "id": latest_idv.id,
                    "verification_id": latest_idv.external_id,
                    "document_type": latest_idv.document_type,
                    "national_id_number": latest_idv.national_id_number,
                    "document_front_url": latest_idv.document_front_url,
                    "document_back_url": latest_idv.document_back_url,
                    "status": latest_idv.verification_status,
                    "reviewer_notes": latest_idv.reviewer_notes,
                } if latest_idv else None,
                "customer": {
                    "id": t.customer.external_id if t.customer else None,
                    "name": t.customer.name if t.customer else "Unknown",
                    "omerta_user_number": t.customer.omerta_user_number if t.customer else None,
                    "email": t.customer.email if t.customer else None,
                    "phone": t.customer.phone if t.customer else None,
                    "transfer_status": t.customer.transfer_status if t.customer else "ACTIVE",
                    "identity_status": t.customer.identity_status if t.customer else "NOT_VERIFIED",
                    "national_id_number": t.customer.national_id_number if t.customer else None,
                    "failed_attempts": t.customer.transfer_failed_attempts if t.customer else 0,
                },
                "issue_type": t.issue_type,
                "priority": t.priority,
                "status": t.status,
                "subject": t.subject,
                "description": t.description,
                "has_pending_id_verification": pending_id,
                "messages_count": len(t.messages),
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
                "last_message": {
                    "sender_name": last_msg.sender_name if last_msg else None,
                    "sender_role": last_msg.sender_role if last_msg else None,
                    "text": last_msg.message_text if last_msg else t.description,
                    "created_at": last_msg.created_at.isoformat() if last_msg else t.created_at.isoformat(),
                } if last_msg else None,
            })

        return results


@router.get("/admin/cases/{ticket_id}")
async def get_admin_case_detail(
    ticket_id: str,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Admin and Auditor case detail fetch endpoint."""
    return await get_ticket_details(ticket_id, current_user)


@router.post("/admin/cases/{ticket_id}/messages", status_code=status.HTTP_201_CREATED)
async def admin_send_case_message(
    ticket_id: str,
    body: SendMessageRequest,
    current_user: dict[str, Any] = Depends(require_role(ADMIN_AUDITOR_ROLES)),
) -> dict[str, Any]:
    """Admin and Auditor message send endpoint."""
    return await send_ticket_message(ticket_id, body, current_user)


@router.post("/admin/cases/{ticket_id}/verify-identity")
async def review_identity_verification(
    ticket_id: str,
    body: VerifyIdentityDecisionRequest,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR", "FRAUD_ANALYST", "SENIOR_INVESTIGATOR", "AUDITOR", "COMPLIANCE_AUDITOR"])),
) -> dict[str, Any]:
    """Human compliance review: approve or reject submitted National ID documents."""
    user_role = current_user.get("role", "")
    if user_role in ("AUDITOR", "COMPLIANCE_AUDITOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Audit Admin accounts have observation and messaging responsibility only. Identity verification decisions are reserved for Administrators.",
        )

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket = await session.scalar(
            select(SupportTicket)
            .options(selectinload(SupportTicket.customer), selectinload(SupportTicket.identity_verifications))
            .where(_ticket_condition(ticket_id))
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        customer = ticket.customer
        if not customer:
            raise HTTPException(status_code=404, detail="Associated customer profile not found.")

        # Update latest identity verification record
        latest_idv = ticket.identity_verifications[-1] if ticket.identity_verifications else None
        if latest_idv:
            latest_idv.verification_status = body.decision
            latest_idv.reviewer_notes = body.reviewer_notes
            latest_idv.reviewed_at = datetime.now(UTC)

        customer.identity_status = body.decision

        reviewer_name = current_user.get("full_name") or current_user.get("username", "Staff")

        # Post system message into support conversation
        if body.decision == "VERIFIED":
            status_text = "✅ [Identity Verified] Your National ID has been approved by our compliance team."
        else:
            status_text = f"❌ [Identity Verification Rejected] Reason: {body.reviewer_notes}. Please upload a clearer ID document."

        session.add(
            SupportMessage(
                external_id=f"MSG-{secrets.token_hex(4).upper()}",
                ticket_id=ticket.id,
                sender_role=current_user.get("role", "ADMINISTRATOR"),
                sender_name=f"{reviewer_name} (Compliance)",
                message_text=status_text,
            )
        )

        # Audit Event
        session.add(
            AuditEvent(
                event_id=f"EVT-IDVR-{secrets.token_hex(4).upper()}",
                event_type=f"IDENTITY_VERIFICATION_{body.decision}",
                actor_type=current_user.get("role", "ADMINISTRATOR"),
                actor_id=str(current_user.get("sub", "")),
                source="IdentityVerificationService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "customer_id": customer.external_id,
                    "decision": body.decision,
                    "reviewer": reviewer_name,
                    "notes": body.reviewer_notes,
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "decision": body.decision,
            "status": body.decision,
            "identity_status": customer.identity_status,
            "identity_verification": {
                "status": body.decision,
                "reviewer_notes": body.reviewer_notes,
                "verification_id": latest_idv.external_id if latest_idv else None,
            },
            "message": f"Identity verification successfully marked as {body.decision}.",
        }


@router.post("/admin/cases/{ticket_id}/restore-transfer")
async def restore_customer_transfer_access(
    ticket_id: str,
    body: RestoreTransferAccessRequest,
    current_user: dict[str, Any] = Depends(require_role(["ADMINISTRATOR", "SENIOR_INVESTIGATOR"])),
) -> dict[str, Any]:
    """Restore transfer functionality for a customer, unblock transfer operations, and require password change."""
    if not body.confirmation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation is required to restore transfer access.",
        )

    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        ticket = await session.scalar(
            select(SupportTicket)
            .options(selectinload(SupportTicket.customer))
            .where(_ticket_condition(ticket_id))
        )
        if not ticket:
            raise HTTPException(status_code=404, detail="Support ticket not found.")

        customer = ticket.customer
        if not customer:
            raise HTTPException(status_code=404, detail="Associated customer profile not found.")

        # Restore transfer access
        customer.transfer_status = "ACTIVE"
        customer.transfer_failed_attempts = 0
        customer.transfer_unblocked_at = datetime.now(UTC)
        customer.require_transfer_password_change = True
        ticket.status = "RESOLVED"
        ticket.resolved_at = datetime.now(UTC)

        admin_name = current_user.get("full_name") or current_user.get("username", "Administrator")

        # Post resolution message to support conversation
        resolution_msg = (
            f"🔓 [Transfer Access Restored] Your transfer services have been restored by {admin_name}. "
            f"For your security, you are now required to set a NEW Transfer Password on your dashboard."
        )
        session.add(
            SupportMessage(
                external_id=f"MSG-{secrets.token_hex(4).upper()}",
                ticket_id=ticket.id,
                sender_role="ADMINISTRATOR",
                sender_name=f"{admin_name} (Administrator)",
                message_text=resolution_msg,
            )
        )

        # Audit Event
        session.add(
            AuditEvent(
                event_id=f"EVT-RESTORE-{secrets.token_hex(4).upper()}",
                event_type="TRANSFER_SERVICES_RESTORED",
                actor_type="ADMINISTRATOR",
                actor_id=str(current_user.get("sub", "")),
                source="AdminSupportService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "customer_id": customer.external_id,
                    "omerta_user_number": customer.omerta_user_number,
                    "admin_name": admin_name,
                    "reason": body.reason,
                    "transfer_status": "ACTIVE",
                    "require_password_change": True,
                },
            )
        )
        await session.commit()

        return {
            "success": True,
            "message": "Transfer access successfully restored. Customer will be prompted to create a new transfer password.",
            "status": "RESOLVED",
            "ticket_status": "RESOLVED",
            "transfer_status": "ACTIVE",
            "require_transfer_password_change": True,
        }
