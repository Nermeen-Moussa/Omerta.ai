# Omerta.ai — Customer Ticket, Security Case & Escalation Architecture

## 1. Executive Summary

Omerta.ai provides an enterprise-grade Customer Support, Security Case, Identity Verification, and Privilege Resolution system. It separates **Support Ticket Resolution** (customer service completion) from **Transfer Restriction Restoration** (privileged administrative action that re-enables money transfers).

---

## 2. Core Architecture & Concepts

### 2.1 Separation of Invariants
* **Ticket Resolution $\neq$ Privilege Restoration**: An administrator resolving a dispute or closing an inquiry does NOT automatically restore sending/receiving money. Privilege restoration requires explicit eligibility checks, mandatory reason logging, identity verification validation, and tier-based role authorization.
* **Non-Logout 3-Strikes Security Hold**: When a customer fails their transfer password 3 consecutive times, their active session remains valid and they remain logged in. Transfers are blocked (`is_transfer_locked=True`), an automated `TRANSFER_PASSWORD_LOCK` ticket is generated with a deduplication guard, and an audit trail is created.
* **Role-Based Workflows**:
  * `CUSTOMER`: Opens tickets, submits simulated National ID documents, replies to staff, views ticket history and security notices. Cannot view internal risk scores, fraud weights, or admin evidence.
  * `ADMINISTRATOR`: Assigns tickets, requests documents, reviews identity verification, resolves standard tickets, restores privileges up to Tier 3.
  * `FRAUD_ANALYST` / `SENIOR_COMPLIANCE`: Handles escalated tickets (`ACCOUNT_TAKEOVER`, Tier 4+ restorations, `RISK_REVIEW` cases with risk scores $> 40.00$).
  * `AUDITOR`: Read-only message and audit review without modification privileges.

---

## 3. Standard Ticket Types & Policies

The ticket policy engine (`domain/ticket_policy.py`) governs all 16 supported ticket types:

| Machine Code | Human Name | Default Priority | Category | Verification Req | Admin Can Resolve | Admin Can Restore | Escalation Trigger |
|---|---|---|---|---|---|---|---|
| `TRANSFER_PASSWORD_LOCK` | Transfer Password Lockout | `MEDIUM` | `SECURITY` | Yes | Yes | Yes (Tiers 1–3) | $\ge 4$ Restorations |
| `TRANSFER_BLOCKED` | Transfer Privileges Blocked | `HIGH` | `SECURITY` | Yes | Yes | Yes (Tiers 1–3) | High risk score |
| `IDENTITY_VERIFICATION` | Identity Verification Request | `MEDIUM` | `VERIFICATION` | Yes | Yes | No | Fraud signal |
| `NEW_DEVICE` | New Device Recognition | `LOW` | `SECURITY` | No | Yes | No | Unrecognized IP |
| `VPN_LOCATION_ISSUE` | VPN / Anomaly Location Notice | `LOW` | `SECURITY` | No | Yes | No | Geo-velocity |
| `ACCOUNT_ACCESS` | Account Access Inquiry | `MEDIUM` | `ACCOUNT` | No | Yes | No | Lockout |
| `BALANCE_DISPUTE` | Account Balance Dispute | `HIGH` | `BILLING` | No | Yes | No | Amount > $10k |
| `TRANSFER_DISPUTE` | Transaction Dispute | `HIGH` | `TRANSACTION` | No | Yes | No | Fraud suspected |
| `SUSPICIOUS_ACTIVITY` | Suspicious Activity Report | `HIGH` | `SECURITY` | Yes | Yes | No | Analyst required |
| `ACCOUNT_TAKEOVER` | Suspected Account Takeover | `CRITICAL` | `SECURITY` | Yes | No | No | Mandatory Compliance |
| `DOCUMENT_VERIFICATION` | KYC Document Review | `MEDIUM` | `VERIFICATION` | Yes | Yes | No | Expired/Unclear |
| `RISK_REVIEW` | Automated Risk Engine Review | `HIGH` | `RISK` | No | Yes | No | Score $> 40.00$ |
| `ACCOUNT_SUSPENSION_APPEAL`| Account Suspension Appeal | `HIGH` | `COMPLIANCE` | Yes | No | No | Senior Compliance |
| `TRANSACTION_INVESTIGATION`| Forensic Tx Investigation | `HIGH` | `SECURITY` | No | Yes | No | Analyst required |
| `GENERAL_SUPPORT` | General Inquiry | `LOW` | `GENERAL` | No | Yes | No | None |
| `OTHER` | Miscellaneous Support Request | `LOW` | `GENERAL` | No | Yes | No | None |

