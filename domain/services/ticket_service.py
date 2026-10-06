"""TicketService: Domain Service for Customer Tickets, Security Cases, and Restriction Restorations.

Implements:
1. End-to-end ticket lifecycle with strict state machine validation.
2. 3-Strikes automatic non-logout security hold and ticket generation.
3. Strict separation between Ticket Resolution and Restriction Restoration.
4. Progressive 4-tier restoration limits (1st-3rd Admin, 4th+ Senior Compliance).
5. IDOR authorization validation for customer resource attachments.
6. Identity verification workflows and immutable restoration ledger.
7. Full audit trail emission for governance compliance.
"""

from datetime import UTC, datetime
import secrets
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.ticket_policy import (
    MAX_STANDARD_ADMIN_RESTORATIONS,
    IdentityVerificationStatus,
    TicketPriority,
    TicketStatus,
    TicketType,
    check_restoration_eligibility,
    get_ticket_policy,
    validate_status_transition,
)
from infrastructure.database.models import (
    Account,
    AuditEvent,
    Customer,
    IdentityVerification,
    SupportMessage,
    SupportTicket,
    Transfer,
    TransferRestoration,
    User,
)


class TicketService:
    """Enterprise domain service governing tickets, cases, identity verification, and restoration policies."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _generate_ticket_number(self) -> str:
        """Generate human-readable unique ticket identifier (e.g. OMR-TKT-7F2A-8C)."""
        hex_part1 = secrets.token_hex(2).upper()
        hex_part2 = secrets.token_hex(2).upper()
        return f"OMR-TKT-{hex_part1}-{hex_part2}"

    async def get_customer_restoration_count(self, customer_id: int) -> int:
        """Query total historical transfer privilege restorations for a customer."""
        stmt = select(func.count(TransferRestoration.id)).where(TransferRestoration.customer_id == customer_id)
        count = await self.session.scalar(stmt)
        return count or 0

    async def create_ticket(
        self,
        customer: Customer,
        title: str,
        description: str,
        ticket_type: str = "GENERAL_SUPPORT",
        related_transaction_id: int | None = None,
        related_account_id: int | None = None,
        related_risk_assessment_id: str | None = None,
        priority_override: str | None = None,
        client_ip: str = "127.0.0.1",
        opened_by: str = "CUSTOMER",
    ) -> SupportTicket:
        """Create a new support or security ticket with strict IDOR ownership checks."""
        # 1. Resolve policy
        policy = get_ticket_policy(ticket_type)
        effective_priority = priority_override or policy.default_priority.value

        # 2. IDOR Validation: verify related_account_id belongs to this customer
        account_pk = None
        if related_account_id:
            s_acc = str(related_account_id)
            acc_cond = or_(Account.id == int(s_acc), Account.external_id == s_acc) if s_acc.isdigit() else Account.external_id == s_acc
            acc = await self.session.scalar(
                select(Account).where(acc_cond, Account.customer_id == customer.id)
            )
            if not acc:
                raise ValueError("Access Denied: Specified account does not belong to your customer profile.")
            account_pk = acc.id

        # 3. IDOR Validation: verify related_transaction_id belongs to this customer
        tx_pk = None
        if related_transaction_id:
            s_tx = str(related_transaction_id)
            tx_cond = or_(Transfer.id == int(s_tx), Transfer.external_id == s_tx) if s_tx.isdigit() else Transfer.external_id == s_tx
            tx = await self.session.scalar(
                select(Transfer).where(
                    tx_cond,
                    or_(
                        Transfer.sender_customer_id == customer.id,
                        Transfer.recipient_customer_id == customer.id,
                    ),
                )
            )
            if not tx:
                raise ValueError("Access Denied: Specified transaction does not belong to your customer profile.")
            tx_pk = tx.id

        # 4. Check One Active Security Ticket Policy for automated locks
        if policy.code == TicketType.TRANSFER_PASSWORD_LOCK or policy.code == TicketType.TRANSFER_BLOCKED:
            active_ticket = await self.session.scalar(
                select(SupportTicket).where(
                    SupportTicket.customer_id == customer.id,
                    SupportTicket.ticket_type.in_([TicketType.TRANSFER_PASSWORD_LOCK.value, TicketType.TRANSFER_BLOCKED.value]),
                    SupportTicket.status.in_([TicketStatus.OPEN.value, TicketStatus.IN_REVIEW.value, TicketStatus.WAITING_FOR_DOCUMENT.value]),
                )
            )
            if active_ticket:
                # Attach note to existing active ticket rather than creating duplicates
                msg = SupportMessage(
                    external_id=f"MSG-{secrets.token_hex(4).upper()}",
                    ticket_id=active_ticket.id,
                    sender_user_id=customer.user_id,
                    sender_role="CUSTOMER",
                    sender_name=customer.name,
                    message_text=f"📌 [Follow-up Event] {title}: {description}",
                )
                self.session.add(msg)
                active_ticket.updated_at = datetime.now(UTC)
                await self.session.flush()
                return active_ticket

        # 5. Get current restoration count
        restoration_count = await self.get_customer_restoration_count(customer.id)
        ticket_number = self._generate_ticket_number()

        # 6. Create SupportTicket entity
        ticket = SupportTicket(
            external_id=ticket_number,
            customer_id=customer.id,
            account_id=account_pk,
            ticket_type=policy.code.value,
            category=policy.category,
            priority=effective_priority,
            status=TicketStatus.OPEN.value,
            title=title.strip(),
            subject=title.strip(),
            description=description.strip(),
            customer_message=description.strip(),
            opened_by=opened_by,
            requires_identity_verification=policy.requires_identity_verification,
            identity_verification_status=(
                IdentityVerificationStatus.PENDING.value
                if policy.requires_identity_verification
                else IdentityVerificationStatus.NOT_REQUIRED.value
            ),
            requires_compliance_review=policy.requires_compliance_escalation,
            escalated_to_compliance=policy.requires_compliance_escalation,
            related_transaction_id=tx_pk,
            related_account_id=account_pk,
            related_risk_assessment_id=related_risk_assessment_id,
            customer_restoration_count_at_creation=restoration_count,
            context_data={
                "client_ip": client_ip,
                "omerta_user_number": customer.omerta_user_number,
                "transfer_status": customer.transfer_status,
                "failed_attempts": customer.transfer_failed_attempts,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        self.session.add(ticket)
        await self.session.flush()

        # 7. Add initial message
        initial_msg = SupportMessage(
            external_id=f"MSG-{secrets.token_hex(4).upper()}",
            ticket_id=ticket.id,
            sender_user_id=customer.user_id if opened_by == "CUSTOMER" else None,
            sender_role="CUSTOMER" if opened_by == "CUSTOMER" else "SYSTEM",
            sender_name=customer.name if opened_by == "CUSTOMER" else "Omerta Active Defense",
            message_text=description.strip(),
        )
        self.session.add(initial_msg)

        # 8. Create immutable Audit Event
        self.session.add(
            AuditEvent(
                event_id=f"EVT-TKT-{secrets.token_hex(4).upper()}",
                event_type="TICKET_CREATED",
                actor_type=opened_by,
                actor_id=str(customer.user_id or customer.id),
                source="TicketService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "ticket_type": ticket.ticket_type,
                    "priority": ticket.priority,
                    "customer_id": customer.external_id,
                    "requires_idv": policy.requires_identity_verification,
                },
            )
        )
        await self.session.flush()
        loaded = await self.get_ticket_by_identifier(ticket.id)
        return loaded or ticket

    async def create_auto_security_ticket(
        self,
        customer_id: int,
        reason: str = "3_CONSECUTIVE_TRANSFER_PASSWORD_FAILURES",
        event_type: str = "TRANSFER_PASSWORD_LOCK",
        client_ip: str = "127.0.0.1",
    ) -> SupportTicket:
        """Automatically create a TRANSFER_PASSWORD_LOCK security ticket upon 3 failed password attempts.

        Enforces non-logout security hold:
        - Customer login/session remains active.
        - Sending/receiving money transfer operations are locked.
        - Deduplicates if active ticket already exists.
        """
        customer = await self.session.scalar(select(Customer).where(Customer.id == customer_id))
        if not customer:
            raise ValueError(f"Customer {customer_id} not found.")

        # Ensure transfer status is marked BLOCKED
        customer.transfer_status = "BLOCKED"
        customer.transfer_blocked_at = datetime.now(UTC)

        title = "Transfer Password Blocked — Security Hold"
        desc_text = (
            f"Transfer capabilities suspended following 3 consecutive incorrect transfer-password attempts "
            f"({reason}). Account access remains secure. Please submit National ID verification to restore transfer privileges."
        )

        ticket = await self.create_ticket(
            customer=customer,
            title=title,
            description=desc_text,
            ticket_type=TicketType.TRANSFER_PASSWORD_LOCK.value,
            priority_override=TicketPriority.HIGH.value,
            client_ip=client_ip,
            opened_by="SYSTEM",
        )

        # Emit audit event for transfer privileges blocked
        self.session.add(
            AuditEvent(
                event_id=f"EVT-LCK-{secrets.token_hex(4).upper()}",
                event_type="TRANSFER_PRIVILEGES_BLOCKED",
                actor_type="SYSTEM",
                actor_id="SecurityEngine",
                source="TicketService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "customer_id": customer.external_id,
                    "reason": reason,
                    "failed_attempts": customer.transfer_failed_attempts,
                },
            )
        )
        await self.session.flush()
        return ticket

    async def get_ticket_by_identifier(
        self,
        identifier: str | int,
        customer_id: int | None = None,
    ) -> SupportTicket | None:
        """Retrieve a ticket by integer ID or external string ID with optional customer isolation."""
        s = str(identifier)
        condition = or_(SupportTicket.id == int(s), SupportTicket.external_id == s) if s.isdigit() else SupportTicket.external_id == s

        stmt = (
            select(SupportTicket)
            .options(
                selectinload(SupportTicket.customer),
                selectinload(SupportTicket.messages),
                selectinload(SupportTicket.identity_verifications),
                selectinload(SupportTicket.transfer_restorations),
                selectinload(SupportTicket.account),
            )
            .where(condition)
        )

        ticket = await self.session.scalar(stmt)
        if not ticket:
            return None

        if customer_id is not None and ticket.customer_id != customer_id:
            raise PermissionError("Access Denied: You do not have permission to view this ticket.")

        return ticket

    async def list_customer_tickets(
        self,
        customer_id: int,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SupportTicket], int]:
        """Fetch paginated customer tickets safe from internal risk telemetry leakage."""
        stmt = (
            select(SupportTicket)
            .options(
                selectinload(SupportTicket.messages),
                selectinload(SupportTicket.identity_verifications),
            )
            .where(SupportTicket.customer_id == customer_id)
            .order_by(desc(SupportTicket.updated_at))
        )

        if status_filter:
            stmt = stmt.where(SupportTicket.status == status_filter)

        count_stmt = select(func.count(SupportTicket.id)).where(SupportTicket.customer_id == customer_id)
        if status_filter:
            count_stmt = count_stmt.where(SupportTicket.status == status_filter)

        total = await self.session.scalar(count_stmt) or 0
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        tickets = (await self.session.scalars(stmt)).all()
        return list(tickets), total

    async def list_admin_tickets(
        self,
        status_filter: str | None = None,
        ticket_type: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        restoration_required: bool | None = None,
        escalated: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[SupportTicket], int]:
        """Fetch paginated operational support & security cases for administrative staff."""
        stmt = (
            select(SupportTicket)
            .options(
                selectinload(SupportTicket.customer),
                selectinload(SupportTicket.messages),
                selectinload(SupportTicket.identity_verifications),
                selectinload(SupportTicket.transfer_restorations),
            )
            .order_by(desc(SupportTicket.updated_at))
        )

        if status_filter:
            stmt = stmt.where(SupportTicket.status == status_filter)
        if ticket_type:
            stmt = stmt.where(SupportTicket.ticket_type == ticket_type)
        if priority:
            stmt = stmt.where(SupportTicket.priority == priority)
        if escalated is not None:
            stmt = stmt.where(SupportTicket.escalated_to_compliance == escalated)

        tickets = (await self.session.scalars(stmt)).all()

        # In-memory search & filter for customer attributes
        filtered = []
        for t in tickets:
            if search:
                s = search.lower()
                matches = (
                    s in t.external_id.lower()
                    or (t.title and s in t.title.lower())
                    or (t.subject and s in t.subject.lower())
                    or (t.customer and s in t.customer.name.lower())
                    or (t.customer and s in t.customer.omerta_user_number.lower())
                    or (t.customer and t.customer.national_id_number and s in t.customer.national_id_number.lower())
                )
                if not matches:
                    continue

            if restoration_required is not None:
                is_blocked = (t.customer.transfer_status == "BLOCKED" if t.customer else False)
                if restoration_required != is_blocked:
                    continue

            filtered.append(t)

        total = len(filtered)
        offset = (page - 1) * page_size
        paginated = filtered[offset : offset + page_size]
        return paginated, total

    async def get_ticket_stats(self) -> dict[str, Any]:
        """Aggregate high-level metrics and KPIs for the Admin Control Center."""
        all_tickets = (
            await self.session.scalars(
                select(SupportTicket).options(selectinload(SupportTicket.customer))
            )
        ).all()

        open_count = sum(1 for t in all_tickets if t.status == TicketStatus.OPEN.value)
        high_priority = sum(1 for t in all_tickets if t.priority in (TicketPriority.HIGH.value, TicketPriority.CRITICAL.value))
        critical_count = sum(1 for t in all_tickets if t.priority == TicketPriority.CRITICAL.value)
        waiting_customer = sum(1 for t in all_tickets if t.status == TicketStatus.WAITING_FOR_CUSTOMER.value)
        waiting_doc = sum(1 for t in all_tickets if t.status == TicketStatus.WAITING_FOR_DOCUMENT.value or t.identity_verification_status == IdentityVerificationStatus.PENDING.value)
        escalated_count = sum(1 for t in all_tickets if t.status == TicketStatus.ESCALATED.value or t.escalated_to_compliance)
        resolved_count = sum(1 for t in all_tickets if t.status in (TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value))

        security_locks = sum(
            1 for t in all_tickets if t.customer and t.customer.transfer_status == "BLOCKED"
        )
        restorations_total = await self.session.scalar(select(func.count(TransferRestoration.id))) or 0

        return {
            "open_tickets": open_count,
            "high_priority_tickets": high_priority,
            "critical_tickets": critical_count,
            "waiting_for_customer": waiting_customer,
            "waiting_for_documents": waiting_doc,
            "waiting_for_document": waiting_doc,
            "escalated_tickets": escalated_count,
            "resolved_tickets": resolved_count,
            "resolved_today": resolved_count,
            "transfer_security_locks": security_locks,
            "restoration_requests": security_locks,
            "customers_requiring_compliance": escalated_count,
            "total_restorations": restorations_total,
            "total_tickets": len(all_tickets),
            "max_standard_restorations": MAX_STANDARD_ADMIN_RESTORATIONS,
        }

    async def update_ticket_status(
        self,
        ticket: SupportTicket,
        new_status: str,
        actor_id: str,
        actor_role: str,
        reason: str | None = None,
    ) -> SupportTicket:
        """Update ticket status with strict state machine validation and audit logging."""
        if not validate_status_transition(ticket.status, new_status):
            raise ValueError(f"Invalid status transition from {ticket.status} to {new_status}.")

        old_status = ticket.status
        ticket.status = new_status
        ticket.updated_at = datetime.now(UTC)

        if new_status == TicketStatus.RESOLVED.value:
            ticket.resolved_at = datetime.now(UTC)
            if reason:
                ticket.resolution_reason = reason
        elif new_status == TicketStatus.CLOSED.value:
            ticket.closed_at = datetime.now(UTC)

        self.session.add(
            AuditEvent(
                event_id=f"EVT-STS-{secrets.token_hex(4).upper()}",
                event_type="TICKET_STATUS_CHANGED",
                actor_type=actor_role,
                actor_id=str(actor_id),
                source="TicketService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "previous_status": old_status,
                    "new_status": new_status,
                    "reason": reason,
                },
            )
        )
        await self.session.flush()
        return ticket

    async def submit_identity_verification(
        self,
        ticket: SupportTicket,
        customer: Customer,
        national_id_number: str,
        document_type: str = "NATIONAL_ID",
        document_front_url: str = "",
        document_back_url: str | None = None,
    ) -> IdentityVerification:
        """Submit simulated KYC / National ID documents for compliance verification."""
        clean_id = national_id_number.strip()
        customer.national_id_number = clean_id
        customer.identity_status = "PENDING_REVIEW"

        ticket.identity_verification_status = IdentityVerificationStatus.SUBMITTED.value
        ticket.status = TicketStatus.IN_REVIEW.value
        ticket.updated_at = datetime.now(UTC)

        idv_ext_id = f"IDV-{secrets.token_hex(4).upper()}"
        idv = IdentityVerification(
            external_id=idv_ext_id,
            customer_id=customer.id,
            ticket_id=ticket.id,
            national_id_number=clean_id,
            document_type=document_type,
            document_front_url=document_front_url,
            document_back_url=document_back_url,
            verification_status="PENDING_REVIEW",
        )
        self.session.add(idv)

        # Message
        msg = SupportMessage(
            external_id=f"MSG-{secrets.token_hex(4).upper()}",
            ticket_id=ticket.id,
            sender_user_id=customer.user_id,
            sender_role="CUSTOMER",
            sender_name=customer.name,
            message_text=f"📄 [Identity Documents Uploaded] National ID ({clean_id}) front & back submitted for compliance audit.",
            attachment_url=document_front_url,
            attachment_type="IMAGE",
        )
        self.session.add(msg)

        self.session.add(
            AuditEvent(
                event_id=f"EVT-IDV-{secrets.token_hex(4).upper()}",
                event_type="DOCUMENT_SUBMITTED",
                actor_type="CUSTOMER",
                actor_id=str(customer.user_id or customer.id),
                source="TicketService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "verification_id": idv_ext_id,
                    "document_type": document_type,
                },
            )
        )
        await self.session.flush()
        return idv

    async def review_identity_verification(
        self,
        ticket: SupportTicket,
        decision: str,  # VERIFIED | REJECTED
        reviewer_notes: str,
        actor_id: str,
        actor_name: str,
        actor_role: str,
    ) -> IdentityVerification:
        """Human compliance officer reviews submitted identity documents."""
        if actor_role in ("AUDITOR", "COMPLIANCE_AUDITOR"):
            raise PermissionError("Audit Admin accounts have observation and messaging responsibility only. Identity verification decisions are reserved for Administrators.")

        if decision not in ("VERIFIED", "REJECTED"):
            raise ValueError("Decision must be either VERIFIED or REJECTED.")

        latest_idv = ticket.identity_verifications[-1] if ticket.identity_verifications else None
        if latest_idv:
            latest_idv.verification_status = decision
            latest_idv.reviewer_notes = reviewer_notes
            latest_idv.reviewed_at = datetime.now(UTC)

        if ticket.customer:
            ticket.customer.identity_status = decision
        ticket.identity_verification_status = decision
        ticket.updated_at = datetime.now(UTC)

        status_text = (
            f"✅ [Identity Verified] National ID document approved by {actor_name} (Compliance)."
            if decision == "VERIFIED"
            else f"❌ [Identity Verification Rejected] Reason: {reviewer_notes}."
        )

        self.session.add(
            SupportMessage(
                external_id=f"MSG-{secrets.token_hex(4).upper()}",
                ticket_id=ticket.id,
                sender_role=actor_role,
                sender_name=f"{actor_name} (Compliance)",
                message_text=status_text,
            )
        )

        self.session.add(
            AuditEvent(
                event_id=f"EVT-IDVR-{secrets.token_hex(4).upper()}",
                event_type=f"IDENTITY_{decision}",
                actor_type=actor_role,
                actor_id=str(actor_id),
                source="TicketService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "decision": decision,
                    "notes": reviewer_notes,
                },
            )
        )
        await self.session.flush()
        return latest_idv

    async def restore_transfer_privileges(
        self,
        ticket: SupportTicket,
        reason: str,
        actor_id: str,
        actor_name: str,
        actor_role: str,
        confirmation: bool,
    ) -> TransferRestoration:
        """Restore customer transfer privileges under the progressive 4-tier security policy.

        CRITICAL BUSINESS RULE:
        Restoration is a SEPARATE operation from Ticket Resolution.
        Restoration resets transfer restrictions without requiring ticket closure.
        """
        if not confirmation:
            raise ValueError("Explicit confirmation is required to restore transfer privileges.")

        if not reason or not reason.strip():
            raise ValueError("Mandatory restoration reason must be provided.")

        if actor_role in ("AUDITOR", "COMPLIANCE_AUDITOR"):
            raise PermissionError("Audit Admins have observation and messaging responsibility only. Transfer restoration is reserved for Administrators.")

        customer = ticket.customer
        if not customer:
            raise ValueError("Associated customer profile not found.")

        # Check progressive restoration policy eligibility
        past_restorations = await self.get_customer_restoration_count(customer.id)
        eligible, policy_msg = check_restoration_eligibility(past_restorations, actor_role)

        if not eligible:
            # Emit limit reached audit event and escalate ticket
            self.session.add(
                AuditEvent(
                    event_id=f"EVT-RLIM-{secrets.token_hex(4).upper()}",
                    event_type="RESTORATION_LIMIT_REACHED",
                    actor_type=actor_role,
                    actor_id=str(actor_id),
                    source="TicketService",
                    metadata_={
                        "ticket_id": ticket.external_id,
                        "customer_id": customer.external_id,
                        "past_restorations": past_restorations,
                        "error": policy_msg,
                    },
                )
            )
            ticket.escalated_to_compliance = True
            ticket.status = TicketStatus.ESCALATED.value
            await self.session.flush()
            raise PermissionError(policy_msg)

        # Execute restoration
        restoration_number = past_restorations + 1
        previous_state = customer.transfer_status
        customer.transfer_status = "ACTIVE"
        customer.transfer_failed_attempts = 0
        customer.transfer_unblocked_at = datetime.now(UTC)
        customer.require_transfer_password_change = True

        ticket.restoration_approved = True
        ticket.restoration_approved_by = actor_name
        ticket.restoration_approved_at = datetime.now(UTC)
        ticket.updated_at = datetime.now(UTC)

        # Create immutable restoration history entry
        restoration_id = f"RST-{secrets.token_hex(4).upper()}"
        restoration = TransferRestoration(
            external_id=restoration_id,
            customer_id=customer.id,
            ticket_id=ticket.id,
            actor_id=str(actor_id),
            actor_name=actor_name,
            actor_role=actor_role,
            restoration_number=restoration_number,
            previous_state=previous_state,
            new_state="ACTIVE",
            reason=reason.strip(),
            verification_reference=ticket.identity_verifications[-1].external_id if ticket.identity_verifications else None,
        )
        self.session.add(restoration)

        # Post system message into support conversation
        self.session.add(
            SupportMessage(
                external_id=f"MSG-{secrets.token_hex(4).upper()}",
                ticket_id=ticket.id,
                sender_role="SYSTEM",
                sender_name="Compliance & Security",
                message_text=(
                    f"🔓 [Transfer Privileges Restored — Tier #{restoration_number}] Transfer privileges have been restored by {actor_name}. "
                    f"Please set a new transfer password on your next login to begin sending money."
                ),
            )
        )

        # Audit Event
        self.session.add(
            AuditEvent(
                event_id=f"EVT-REST-{secrets.token_hex(4).upper()}",
                event_type="TRANSFER_PRIVILEGES_RESTORED",
                actor_type=actor_role,
                actor_id=str(actor_id),
                source="TicketService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "customer_id": customer.external_id,
                    "restoration_number": restoration_number,
                    "reason": reason.strip(),
                    "policy_tier": f"{restoration_number}/{MAX_STANDARD_ADMIN_RESTORATIONS}",
                },
            )
        )
        await self.session.flush()
        return restoration

    async def resolve_ticket(
        self,
        ticket: SupportTicket,
        resolution_reason: str,
        admin_notes: str | None,
        actor_id: str,
        actor_name: str,
        actor_role: str,
    ) -> SupportTicket:
        """Resolve a support ticket.

        CRITICAL: Resolving a ticket does NOT automatically unblock transfers.
        """
        if not resolution_reason or not resolution_reason.strip():
            raise ValueError("Resolution reason is required.")

        ticket = await self.update_ticket_status(
            ticket=ticket,
            new_status=TicketStatus.RESOLVED.value,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=resolution_reason.strip(),
        )
        ticket.admin_notes = admin_notes.strip() if admin_notes else None

        self.session.add(
            SupportMessage(
                external_id=f"MSG-{secrets.token_hex(4).upper()}",
                ticket_id=ticket.id,
                sender_role=actor_role,
                sender_name=f"{actor_name} (Staff)",
                message_text=f"✅ [Ticket Resolved] {resolution_reason.strip()}",
            )
        )

        self.session.add(
            AuditEvent(
                event_id=f"EVT-RES-{secrets.token_hex(4).upper()}",
                event_type="TICKET_RESOLVED",
                actor_type=actor_role,
                actor_id=str(actor_id),
                source="TicketService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "resolution_reason": resolution_reason.strip(),
                },
            )
        )
        await self.session.flush()
        return ticket

    async def escalate_ticket(
        self,
        ticket: SupportTicket,
        reason: str,
        actor_id: str,
        actor_name: str,
        actor_role: str,
    ) -> SupportTicket:
        """Escalate a ticket to Senior Compliance or Fraud Analyst review."""
        ticket.escalated_to_compliance = True
        ticket.requires_compliance_review = True

        ticket = await self.update_ticket_status(
            ticket=ticket,
            new_status=TicketStatus.ESCALATED.value,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason.strip(),
        )

        self.session.add(
            SupportMessage(
                external_id=f"MSG-{secrets.token_hex(4).upper()}",
                ticket_id=ticket.id,
                sender_role=actor_role,
                sender_name=f"{actor_name} (Compliance)",
                message_text=f"⚠️ [Ticket Escalated] Case escalated for senior compliance/fraud investigation: {reason.strip()}",
            )
        )

        self.session.add(
            AuditEvent(
                event_id=f"EVT-ESC-{secrets.token_hex(4).upper()}",
                event_type="TICKET_ESCALATED",
                actor_type=actor_role,
                actor_id=str(actor_id),
                source="TicketService",
                metadata_={
                    "ticket_id": ticket.external_id,
                    "reason": reason.strip(),
                },
            )
        )
        await self.session.flush()
        return ticket
