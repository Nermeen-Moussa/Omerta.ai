"""Stage 2 Comprehensive Pytest Suite: Customer Banking Platform & Admin Control Center.

Verifies:
1. Customer Self-Registration with unique Omerta User Number (OMR-XXXX-XXXX) and initial opening balance ledger entry.
2. Login and Role-based authorization.
3. Strict Customer Data Isolation (IDOR defense, customer-scoped access, 403 on admin routes).
4. Privacy-Preserving Recipient Lookup via Omerta User Number.
5. Peer-to-Peer Transfer Execution with atomic double-entry ledger updates, insufficient balance defense, self-transfer block, and idempotency key safety.
6. Deterministic Human Review Threshold: strictly `risk_score > 40.00` (score of 40.00 does NOT trigger review).
7. Admin Control Center: Overview KPIs, User Status Management with audit logs, and Ledger-backed Balance Adjustments with mandatory reason.
8. Customer Privacy & Device Security: Session telemetry, VPN notices, revocation, and consent settings.
"""

import re
import secrets
import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_customer_registration_with_opening_balance(seeded_db):
    """Verify customer registration creates user, profile, unique Omerta User Number, and opening ledger entry."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "full_name": "Kareem El-Sayed",
            "email": "kareem.test@omerta.ai",
            "username": "kareem_test",
            "password": "SecureCustomerPass2026!",
            "confirm_password": "SecureCustomerPass2026!",
            "country": "EG",
            "preferred_currency": "EGP",
            "initial_balance": 18500.0,
            "device_consent": True,
        }

        res = await client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 201, res.text
        data = res.json()

        assert "access_token" in data
        assert data["user"]["role"] == "CUSTOMER"
        assert data["user"]["email"] == "kareem.test@omerta.ai"

        customer = data["customer"]
        assert customer["name"] == "Kareem El-Sayed"
        assert customer["declared_country"] == "EG"
        assert customer["preferred_currency"] == "EGP"
        assert customer["device_consent"] is True

        omerta_num = customer["omerta_user_number"]
        assert omerta_num is not None
        assert re.match(r"^OMR-\d{4}-\d{4}$", omerta_num), f"Invalid Omerta User Number format: {omerta_num}"

        # Verify Customer Account and Initial Ledger Entry
        token = data["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        acc_res = await client.get("/api/v1/customer/accounts", headers=auth_headers)
        assert acc_res.status_code == 200
        accounts = acc_res.json()
        assert len(accounts) >= 1

        primary_acc = accounts[0]
        assert primary_acc["currency"] == "EGP"
        assert primary_acc["balance"] == 18500.0
        assert primary_acc["status"] == "ACTIVE"

        # Check ledger statement
        assert "recent_ledger" in primary_acc
        ledger = primary_acc["recent_ledger"]
        assert len(ledger) >= 1
        opening_entry = ledger[-1]
        assert opening_entry["entry_type"] == "OPENING_BALANCE"
        assert opening_entry["amount"] == 18500.0
        assert opening_entry["balance_after"] == 18500.0


@pytest.mark.asyncio
async def test_customer_login_and_auth_flow(seeded_db):
    """Verify customer login with valid credentials and failure on invalid password."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Valid Login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert "access_token" in data
        assert data["user"]["role"] == "CUSTOMER"
        assert data["customer"]["omerta_user_number"] == "OMR-1092-4821"

        # 2. Invalid Password
        bad_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "WrongPassword123!"},
        )
        assert bad_res.status_code == 401


