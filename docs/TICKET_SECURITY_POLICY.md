# Omerta.ai — Ticket & Security Resolution Policy

## 1. Security Invariants

1. **Authentication State Separation**:
   * A security hold on financial transfers does **NOT** revoke web or API session tokens.
   * Customers can freely log in, view account balances, review transaction statements, communicate via support chat, and upload identity verification documents.
   * `TRANSFER_SEND_ALLOWED` and `TRANSFER_RECEIVE_ALLOWED` are revoked while `LOGIN_ALLOWED` and `ACCOUNT_ACCESS_ALLOWED` remain active.

2. **Deduplication of Automatic Security Tickets**:
   * Repeated trigger events (e.g. further failed transfer attempts while already locked) do not spawn redundant tickets.
   * `TicketService.create_auto_security_ticket()` checks for existing active tickets matching the customer and category (`SECURITY`), appending an audit event rather than creating duplicates.

3. **Strict IDOR (Insecure Direct Object Reference) Protection**:
   * Customer endpoints extract identity solely from signed JWT claims (`current_user.customer_id`).
   * When attaching `related_account_id` or `related_transaction_id`, the backend verifies database ownership against the customer's owned accounts. Any foreign ID triggers an immediate `HTTP 403 / 404` error.

---

## 2. Progressive 4-Tier Restoration Policy

To prevent abuse and mitigate recurring social engineering or compromise patterns, transfer restoration follows a progressive tier policy:

| Restoration Index | Policy Requirement | Permitted Roles | Additional Validation |
|---|---|---|---|
| **Tier 1 (1st Restoration)** | Standard Restoration | `ADMINISTRATOR`, `FRAUD_ANALYST` | Verified Identity (`VERIFIED`) |
| **Tier 2 (2nd Restoration)** | Enhanced Audit Review | `ADMINISTRATOR`, `FRAUD_ANALYST` | Verified Identity + Reason Audit Trail |
| **Tier 3 (3rd Restoration)** | Explicit Compliance Review | `ADMINISTRATOR`, `FRAUD_ANALYST` | Verified Identity + Historical Review |
| **Tier 4+ ($\ge 4$ Restorations)** | **Strict Escalation Required** | `SENIOR_COMPLIANCE` only | Standard Admin **DENIED** (`requires_senior_compliance=True`). Mandatory manual compliance review. |

### Restoration Execution Rules:
* Action requires non-empty `reason` string (trimmed).
* Verifies `ticket.ticket_type` permits privilege restoration (e.g. `TRANSFER_PASSWORD_LOCK`, `TRANSFER_BLOCKED`).
* Validates `identity_verification_status == 'VERIFIED'`.
* Restores customer `is_transfer_locked = False`, `transfer_password_failures = 0`.
* Writes an immutable record to `transfer_restorations` with actor details, previous state (`BLOCKED`), and new state (`ACTIVE`).
* Emits a system `AUDIT_LOG` event (`TRANSFER_PRIVILEGES_RESTORED`).

---

## 3. Account Takeover & Fraud Protocols

### 3.1 Account Takeover (`ACCOUNT_TAKEOVER`)
* **Priority**: `CRITICAL`
* **Resolution**: Standard administrators cannot resolve without compliance elevation.
* **Privileges**: Never restored via normal quick-actions.
* **Customer Facing**: Generic, secure notice without revealing internal fraud scores or attribution markers.

### 3.2 Risk Engine Integration (`RISK_REVIEW`)
* Triggered when transaction fraud scoring evaluates to `risk_score > 40.00`.
* Creates a `RISK_REVIEW` ticket linked to `related_transaction_id` and `related_risk_assessment_id`.
* Displays full telemetry to analysts: device fingerprint, emulator detection, VPN presence, and behavioral anomalies.
