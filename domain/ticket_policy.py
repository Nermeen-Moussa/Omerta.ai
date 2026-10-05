"""Centralized Ticket & Security Case Policy Configuration for Omerta.ai.

Defines:
1. All 16 Structured Ticket Types and their operational metadata.
2. Valid Ticket Status Transitions.
3. Identity Verification Lifecycles.
4. Progressive Restriction Restoration Policy & Limits.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TicketType(StrEnum):
    """Supported ticket types across customer support and active defense security workflows."""

    TRANSFER_PASSWORD_LOCK = "TRANSFER_PASSWORD_LOCK"
    TRANSFER_BLOCKED = "TRANSFER_BLOCKED"
    IDENTITY_VERIFICATION = "IDENTITY_VERIFICATION"
    NEW_DEVICE = "NEW_DEVICE"
    VPN_LOCATION_ISSUE = "VPN_LOCATION_ISSUE"
    ACCOUNT_ACCESS = "ACCOUNT_ACCESS"
    BALANCE_DISPUTE = "BALANCE_DISPUTE"
    TRANSFER_DISPUTE = "TRANSFER_DISPUTE"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    ACCOUNT_TAKEOVER = "ACCOUNT_TAKEOVER"
    DOCUMENT_VERIFICATION = "DOCUMENT_VERIFICATION"
    RISK_REVIEW = "RISK_REVIEW"
    ACCOUNT_SUSPENSION_APPEAL = "ACCOUNT_SUSPENSION_APPEAL"
    TRANSACTION_INVESTIGATION = "TRANSACTION_INVESTIGATION"
    GENERAL_SUPPORT = "GENERAL_SUPPORT"
    OTHER = "OTHER"


class TicketStatus(StrEnum):
    """Ticket workflow states."""

    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    WAITING_FOR_DOCUMENT = "WAITING_FOR_DOCUMENT"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    CLOSED = "CLOSED"


class TicketPriority(StrEnum):
    """Ticket triage priority."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IdentityVerificationStatus(StrEnum):
    """Document/KYC verification lifecycle status."""

    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class TicketTypePolicy:
    """Policy constraints and rules for each ticket type."""

    code: TicketType
    name: str
    description: str
    default_priority: TicketPriority
    requires_identity_verification: bool
    allow_admin_resolution: bool
    requires_compliance_escalation: bool
    allow_transfer_restoration: bool
    required_role: str = "ADMINISTRATOR"
    category: str = "SUPPORT"