---

## 4. Ticket Lifecycle & State Transitions

The system enforces valid state transitions in `TicketService`:

```
                 ┌───────────────┐
                 │     OPEN      │
                 └───────┬───────┘
                         │
                         ▼
                 ┌───────────────┐
         ┌───────┤   IN_REVIEW   ├────────┐
         │       └───────┬───────┘        │
         │               │                │
         ▼               ▼                ▼
┌──────────────────┐ ┌───────────────┐ ┌───────────────┐
│ WAITING_CUSTOMER │ │ WAITING_DOC   │ │   ESCALATED   │
└────────┬─────────┘ └───────┬───────┘ └───────┬───────┘
         │                   │                 │
         └─────────► ┌───────┴───────┐ ◄───────┘
                     │   IN_REVIEW   │
                     └───────┬───────┘
                             │
                     ┌───────┴───────┐
                     ▼               ▼
             ┌───────────────┐ ┌───────────────┐
             │   RESOLVED    │ │   REJECTED    │
             └───────┬───────┘ └───────┬───────┘
                     │                 │
                     └────────► ┌──────┴───────┐
                                │    CLOSED    │
                                └──────────────┘
```

---

## 5. API Endpoints

### Customer Endpoints (`/api/v1/customer/tickets`)
* `POST /api/v1/customer/tickets`: Create a new ticket with owned `related_account_id` or `related_transaction_id`.
* `GET /api/v1/customer/tickets`: List current user's tickets with status, verification, and unread counts.
* `GET /api/v1/customer/tickets/{ticket_id}`: Retrieve detailed ticket view (strict IDOR protection).
* `POST /api/v1/customer/tickets/{ticket_id}/verification`: Submit simulated National ID document and selfie proof.
* `POST /api/v1/customer/tickets/{ticket_id}/messages`: Post a chat message to support.

### Admin Endpoints (`/api/v1/admin/tickets`)
* `GET /api/v1/admin/tickets`: Paginated ticket index with multi-dimensional filtering.
* `GET /api/v1/admin/tickets/stats`: Aggregate dashboard KPIs (open, critical, locks, restorations, escalated).
* `GET /api/v1/admin/tickets/{ticket_id}`: Comprehensive staff detail view with audit timeline, restoration history, IDV state, and risk intelligence.
* `POST /api/v1/admin/tickets/{ticket_id}/assign`: Assign administrator or fraud analyst.
* `POST /api/v1/admin/tickets/{ticket_id}/request-document`: Transition ticket to `WAITING_FOR_DOCUMENT`.
* `POST /api/v1/admin/tickets/{ticket_id}/verify`: Approve submitted simulated identity document.
* `POST /api/v1/admin/tickets/{ticket_id}/reject-verification`: Reject submitted identity verification.
* `POST /api/v1/admin/tickets/{ticket_id}/restore-transfer`: Execute privileged transfer privilege restoration with audit logging.
* `POST /api/v1/admin/tickets/{ticket_id}/resolve`: Resolve ticket without necessarily restoring transfers.
* `POST /api/v1/admin/tickets/{ticket_id}/escalate`: Escalate ticket to Senior Compliance.
* `POST /api/v1/admin/tickets/{ticket_id}/close`: Close resolved/rejected ticket.