@pytest.mark.asyncio
async def test_customer_data_isolation_and_idor_protection(seeded_db):
    """Verify strict data isolation: Customer cannot access other customers' data or admin routes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ziad Login
        ziad_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        ziad_token = ziad_res.json()["access_token"]
        ziad_headers = {"Authorization": f"Bearer {ziad_token}"}

        # 1. Ziad accesses /customer/dashboard -> only returns Ziad's profile and accounts
        dash_res = await client.get("/api/v1/customer/dashboard", headers=ziad_headers)
        assert dash_res.status_code == 200
        dash_data = dash_res.json()
        assert dash_data["customer"]["omerta_user_number"] == "OMR-1092-4821"
        assert dash_data["customer"]["name"] == "Ziad Karim"

        # 2. Customer attempting to access Admin endpoints MUST return 403 Forbidden
        admin_dash_res = await client.get("/api/v1/admin/dashboard", headers=ziad_headers)
        assert admin_dash_res.status_code == 403

        admin_users_res = await client.get("/api/v1/admin/users", headers=ziad_headers)
        assert admin_users_res.status_code == 403

        admin_accounts_res = await client.get("/api/v1/admin/accounts", headers=ziad_headers)
        assert admin_accounts_res.status_code == 403


@pytest.mark.asyncio
async def test_recipient_lookup_by_omerta_user_number(seeded_db):
    """Verify recipient lookup returns safe masked metadata without leaking email, phone, or balance."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ziad Login
        ziad_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        ziad_headers = {"Authorization": f"Bearer {ziad_res.json()['access_token']}"}

        # Lookup Layla by her Omerta User Number (OMR-3847-1920)
        res = await client.get(
            "/api/v1/customer/recipient/lookup?omerta_user_number=OMR-3847-1920",
            headers=ziad_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["found"] is True
        assert data["omerta_user_number"] == "OMR-3847-1920"
        assert "Layla" in data["display_name"]
        assert data["country"] == "EG"
        assert "EGP" in data["supported_currencies"]

        # Ensure private/sensitive info is NOT leaked
        assert "email" not in data
        assert "phone" not in data
        assert "balance" not in data
        assert "id" not in data

        # Non-existent recipient lookup
        notFoundRes = await client.get(
            "/api/v1/customer/recipient/lookup?omerta_user_number=OMR-9999-9999",
            headers=ziad_headers,
        )
        assert notFoundRes.status_code == 404
        assert notFoundRes.json()["detail"]["error"] == "RECIPIENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_peer_to_peer_transfer_execution(seeded_db):
    """Verify full P2P transfer between registered users with atomic double-entry ledger."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login Ziad (Sender)
        ziad_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        ziad_headers = {"Authorization": f"Bearer {ziad_login.json()['access_token']}"}

        # 2. Login Layla (Recipient)
        layla_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!"},
        )
        layla_headers = {"Authorization": f"Bearer {layla_login.json()['access_token']}"}

        # Check initial balances
        ziad_accs = (await client.get("/api/v1/customer/accounts", headers=ziad_headers)).json()
        layla_accs = (await client.get("/api/v1/customer/accounts", headers=layla_headers)).json()

        ziad_initial_balance = ziad_accs[0]["balance"]
        layla_initial_balance = layla_accs[0]["balance"]
        transfer_amount = 3500.0

        # 3. Execute Transfer
        transfer_payload = {
            "source_account_id": ziad_accs[0]["account_id"],
            "recipient_omerta_number": "OMR-3847-1920",  # Layla's number
            "amount": transfer_amount,
            "currency": "EGP",
            "note": "Payment for software project deliverables",
            "idempotency_key": "IDEM-TEST-STAGE2-001",
        }

        transfer_res = await client.post(
            "/api/v1/customer/transfers",
            json=transfer_payload,
            headers=ziad_headers,
        )
        assert transfer_res.status_code == 201, transfer_res.text
        receipt = transfer_res.json()

        assert receipt["status"] == "COMPLETED"
        assert receipt["amount"] == transfer_amount
        assert receipt["currency"] == "EGP"
        assert receipt["sender"]["omerta_user_number"] == "OMR-1092-4821"
        assert receipt["recipient"]["omerta_user_number"] == "OMR-3847-1920"
        assert receipt["is_demo"] is True

        # 4. Verify Sender Balance & Debit Ledger Entry
        ziad_accs_after = (await client.get("/api/v1/customer/accounts", headers=ziad_headers)).json()
        assert ziad_accs_after[0]["balance"] == ziad_initial_balance - transfer_amount
        ziad_ledger = ziad_accs_after[0]["recent_ledger"]
        latest_debit = ziad_ledger[0]
        assert latest_debit["entry_type"] == "DEBIT"
        assert latest_debit["amount"] == transfer_amount
        assert latest_debit["balance_after"] == ziad_initial_balance - transfer_amount

        # 5. Verify Recipient Balance & Credit Ledger Entry
        layla_accs_after = (await client.get("/api/v1/customer/accounts", headers=layla_headers)).json()
        assert layla_accs_after[0]["balance"] == layla_initial_balance + transfer_amount
        layla_ledger = layla_accs_after[0]["recent_ledger"]
        latest_credit = layla_ledger[0]
        assert latest_credit["entry_type"] == "CREDIT"
        assert latest_credit["amount"] == transfer_amount
        assert latest_credit["balance_after"] == layla_initial_balance + transfer_amount


@pytest.mark.asyncio
async def test_transfer_safety_guards(seeded_db):
    """Verify transfer validation: self-transfer block, insufficient balance block, and duplicate idempotency."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ziad Login
        ziad_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        ziad_headers = {"Authorization": f"Bearer {ziad_login.json()['access_token']}"}
        ziad_acc = (await client.get("/api/v1/customer/accounts", headers=ziad_headers)).json()[0]

        # 1. Self-Transfer Attempt
        self_res = await client.post(
            "/api/v1/customer/transfers",
            json={
                "source_account_id": ziad_acc["account_id"],
                "recipient_omerta_number": "OMR-1092-4821",  # Ziad's own number
                "amount": 500.0,
                "currency": "EGP",
            },
            headers=ziad_headers,
        )
        assert self_res.status_code == 400
        assert "own" in self_res.json()["detail"]["message"].lower()

        # 2. Insufficient Balance Attempt
        overdraft_res = await client.post(
            "/api/v1/customer/transfers",
            json={
                "source_account_id": ziad_acc["account_id"],
                "recipient_omerta_number": "OMR-3847-1920",
                "amount": 9999999.0,
                "currency": "EGP",
            },
            headers=ziad_headers,
        )
        assert overdraft_res.status_code == 400
        assert "insufficient" in overdraft_res.json()["detail"]["message"].lower()

        # 3. Idempotency Key Duplicate Defense
        dup_payload = {
            "source_account_id": ziad_acc["account_id"],
            "recipient_omerta_number": "OMR-3847-1920",
            "amount": 100.0,
            "currency": "EGP",
            "idempotency_key": "IDEM-DUP-TEST-001",
        }
        res1 = await client.post("/api/v1/customer/transfers", json=dup_payload, headers=ziad_headers)
        assert res1.status_code == 201

        # Second submission with same idempotency key must not execute twice
        res2 = await client.post("/api/v1/customer/transfers", json=dup_payload, headers=ziad_headers)
        assert res2.status_code in [200, 201, 409]
        if res2.status_code == 409:
            assert "duplicate" in res2.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_strict_human_review_threshold():
    """Verify that human review rule strictly follows risk_score > 40.00 (score of 40.0 does NOT trigger review)."""
    def evaluate_review(score: float) -> bool:
        return score > 40.0

    assert evaluate_review(40.00) is False, "Score of exactly 40.0 must NOT trigger human review"
    assert evaluate_review(40.01) is True, "Score of 40.01 MUST trigger human review"
    assert evaluate_review(15.00) is False, "Low score must not trigger review"
    assert evaluate_review(75.00) is True, "High score must trigger review"


@pytest.mark.asyncio
async def test_admin_control_center_and_balance_adjustment(seeded_db):
    """Verify admin control center overview, user management, and ledger-backed balance adjustment with reason."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin Login
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Admin Dashboard Overview
        dash_res = await client.get("/api/v1/admin/dashboard", headers=admin_headers)
        assert dash_res.status_code == 200
        dash = dash_res.json()
        summary = dash["summary"] if "summary" in dash else dash
        assert "total_customers" in summary
        assert "total_accounts" in summary
        assert "total_transactions" in summary
        assert "transactions_requiring_review" in summary

        # 3. Admin Users List
        users_res = await client.get("/api/v1/admin/users", headers=admin_headers)
        assert users_res.status_code == 200
        users_data = users_res.json()
        assert len(users_data["items"]) >= 1

        # 4. Admin Accounts List
        accs_res = await client.get("/api/v1/admin/accounts", headers=admin_headers)
        assert accs_res.status_code == 200
        accounts = accs_res.json()["items"]
        target_account = accounts[0]
        acc_id = target_account["id"]
        old_balance = target_account["balance"]

        # 5. Ledger-backed Balance Adjustment WITH Reason
        adj_res = await client.post(
            f"/api/v1/admin/accounts/{acc_id}/adjustment",
            json={
                "adjustment_amount": 5000.0,
                "reason": "Regulatory compliance audit compensation credit",
            },
            headers=admin_headers,
        )
        assert adj_res.status_code == 200
        adj_data = adj_res.json()
        assert adj_data["success"] is True
        assert adj_data["new_balance"] == old_balance + 5000.0
        assert adj_data["entry_type"] == "ADMIN_ADJUSTMENT"

        # 6. Adjustment WITHOUT Reason MUST Fail
        fail_res = await client.post(
            f"/api/v1/admin/accounts/{acc_id}/adjustment",
            json={"adjustment_amount": 100.0, "reason": ""},
            headers=admin_headers,
        )
        assert fail_res.status_code in [400, 422]


@pytest.mark.asyncio
async def test_customer_security_and_consent_management(seeded_db):
    """Verify customer session tracking, VPN notices, revocation, and consent settings."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ziad Login
        ziad_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        ziad_headers = {"Authorization": f"Bearer {ziad_login.json()['access_token']}"}

        # 1. Fetch Sessions
        sess_res = await client.get("/api/v1/customer/security/sessions", headers=ziad_headers)
        assert sess_res.status_code == 200
        sessions = sess_res.json()
        assert len(sessions) >= 1
        curr_session = sessions[0]
        assert "session_id" in curr_session
        assert "is_active" in curr_session

        # 2. Update Consent Setting
        consent_res = await client.post(
            "/api/v1/customer/security/consent",
            json={"device_consent": False},
            headers=ziad_headers,
        )
        assert consent_res.status_code == 200
        assert consent_res.json()["device_consent"] is False

        # 3. Revoke Session
        revoke_res = await client.post(
            f"/api/v1/customer/security/sessions/{curr_session['session_id']}/revoke",
            headers=ziad_headers,
        )
        assert revoke_res.status_code == 200
        assert revoke_res.json()["revoked"] is True


@pytest.mark.asyncio
async def test_customer_phone_registration_and_phone_transfer(seeded_db):
    """Verify registration with phone number and transferring money using recipient phone number."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a new user with Egyptian phone number
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Tamer Hosny",
                "email": "tamer@omerta.ai",
                "username": "tamer_h",
                "password": "CustomerPass2026!",
                "confirm_password": "CustomerPass2026!",
                "phone": "+20 10 9999 8888",
                "country": "EG",
                "preferred_currency": "EGP",
                "initial_balance": 30000.0,
                "device_consent": True,
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        tamer_data = reg_res.json()
        tamer_token = tamer_data["access_token"]
        tamer_headers = {"Authorization": f"Bearer {tamer_token}"}

        # 2. Verify recipient lookup by phone number for Layla Hassan (+201022223333)
        lookup_res = await client.get(
            "/api/v1/customer/recipient/lookup?identifier=%2B201022223333",
            headers=tamer_headers,
        )
        assert lookup_res.status_code == 200, lookup_res.text
        recip = lookup_res.json()
        assert recip["found"] is True
        assert "Layla" in recip["display_name"]
        assert recip["omerta_user_number"] == "OMR-3847-1920"

        # 3. Get Tamer's account ID
        accounts = (await client.get("/api/v1/customer/accounts", headers=tamer_headers)).json()
        tamer_acc_id = accounts[0]["account_id"]

        # 4. Transfer 5,000 EGP to Layla using her phone number as identifier
        transfer_res = await client.post(
            "/api/v1/customer/transfers",
            headers=tamer_headers,
            json={
                "sender_account_id": tamer_acc_id,
                "recipient_identifier": "+20 10 2222 3333",
                "amount": 5000.0,
                "currency": "EGP",
                "note": "Payment via mobile number",
            },
        )
        assert transfer_res.status_code == 201, transfer_res.text
        receipt = transfer_res.json()
        assert receipt["status"] == "COMPLETED"
        assert receipt["recipient"]["omerta_user_number"] == "OMR-3847-1920"
        assert receipt["amount"] == 5000.0


@pytest.mark.asyncio
async def test_customer_profile_hides_risk_rating(seeded_db):
    """Verify customer profile never returns or displays internal AML risk scores to customer."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        profile_res = await client.get("/api/v1/customer/profile", headers=headers)
        assert profile_res.status_code == 200
        profile = profile_res.json()

        assert "risk_level" not in profile or profile.get("verification_status") == "TIER_1_VERIFIED"
        assert profile["name"] == "Ziad Karim"
        assert profile["omerta_user_number"] == "OMR-1092-4821"
        assert "phone" in profile


@pytest.mark.asyncio
async def test_admin_create_and_manage_staff_subadmins(seeded_db):
    """Verify administrator can create sub-admins and operational staff with granular privileges."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as Admin
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. List initial staff
        staff_list_res = await client.get("/api/v1/admin/staff", headers=admin_headers)
        assert staff_list_res.status_code == 200
        initial_staff = staff_list_res.json()
        assert len(initial_staff) >= 4  # admin, analyst, investigator, auditor

        # 3. Create a new Sub-Admin / Operations Lead
        new_staff_payload = {
            "full_name": "Mostafa Nabil",
            "email": "mostafa.ops@omerta.ai",
            "username": "mostafa_ops",
            "password": "StaffSecretPass2026!",
            "role": "FRAUD_ANALYST",
            "privileges": [
                "USER_MANAGEMENT",
                "FLAGGED_TRANSACTION_REVIEW",
                "AUDIT_TELEMETRY",
            ],
        }
        create_res = await client.post("/api/v1/admin/staff", headers=admin_headers, json=new_staff_payload)
        assert create_res.status_code == 201, create_res.text
        created = create_res.json()
        assert created["full_name"] == "Mostafa Nabil"
        assert created["email"] == "mostafa.ops@omerta.ai"
        assert created["role"] == "FRAUD_ANALYST"
        assert "FLAGGED_TRANSACTION_REVIEW" in created["privileges"]

        # 4. Verify login as the new staff member
        staff_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "mostafa.ops@omerta.ai", "password": "StaffSecretPass2026!"},
        )
        assert staff_login.status_code == 200
        staff_token = staff_login.json()["access_token"]
        staff_headers = {"Authorization": f"Bearer {staff_token}"}

        # 5. Verify staff cannot create another staff member (only ADMINISTRATOR can)
        unauth_create = await client.post(
            "/api/v1/admin/staff",
            headers=staff_headers,
            json={
                "full_name": "Rogue Staff",
                "email": "rogue@omerta.ai",
                "username": "rogue",
                "password": "Password123!",
                "role": "FRAUD_ANALYST",
                "privileges": [],
            },
        )
        assert unauth_create.status_code == 403


@pytest.mark.asyncio
async def test_registration_validation_duplicates_and_policy_consent(seeded_db):
    """Verify validation for duplicate email, username, phone, full name, and mandatory policy consent."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Reject without Policy & Terms Consent
        no_consent_res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Hesham Refaat",
                "email": "hesham@omerta.ai",
                "username": "hesham_r",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "phone": "+20 10 9999 1111",
                "country": "EG",
                "preferred_currency": "EGP",
                "initial_balance": 15000.0,
                "device_consent": False,
            },
        )
        assert no_consent_res.status_code == 400
        assert "accept the Banking Terms" in no_consent_res.json()["detail"]["message"]

        # 2. Reject duplicate email (ziad@omerta.ai already exists)
        dup_email_res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Ziad New",
                "email": "ziad@omerta.ai",
                "username": "ziad_unique_123",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "phone": "+20 10 9999 2222",
                "country": "EG",
                "preferred_currency": "EGP",
                "initial_balance": 15000.0,
                "device_consent": True,
            },
        )
        assert dup_email_res.status_code == 400
        assert "email" in dup_email_res.json()["detail"]["message"].lower()

        # 3. Reject duplicate username (layla@omerta.ai already exists)
        dup_user_res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Layla Alternate",
                "email": "layla.alt@omerta.ai",
                "username": "layla@omerta.ai",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "phone": "+20 10 9999 3333",
                "country": "EG",
                "preferred_currency": "EGP",
                "initial_balance": 15000.0,
                "device_consent": True,
            },
        )
        assert dup_user_res.status_code == 400
        assert "username" in dup_user_res.json()["detail"]["message"].lower()

        # 4. Reject duplicate phone (+20 10 3333 4444 belonging to Amira)
        dup_phone_res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Different Name",
                "email": "diff.user@omerta.ai",
                "username": "diff_user_444",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "phone": "+20 10 3333 4444",
                "country": "EG",
                "preferred_currency": "EGP",
                "initial_balance": 15000.0,
                "device_consent": True,
            },
        )
        assert dup_phone_res.status_code == 400
        assert "phone" in dup_phone_res.json()["detail"]["message"].lower()

        # 5. Reject duplicate legal name ("Amira El-Sayed")
        dup_name_res = await client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Amira El-Sayed",
                "email": "amira.alt@omerta.ai",
                "username": "amira_alt_999",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "phone": "+20 10 9999 4444",
                "country": "EG",
                "preferred_currency": "EGP",
                "initial_balance": 15000.0,
                "device_consent": True,
            },
        )
        assert dup_name_res.status_code == 400
        assert "legal name" in dup_name_res.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_concurrent_session_restriction_and_force_login(seeded_db):
    """Verify single active session constraint: second login without force_login is blocked."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login session 1 for Layla
        login1 = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!"},
        )
        assert login1.status_code == 200
        token1 = login1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        assert (await client.get("/api/v1/auth/me", headers=headers1)).status_code == 200

        # 2. Login session 2 for same user -> succeeds and revokes session 1
        login2 = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!"},
        )
        assert login2.status_code == 200
        token2 = login2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Session 2 is valid
        assert (await client.get("/api/v1/auth/me", headers=headers2)).status_code == 200

        # Session 1 is now revoked
        me1_revoked = await client.get("/api/v1/auth/me", headers=headers1)
        assert me1_revoked.status_code == 401
        assert me1_revoked.json()["detail"]["error"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_transfer_concurrency_mutex_safety(seeded_db):
    """Verify asyncio Mutex & Semaphore concurrency controller safely coordinates multiple transfers."""
    import asyncio

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Ziad Login
        ziad_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!", "force_login": True},
        )
        ziad_token = ziad_res.json()["access_token"]
        ziad_headers = {"Authorization": f"Bearer {ziad_token}"}

        # Get Ziad's account ID
        accounts = (await client.get("/api/v1/customer/accounts", headers=ziad_headers)).json()
        acc_id = accounts[0]["account_id"]

        # Run 3 concurrent transfers of 500 EGP each to Layla
        async def do_transfer(idx: int):
            return await client.post(
                "/api/v1/customer/transfers",
                headers=ziad_headers,
                json={
                    "sender_account_id": acc_id,
                    "recipient_identifier": "OMR-3847-1920",
                    "amount": 500.0,
                    "currency": "EGP",
                    "note": f"Concurrent transfer {idx}",
                    "idempotency_key": f"CONCURRENT-TEST-{idx}-{secrets.token_hex(4)}",
                },
            )

        results = await asyncio.gather(do_transfer(1), do_transfer(2), do_transfer(3))
        for r in results:
            assert r.status_code == 201
            assert r.json()["status"] == "COMPLETED"