# Comprehensive Policy Registry for all 16 Ticket Types
TICKET_TYPE_POLICIES: dict[TicketType, TicketTypePolicy] = {
    TicketType.TRANSFER_PASSWORD_LOCK: TicketTypePolicy(
        code=TicketType.TRANSFER_PASSWORD_LOCK,
        name="Transfer Password Lockout (3 Strikes)",
        description="Automatic security hold triggered by 3 consecutive failed transfer-password attempts.",
        default_priority=TicketPriority.MEDIUM,
        requires_identity_verification=True,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=True,
        category="SECURITY",
    ),
    TicketType.TRANSFER_BLOCKED: TicketTypePolicy(
        code=TicketType.TRANSFER_BLOCKED,
        name="Transfer Privileges Blocked",
        description="Customer transfer functionality restricted due to compliance or security hold.",
        default_priority=TicketPriority.HIGH,
        requires_identity_verification=True,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=True,
        category="SECURITY",
    ),
    TicketType.IDENTITY_VERIFICATION: TicketTypePolicy(
        code=TicketType.IDENTITY_VERIFICATION,
        name="Identity Verification (KYC)",
        description="Submission and review of National ID / Passport documents for account tiering.",
        default_priority=TicketPriority.MEDIUM,
        requires_identity_verification=True,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="COMPLIANCE",
    ),
    TicketType.NEW_DEVICE: TicketTypePolicy(
        code=TicketType.NEW_DEVICE,
        name="New Device Authorization",
        description="Inquiry or authorization verification for login from unrecognized hardware or browser.",
        default_priority=TicketPriority.MEDIUM,
        requires_identity_verification=False,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="SECURITY",
    ),
    TicketType.VPN_LOCATION_ISSUE: TicketTypePolicy(
        code=TicketType.VPN_LOCATION_ISSUE,
        name="VPN / Geolocation Policy Exception",
        description="Assistance with proxy/VPN detection, travel notices, or datacenter IP block exemptions.",
        default_priority=TicketPriority.MEDIUM,
        requires_identity_verification=False,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="SECURITY",
    ),
    TicketType.ACCOUNT_ACCESS: TicketTypePolicy(
        code=TicketType.ACCOUNT_ACCESS,
        name="Account Access Recovery",
        description="Assistance with credentials, password recovery, or login multi-factor issues.",
        default_priority=TicketPriority.HIGH,
        requires_identity_verification=True,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="SECURITY",
    ),
    TicketType.BALANCE_DISPUTE: TicketTypePolicy(
        code=TicketType.BALANCE_DISPUTE,
        name="Balance Dispute & Discrepancy",
        description="Inquiry regarding ledger balances, pending deposits, or calculation mismatches.",
        default_priority=TicketPriority.HIGH,
        requires_identity_verification=False,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="TRANSACTIONS",
    ),
    TicketType.TRANSFER_DISPUTE: TicketTypePolicy(
        code=TicketType.TRANSFER_DISPUTE,
        name="Transfer & Payment Dispute",
        description="Dispute over peer-to-peer money movement, incorrect recipient, or unauthorized debit.",
        default_priority=TicketPriority.HIGH,
        requires_identity_verification=False,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="TRANSACTIONS",
    ),
    TicketType.SUSPICIOUS_ACTIVITY: TicketTypePolicy(
        code=TicketType.SUSPICIOUS_ACTIVITY,
        name="Suspicious Activity Report",
        description="Customer or system flagged unusual transaction volume, velocities, or strange access.",
        default_priority=TicketPriority.HIGH,
        requires_identity_verification=True,
        allow_admin_resolution=True,
        requires_compliance_escalation=True,
        allow_transfer_restoration=False,
        required_role="FRAUD_ANALYST",
        category="SECURITY",
    ),
    TicketType.ACCOUNT_TAKEOVER: TicketTypePolicy(
        code=TicketType.ACCOUNT_TAKEOVER,
        name="Account Takeover (ATO) Incident",
        description="Critical incident: reported unauthorized access, compromised credentials, or SIM swap.",
        default_priority=TicketPriority.CRITICAL,
        requires_identity_verification=True,
        allow_admin_resolution=False,
        requires_compliance_escalation=True,
        allow_transfer_restoration=False,
        required_role="SENIOR_COMPLIANCE",
        category="SECURITY",
    ),
    TicketType.DOCUMENT_VERIFICATION: TicketTypePolicy(
        code=TicketType.DOCUMENT_VERIFICATION,
        name="Document Verification",
        description="Submission of secondary identification, utility bills, or business ownership proofs.",
        default_priority=TicketPriority.MEDIUM,
        requires_identity_verification=True,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="COMPLIANCE",
    ),
    TicketType.RISK_REVIEW: TicketTypePolicy(
        code=TicketType.RISK_REVIEW,
        name="Risk Engine Review (>40 Score)",
        description="Automated risk score evaluation triggered by risk engine score exceeding threshold.",
        default_priority=TicketPriority.HIGH,
        requires_identity_verification=False,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        required_role="FRAUD_ANALYST",
        category="RISK",
    ),
    TicketType.ACCOUNT_SUSPENSION_APPEAL: TicketTypePolicy(
        code=TicketType.ACCOUNT_SUSPENSION_APPEAL,
        name="Account Suspension Appeal",
        description="Formal appeal of administrative account deactivation or AML block.",
        default_priority=TicketPriority.HIGH,
        requires_identity_verification=True,
        allow_admin_resolution=False,
        requires_compliance_escalation=True,
        allow_transfer_restoration=False,
        required_role="SENIOR_COMPLIANCE",
        category="COMPLIANCE",
    ),
    TicketType.TRANSACTION_INVESTIGATION: TicketTypePolicy(
        code=TicketType.TRANSACTION_INVESTIGATION,
        name="Transaction Investigation",
        description="In-depth audit investigation of wire clearings, counterparty hops, or SAR candidates.",
        default_priority=TicketPriority.HIGH,
        requires_identity_verification=False,
        allow_admin_resolution=True,
        requires_compliance_escalation=True,
        allow_transfer_restoration=False,
        required_role="SENIOR_INVESTIGATOR",
        category="INVESTIGATION",
    ),
    TicketType.GENERAL_SUPPORT: TicketTypePolicy(
        code=TicketType.GENERAL_SUPPORT,
        name="General Support",
        description="General customer service inquiries, guidance, or portal feedback.",
        default_priority=TicketPriority.LOW,
        requires_identity_verification=False,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="SUPPORT",
    ),
    TicketType.OTHER: TicketTypePolicy(
        code=TicketType.OTHER,
        name="Other Inquiries",
        description="Miscellaneous inquiries not covered by other categories.",
        default_priority=TicketPriority.LOW,
        requires_identity_verification=False,
        allow_admin_resolution=True,
        requires_compliance_escalation=False,
        allow_transfer_restoration=False,
        category="SUPPORT",
    ),
}


