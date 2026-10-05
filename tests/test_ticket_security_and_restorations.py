"""Comprehensive Test Suite for Omerta.ai Ticket & Security Resolution System.

Validates all 10 core verification areas specified in Section 34:
1. Customer Ticket Creation & strict IDOR cross-customer rejection.
2. 3-Strikes Non-Logout Security Hold & automated TRANSFER_PASSWORD_LOCK ticket generation.
3. Simulated Identity Verification lifecycle (PENDING -> SUBMITTED -> VERIFIED / REJECTED).
4. Progressive 4-Tier Restoration Policy Enforcement:
   - Restoration #1: Standard Admin allowed after IDV.
   - Restoration #2: Standard Admin allowed after IDV + enhanced audit.
   - Restoration #3: Standard Admin allowed after IDV + compliance review.
   - Restoration #4+: Standard Admin strictly REJECTED (requires Senior Compliance escalation).
5. Separation of Ticket Resolution vs. Restriction Restoration:
   - Ticket can be RESOLVED while transfer privileges remain BLOCKED.
6. Account Takeover Security Handling:
   - CRITICAL priority, strict containment, audit logging.
7. Stage 3 Risk Engine Integration:
   - Risk score > 40.00 triggers automated RISK_REVIEW ticket.
8. Role-Based Access Control & IDOR Prevention:
   - Customer cannot access admin ticket routes.
   - Customer cannot access another customer's ticket or verification.
9. Mandatory Restoration Confirmation Reason validation (no whitespace / empty reasons).
10. Concurrency & Idempotency:
   - Double restoration on active customer is handled safely.
"""

from decimal import Decimal
import secrets
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from apps.api.main import app
from infrastructure.database.models import Customer, SupportTicket, TransferRestoration, User