# Valid Ticket Status Transitions
VALID_STATUS_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {
        TicketStatus.IN_REVIEW,
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.WAITING_FOR_DOCUMENT,
        TicketStatus.ESCALATED,
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
        TicketStatus.CLOSED,
    },
    TicketStatus.IN_REVIEW: {
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.WAITING_FOR_DOCUMENT,
        TicketStatus.ESCALATED,
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
        TicketStatus.CLOSED,
    },
    TicketStatus.WAITING_FOR_CUSTOMER: {
        TicketStatus.IN_REVIEW,
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
        TicketStatus.CLOSED,
    },
    TicketStatus.WAITING_FOR_DOCUMENT: {
        TicketStatus.IN_REVIEW,
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
        TicketStatus.CLOSED,
    },
    TicketStatus.ESCALATED: {
        TicketStatus.IN_REVIEW,
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.WAITING_FOR_DOCUMENT,
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
        TicketStatus.CLOSED,
    },
    TicketStatus.RESOLVED: {
        TicketStatus.CLOSED,
        TicketStatus.IN_REVIEW,  # Reopen if customer replies with new issue
    },
    TicketStatus.REJECTED: {
        TicketStatus.CLOSED,
        TicketStatus.IN_REVIEW,
    },
    TicketStatus.CLOSED: {
        TicketStatus.IN_REVIEW,
    },
}


# Progressive Restriction Restoration Policy Constants
MAX_STANDARD_ADMIN_RESTORATIONS: int = 3


def validate_status_transition(current_status: str | TicketStatus, new_status: str | TicketStatus) -> bool:
    """Validate whether transitioning from current_status to new_status is permitted."""
    try:
        curr_enum = TicketStatus(current_status)
        new_enum = TicketStatus(new_status)
    except ValueError:
        return False

    if curr_enum == new_enum:
        return True

    allowed = VALID_STATUS_TRANSITIONS.get(curr_enum, set())
    return new_enum in allowed


def get_ticket_policy(ticket_type: str | TicketType) -> TicketTypePolicy:
    """Resolve policy for a ticket type with safe fallback to OTHER."""
    try:
        t_enum = TicketType(ticket_type)
        return TICKET_TYPE_POLICIES.get(t_enum, TICKET_TYPE_POLICIES[TicketType.OTHER])
    except ValueError:
        return TICKET_TYPE_POLICIES[TicketType.OTHER]


def check_restoration_eligibility(
    customer_restoration_count: int,
    actor_role: str,
) -> tuple[bool, str]:
    """Evaluate whether an actor can execute a restriction restoration based on progressive policy.

    Restoration #1 -> Standard Admin allowed after required verification.
    Restoration #2 -> Standard Admin allowed after required verification + stronger audit.
    Restoration #3 -> Standard Admin allowed after required verification + explicit compliance review.
    Restoration #4+ -> Ordinary Administrator DENIED! Requires SENIOR_COMPLIANCE.
    """
    next_restoration_number = customer_restoration_count + 1

    if next_restoration_number <= MAX_STANDARD_ADMIN_RESTORATIONS:
        # Standard admin, senior investigator, or compliance officer can restore
        if actor_role in ("ADMINISTRATOR", "SUB_ADMINISTRATOR", "SENIOR_INVESTIGATOR", "SENIOR_COMPLIANCE"):
            return True, f"Restoration #{next_restoration_number} authorized under standard policy (Tier {next_restoration_number}/3)."
        else:
            return False, f"Role {actor_role} is not authorized to restore transfer privileges."

    # 4th and subsequent restorations strictly require Senior Compliance / Executive Review
    if actor_role == "SENIOR_COMPLIANCE" or actor_role == "ADMINISTRATOR_SUPER":
        return True, f"Restoration #{next_restoration_number} authorized under Senior Compliance override."
    else:
        return (
            False,
            f"Restoration limit reached ({MAX_STANDARD_ADMIN_RESTORATIONS} standard restorations exhausted). "
            f"Restoration #{next_restoration_number} requires Senior Compliance escalation and cannot be restored by standard administrator.",
        )