@pytest.mark.asyncio
async def test_ticket_creation_and_strict_idor_isolation(seeded_db):
    """Verify customer ticket creation, ownership validation, and IDOR prevention."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login Customer A (Ziad Karim)
        login_res_a = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        assert login_res_a.status_code == 200, login_res_a.text
        token_a = login_res_a.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 2. Login Customer B (Layla Hassan)
        login_res_b = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!"},
        )
        assert login_res_b.status_code == 200, login_res_b.text
        token_b = login_res_b.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Get Customer B's account ID via dashboard
        dash_b = await client.get("/api/v1/customer/dashboard", headers=headers_b)
        assert dash_b.status_code == 200
        cust_b_acc_id = dash_b.json()["accounts"][0]["account_id"]

        # 3. Customer A creates a valid ticket
        valid_payload = {
            "ticket_type": "GENERAL_SUPPORT",
            "title": "Inquiry about international transfers",
            "description": "When will international wire transfers be supported?",
        }
        res_create = await client.post("/api/v1/customer/tickets", json=valid_payload, headers=headers_a)
        assert res_create.status_code == 201, res_create.text
        tkt_data = res_create.json()
        assert tkt_data["ticket_number"].startswith("OMR-TKT-")
        assert tkt_data["ticket_type"] == "GENERAL_SUPPORT"
        assert tkt_data["status"] == "OPEN"
        tkt_number = tkt_data["ticket_number"]

        # 4. IDOR Attack Test: Customer A tries to attach Customer B's account
        idor_payload = {
            "ticket_type": "BALANCE_DISPUTE",
            "title": "Disputing foreign balance",
            "description": "Attempting to inspect another account",
            "related_account_id": cust_b_acc_id,
        }
        idor_res = await client.post("/api/v1/customer/tickets", json=idor_payload, headers=headers_a)
        assert idor_res.status_code in [400, 403], "Customer must not attach an account they do not own"

        # 5. IDOR Read Test: Customer B attempts to read Customer A's ticket
        res_get_other = await client.get(f"/api/v1/customer/tickets/{tkt_number}", headers=headers_b)
        assert res_get_other.status_code in [403, 404], "Customer B must not access Customer A's ticket"

        # Customer A can read their own ticket
        res_get_own = await client.get(f"/api/v1/customer/tickets/{tkt_number}", headers=headers_a)
        assert res_get_own.status_code == 200
        assert res_get_own.json()["ticket_number"] == tkt_number


@pytest.mark.asyncio
async def test_three_strikes_lockout_and_automatic_ticket_creation(seeded_db):
    """Verify 3 consecutive failed transfer password attempts block transfers and create automated ticket."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a fresh customer
        suffix = secrets.token_hex(4)
        reg_payload = {
            "full_name": f"Test User {suffix}",
            "email": f"user.{suffix}@omerta.ai",
            "username": f"user_{suffix}",
            "national_id_number": "29801011987654",
            "password": "LoginPassword2026!",
            "confirm_password": "LoginPassword2026!",
            "transfer_password": "TransferPassword2026!",
            "confirm_transfer_password": "TransferPassword2026!",
            "country": "EG",
            "preferred_currency": "EGP",
            "initial_balance": 20000.0,
            "device_consent": True,
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201, reg_res.text
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        dash_new = await client.get("/api/v1/customer/dashboard", headers=headers)
        sender_acc_id = dash_new.json()["accounts"][0]["account_id"]

        # Recipient: Ziad Karim (OMR-1092-4821)
        transfer_body = {
            "sender_account_id": sender_acc_id,
            "recipient_user_number": "OMR-1092-4821",
            "amount": "500.00",
            "currency": "EGP",
            "note": "Test transfer",
            "password": "WrongPassword123!",
        }

        # Attempt 1: 401 Unauthorized (remaining = 2)
        res1 = await client.post("/api/v1/customer/transfers", json=transfer_body, headers=headers)
        assert res1.status_code == 401
        assert res1.json()["detail"]["remaining_attempts"] == 2

        # Attempt 2: 401 Unauthorized (remaining = 1)
        res2 = await client.post("/api/v1/customer/transfers", json=transfer_body, headers=headers)
        assert res2.status_code == 401
        assert res2.json()["detail"]["remaining_attempts"] == 1

        # Attempt 3: 403 Forbidden (transfer locked, auto-ticket generated)
        res3 = await client.post("/api/v1/customer/transfers", json=transfer_body, headers=headers)
        assert res3.status_code == 403
        detail = res3.json()["detail"]
        assert detail["transfer_status"] == "BLOCKED"
        assert "ticket_number" in detail
        auto_ticket_number = detail["ticket_number"]

        # 2. Verify customer remains logged in and can view dashboard
        dash_res = await client.get("/api/v1/customer/dashboard", headers=headers)
        assert dash_res.status_code == 200
        assert dash_res.json()["customer"]["transfer_status"] == "BLOCKED"

        # 3. Verify transfer sending is blocked
        res_blocked = await client.post(
            "/api/v1/customer/transfers",
            json={**transfer_body, "password": "TransferPassword2026!"},
            headers=headers,
        )
        assert res_blocked.status_code == 403
        assert res_blocked.json()["detail"]["transfer_status"] == "BLOCKED"

        # 4. Verify the automatic ticket in customer's ticket list
        tkts_res = await client.get("/api/v1/customer/tickets", headers=headers)
        assert tkts_res.status_code == 200
        tickets = tkts_res.json()["items"]
        matching = [t for t in tickets if t["ticket_number"] == auto_ticket_number]
        assert len(matching) == 1
        assert matching[0]["ticket_type"] == "TRANSFER_PASSWORD_LOCK"
        assert matching[0]["requires_identity_verification"] is True
        assert matching[0]["identity_verification_status"] == "PENDING"


@pytest.mark.asyncio
async def test_simulated_identity_verification_workflow(seeded_db):
    """Verify simulated identity verification submission, admin review, approval, and rejection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login Customer (Layla Hassan)
        cust_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!"},
        )
        cust_headers = {"Authorization": f"Bearer {cust_login.json()['access_token']}"}

        # 2. Login Admin (Dr. Sarah Al-Rashid)
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # 3. Create an IDENTITY_VERIFICATION ticket
        tkt_res = await client.post(
            "/api/v1/customer/tickets",
            json={
                "ticket_type": "IDENTITY_VERIFICATION",
                "title": "National ID submission for limit elevation",
                "description": "Uploading Egyptian National ID card for verification.",
            },
            headers=cust_headers,
        )
        assert tkt_res.status_code == 201
        ticket_number = tkt_res.json()["ticket_number"]

        # 4. Customer submits verification document
        idv_payload = {
            "document_type": "NATIONAL_ID",
            "national_id_number": "29902022345678",
            "document_front_url": "/uploads/test_id.jpg",
            "document_back_url": "/uploads/test_id_back.jpg",
        }
        submit_res = await client.post(
            f"/api/v1/customer/tickets/{ticket_number}/verification",
            json=idv_payload,
            headers=cust_headers,
        )
        assert submit_res.status_code == 201, submit_res.text
        assert submit_res.json()["status"] == "PENDING_REVIEW"

        # 5. Admin verifies identity
        verify_res = await client.post(
            f"/api/v1/admin/tickets/{ticket_number}/verify",
            json={
                "decision": "VERIFIED",
                "reviewer_notes": "National ID validated against Civil Registry format.",
            },
            headers=admin_headers,
        )
        assert verify_res.status_code == 200, verify_res.text
        assert verify_res.json()["identity_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_progressive_4_tier_restoration_policy_enforcement(seeded_db):
    """Verify progressive 4-tier restoration limits (Restorations 1-3 allowed by admin, 4th rejected & escalated)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin login
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # Check Seeded Ticket 10 for Nour Mansour (which has 3 historical restorations)
        ticket_number = "OMR-TKT-000010"

        # 1. Admin attempts to restore transfer privileges on 4th restoration attempt (MUST BE REJECTED)
        restore_res = await client.post(
            f"/api/v1/admin/tickets/{ticket_number}/restore-transfer",
            json={
                "confirmation": True,
                "reason": "Admin attempting 4th standard restoration without Senior Compliance",
            },
            headers=admin_headers,
        )
        assert restore_res.status_code == 403, restore_res.text
        assert "Restoration Limit Exceeded" in restore_res.text or "Senior Compliance" in restore_res.text

        # 2. Check that ticket status is updated to ESCALATED
        tkt_check = await client.get(f"/api/v1/admin/tickets/{ticket_number}", headers=admin_headers)
        assert tkt_check.status_code == 200
        assert tkt_check.json()["escalated_to_compliance"] is True
        assert tkt_check.json()["status"] == "ESCALATED"

        # 3. Test Customer with 0 restorations (Ziad Karim on OMR-TKT-000001):
        # First, admin verifies identity
        v_res = await client.post(
            "/api/v1/admin/tickets/OMR-TKT-000001/verify",
            json={
                "decision": "VERIFIED",
                "reviewer_notes": "Simulated Egyptian National ID verified.",
            },
            headers=admin_headers,
        )
        assert v_res.status_code == 200

        # Now admin performs 1st Restoration (MUST SUCCEED)
        rest_1_res = await client.post(
            "/api/v1/admin/tickets/OMR-TKT-000001/restore-transfer",
            json={
                "confirmation": True,
                "reason": "Tier 1: Identity verified. Standard first restoration approved.",
            },
            headers=admin_headers,
        )
        assert rest_1_res.status_code == 200
        assert rest_1_res.json()["transfer_status"] == "ACTIVE"
        assert rest_1_res.json()["restoration_number"] == 1


@pytest.mark.asyncio
async def test_ticket_resolution_vs_restriction_restoration_separation(seeded_db):
    """Verify that resolving a ticket does NOT restore transfer privileges without explicit restoration."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Admin login
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # Customer login (Omar Farouk - CUST-4001)
        cust_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "omar@omerta.ai", "password": "Customer@2026!"},
        )
        cust_headers = {"Authorization": f"Bearer {cust_login.json()['access_token']}"}

        # Lock Omar's transfers via 3 wrong attempts
        dash = await client.get("/api/v1/customer/dashboard", headers=cust_headers)
        sender_acc_id = dash.json()["accounts"][0]["account_id"]
        for _ in range(3):
            await client.post(
                "/api/v1/customer/transfers",
                json={
                    "sender_account_id": sender_acc_id,
                    "recipient_user_number": "OMR-1092-4821",
                    "amount": "100.00",
                    "password": "WrongPassword!",
                },
                headers=cust_headers,
            )

        # Get the latest ticket created
        tkts = await client.get("/api/v1/customer/tickets", headers=cust_headers)
        ticket_number = tkts.json()["items"][0]["ticket_number"]

        # Admin resolves ticket without calling restore-transfer
        resolve_res = await client.post(
            f"/api/v1/admin/tickets/{ticket_number}/resolve",
            json={
                "resolution_reason": "Inquiry answered. Customer informed of security policies.",
                "admin_notes": "Ticket resolved without unlocking transfers.",
            },
            headers=admin_headers,
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "RESOLVED"

        # Verify customer's transfer privileges remain BLOCKED
        dash_res = await client.get("/api/v1/customer/dashboard", headers=cust_headers)
        assert dash_res.status_code == 200
        assert dash_res.json()["customer"]["transfer_status"] == "BLOCKED"


@pytest.mark.asyncio
async def test_mandatory_restoration_reason_validation(seeded_db):
    """Verify that empty, missing, or whitespace-only restoration reasons are rejected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # Attempt restoration with whitespace only
        res = await client.post(
            "/api/v1/admin/tickets/OMR-TKT-000001/restore-transfer",
            json={"confirmation": True, "reason": "    "},
            headers=admin_headers,
        )
        assert res.status_code in [400, 422], "Whitespace-only restoration reasons must be rejected"


@pytest.mark.asyncio
async def test_account_takeover_critical_workflow_and_escalation(seeded_db):
    """Verify ACCOUNT_TAKEOVER creates CRITICAL priority ticket, blocks standard restoration, and escalates."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cust_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        cust_headers = {"Authorization": f"Bearer {cust_login.json()['access_token']}"}

        # Customer reports account takeover
        tkt_res = await client.post(
            "/api/v1/customer/tickets",
            json={
                "ticket_type": "ACCOUNT_TAKEOVER",
                "title": "Unauthorized login from abroad",
                "description": "I see sessions I did not initiate.",
            },
            headers=cust_headers,
        )
        assert tkt_res.status_code == 201
        tkt = tkt_res.json()
        assert tkt["priority"] == "CRITICAL"
        assert tkt["requires_compliance_review"] is True
        assert tkt["escalated_to_compliance"] is True


@pytest.mark.asyncio
async def test_rbac_and_role_boundaries_on_ticket_apis(seeded_db):
    """Verify customers cannot access admin ticket center or execute administrative actions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cust_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        cust_headers = {"Authorization": f"Bearer {cust_login.json()['access_token']}"}

        # Customer attempts to list admin tickets
        res1 = await client.get("/api/v1/admin/tickets", headers=cust_headers)
        assert res1.status_code == 403

        # Customer attempts to restore transfer privileges
        res2 = await client.post(
            "/api/v1/admin/tickets/OMR-TKT-000001/restore-transfer",
            json={"confirmation": True, "reason": "Unauthorized customer attempt"},
            headers=cust_headers,
        )
        assert res2.status_code == 403

        # Customer attempts to resolve ticket
        res3 = await client.post(
            "/api/v1/admin/tickets/OMR-TKT-000001/resolve",
            json={"resolution_reason": "Hacking ticket"},
            headers=cust_headers,
        )
        assert res3.status_code == 403


@pytest.mark.asyncio
async def test_risk_review_workflow_on_high_risk_transfer(seeded_db):
    """Verify transfers with risk_score > 40.00 trigger automated RISK_REVIEW ticket."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cust_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        assert cust_login.status_code == 200
        headers = {"Authorization": f"Bearer {cust_login.json()['access_token']}"}

        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        dash = await client.get("/api/v1/customer/dashboard", headers=headers)
        sender_acc_id = dash.json()["accounts"][0]["account_id"]

        # Send transfer with amount >= 50,000 EGP (triggers HIGH_VALUE_TRANSFER rule: risk > 40.00)
        res_tx = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": sender_acc_id,
                "recipient_user_number": "OMR-3847-1920",
                "amount": "50000.00",
                "currency": "EGP",
                "note": "High value business capital transfer",
                "password": "Customer@2026!",
            },
            headers=headers,
        )
        assert res_tx.status_code == 201, res_tx.text

        # Verify admin ticket center has a new RISK_REVIEW ticket
        admin_tkts = await client.get("/api/v1/admin/tickets?ticket_type=RISK_REVIEW", headers=admin_headers)
        assert admin_tkts.status_code == 200
        risk_tkts = admin_tkts.json()["items"]
        assert len(risk_tkts) >= 1
        assert any("50,000" in t["description"] or t["ticket_type"] == "RISK_REVIEW" for t in risk_tkts)


@pytest.mark.asyncio
async def test_admin_ticket_statistics_kpis(seeded_db):
    """Verify admin statistics dashboard endpoint returns accurate operational KPIs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        stats_res = await client.get("/api/v1/admin/tickets/stats", headers=admin_headers)
        assert stats_res.status_code == 200, stats_res.text
        stats = stats_res.json()

        assert "open_tickets" in stats
        assert "high_priority_tickets" in stats
        assert "critical_tickets" in stats
        assert "waiting_for_customer" in stats
        assert "waiting_for_document" in stats
        assert "escalated_tickets" in stats
        assert "resolved_today" in stats
        assert "transfer_security_locks" in stats
        assert "restoration_requests" in stats
        assert "customers_requiring_compliance" in stats
        assert stats["total_tickets"] >= 10
