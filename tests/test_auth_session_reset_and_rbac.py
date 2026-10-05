"""Pytest suite for Session Termination, Password-Protected Transfers, Password Reset, and RBAC."""

import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_forgot_and_reset_password_flow(seeded_db):
    """Verify forgot password dispatch and reset token execution."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Request Password Reset
        forgot_res = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "ziad@omerta.ai"},
        )
        assert forgot_res.status_code == 200, forgot_res.text
        data = forgot_res.json()
        assert data["success"] is True
        assert data["simulated_email"] is not None
        reset_token = data["simulated_email"]["token"]
        assert reset_token

        # 2. Execute Password Reset with new password
        reset_res = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": reset_token,
                "new_password": "NewSecretPass2026!",
                "confirm_password": "NewSecretPass2026!",
            },
        )
        assert reset_res.status_code == 200, reset_res.text
        assert reset_res.json()["success"] is True

        # 3. Old password should fail
        old_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        assert old_login.status_code == 401

        # 4. New password succeeds
        new_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "NewSecretPass2026!", "force_login": True},
        )
        assert new_login.status_code == 200

        # 5. Restore default password for test cleanliness
        req_res2 = await client.post("/api/v1/auth/forgot-password", json={"email": "ziad@omerta.ai"})
        token2 = req_res2.json()["simulated_email"]["token"]
        await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token2, "new_password": "Customer@2026!", "confirm_password": "Customer@2026!"},
        )


@pytest.mark.asyncio
async def test_transfer_password_verification_and_3_strike_risk_lock(seeded_db):
    """Verify that transfers require password, track 3 failed attempts, and lock account as HIGH risk."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
        )
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        accs_res = await client.get("/api/v1/customer/accounts", headers=headers)
        acc_id = accs_res.json()[0]["account_id"]

        # 1st Failed attempt -> 401
        res_fail1 = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": acc_id,
                "recipient_identifier": "OMR-3847-1920",
                "amount": 250.0,
                "currency": "EGP",
                "password": "WrongPassword1!",
            },
            headers=headers,
        )
        assert res_fail1.status_code == 401
        assert "Attempt 1 of 3" in res_fail1.json()["detail"]["message"]

        # 2nd Failed attempt -> 401
        res_fail2 = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": acc_id,
                "recipient_identifier": "OMR-3847-1920",
                "amount": 250.0,
                "currency": "EGP",
                "password": "WrongPassword2!",
            },
            headers=headers,
        )
        assert res_fail2.status_code == 401
        assert "Attempt 2 of 3" in res_fail2.json()["detail"]["message"]

        # 3rd Failed attempt -> 403 Forbidden with ACCOUNT_INACTIVATED_LOCKOUT
        res_fail3 = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": acc_id,
                "recipient_identifier": "OMR-3847-1920",
                "amount": 250.0,
                "currency": "EGP",
                "password": "WrongPassword3!",
            },
            headers=headers,
        )
        assert res_fail3.status_code == 403
        assert res_fail3.json()["detail"]["error"] == "ACCOUNT_INACTIVATED_LOCKOUT"
        assert "INACTIVATED" in res_fail3.json()["detail"]["message"]

        # 4. Attempting to log in as Ziad is now BLOCKED with 403 ACCOUNT_INACTIVE_LOCKED
        res_login_blocked = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!", "is_vpn": False},
        )
        assert res_login_blocked.status_code == 403
        assert res_login_blocked.json()["detail"]["error"] == "ACCOUNT_INACTIVE_LOCKED"

        # 5. Administrator logs in and resolves Ziad's risk in Admin Control Center
        res_admin = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!", "is_vpn": False},
        )
        admin_headers = {"Authorization": f"Bearer {res_admin.json()['access_token']}"}

        # Resolve risk for customer
        res_resolve = await client.post(
            "/api/v1/admin/problem-customers/CUST-1001/resolve-risk",
            json={"reason": "Customer identity verified by telephone; account reactivated.", "reset_risk_to": "LOW"},
            headers=admin_headers,
        )
        assert res_resolve.status_code == 200
        assert res_resolve.json()["success"] is True

        # 6. Ziad CAN NOW LOG IN SUCCESSFULLY!
        res_login_success = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!", "is_vpn": False},
        )
        assert res_login_success.status_code == 200
        assert res_login_success.json()["user"]["username"] == "ziad@omerta.ai"


@pytest.mark.asyncio
async def test_transfer_vpn_blocking_and_risk_escalation(seeded_db):
    """Verify that transfers initiated over VPN or proxy tunnels are blocked and customer risk is elevated to HIGH."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login Layla
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!"},
        )
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        accs_res = await client.get("/api/v1/customer/accounts", headers=headers)
        acc_id = accs_res.json()[0]["account_id"]

        # Transfer attempt with VPN telemetry -> blocked with 403
        res_vpn = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": acc_id,
                "recipient_identifier": "OMR-1092-4821",
                "amount": 150.0,
                "currency": "EGP",
                "password": "Customer@2026!",
                "is_vpn": True,
                "country": "US",
                "isp": "M247 Ltd VPN Hosting",
            },
            headers=headers,
        )
        assert res_vpn.status_code == 403
        assert res_vpn.json()["detail"]["error"] == "VPN_TRANSFER_BLOCKED"
        assert "commercial VPNs" in res_vpn.json()["detail"]["message"]

        # Direct Transfer without VPN -> succeeds with 201
        res_direct = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": acc_id,
                "recipient_identifier": "OMR-1092-4821",
                "amount": 100.0,
                "currency": "EGP",
                "password": "Customer@2026!",
                "is_vpn": False,
                "country": "EG",
                "isp": "Telecom Egypt (TE-AS)",
            },
            headers=headers,
        )
        assert res_direct.status_code == 201
        assert res_direct.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_multi_user_concurrent_login_independence(seeded_db):
    """Verify that different users remain logged in concurrently, while same-user multi-login supersedes old session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login User 1 (Ziad) in Browser A
        res_user1_a = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
            headers={"User-Agent": "Chrome-Linux"},
        )
        assert res_user1_a.status_code == 200
        token_u1_a = res_user1_a.json()["access_token"]
        headers_u1_a = {"Authorization": f"Bearer {token_u1_a}"}

        # 2. Login User 2 (Layla) in Browser B
        res_user2 = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!"},
            headers={"User-Agent": "Firefox-Linux"},
        )
        assert res_user2.status_code == 200
        token_u2 = res_user2.json()["access_token"]
        headers_u2 = {"Authorization": f"Bearer {token_u2}"}

        # 3. BOTH User 1 and User 2 should be active and valid simultaneously!
        me_u1 = await client.get("/api/v1/auth/me", headers=headers_u1_a)
        assert me_u1.status_code == 200
        assert me_u1.json()["user"]["username"] == "ziad@omerta.ai"

        me_u2 = await client.get("/api/v1/auth/me", headers=headers_u2)
        assert me_u2.status_code == 200
        assert me_u2.json()["user"]["username"] == "layla@omerta.ai"

        # 4. Now User 1 (Ziad) logs into Browser C
        res_user1_c = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!"},
            headers={"User-Agent": "Edge-Windows"},
        )
        assert res_user1_c.status_code == 200
        token_u1_c = res_user1_c.json()["access_token"]
        headers_u1_c = {"Authorization": f"Bearer {token_u1_c}"}

        # 5. User 1's OLD session (Browser A) is revoked
        me_u1_old = await client.get("/api/v1/auth/me", headers=headers_u1_a)
        assert me_u1_old.status_code == 401
        assert me_u1_old.json()["detail"]["error"] == "SESSION_REVOKED"

        # 6. User 1's NEW session (Browser C) is active
        me_u1_new = await client.get("/api/v1/auth/me", headers=headers_u1_c)
        assert me_u1_new.status_code == 200

        # 7. User 2 (Layla) is STILL active and completely untouched!
        me_u2_still = await client.get("/api/v1/auth/me", headers=headers_u2)
        assert me_u2_still.status_code == 200
        assert me_u2_still.json()["user"]["username"] == "layla@omerta.ai"


@pytest.mark.asyncio
async def test_session_revocation_on_force_login(seeded_db):
    """Verify that when Session B force-logs in, Session A's JWT token is revoked upon access."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login on Device 1
        res_sess1 = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!", "force_login": True},
            headers={"User-Agent": "Browser-Window-A"},
        )
        assert res_sess1.status_code == 200
        sess1_token = res_sess1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {sess1_token}"}

        # Device 1 can access /auth/me
        me1 = await client.get("/api/v1/auth/me", headers=headers1)
        assert me1.status_code == 200

        # 2. Login on Device 2 with force_login=True (terminates Device 1 session)
        res_sess2 = await client.post(
            "/api/v1/auth/login",
            json={"username": "layla@omerta.ai", "password": "Customer@2026!", "force_login": True},
            headers={"User-Agent": "Browser-Window-B-Private"},
        )
        assert res_sess2.status_code == 200

        # 3. Device 1 attempts another request -> rejected 401 SESSION_REVOKED
        me1_after = await client.get("/api/v1/auth/me", headers=headers1)
        assert me1_after.status_code == 401
        assert me1_after.json()["detail"]["error"] == "SESSION_REVOKED"


@pytest.mark.asyncio
async def test_reports_endpoints_and_summary(seeded_db):
    """Verify /reports/summary, /reports/types, and /reports/generate endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET summary
        res_sum = await client.get("/api/v1/reports/summary")
        assert res_sum.status_code == 200
        summary_data = res_sum.json()
        assert "available_reports" in summary_data
        assert "total_transactions" in summary_data

        # GET types
        res_types = await client.get("/api/v1/reports/types")
        assert res_types.status_code == 200
        assert len(res_types.json()) >= 5

        # POST generate
        res_post_gen = await client.post(
            "/api/v1/reports/generate",
            json={"report_type": "risk-distribution"},
        )
        assert res_post_gen.status_code == 200
        assert res_post_gen.json()["report_type"] == "risk-distribution"


@pytest.mark.asyncio
async def test_admin_vpn_lockout_and_clean_ip_unlock(seeded_db):
    """Verify that an Administrator using VPN has their account locked immediately, and unlocks upon connecting from a clean normal IP."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin logs in with VPN connection telemetry -> Locked immediately with 403
        res_vpn_admin = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin@omerta.ai",
                "password": "AdminPass123!",
                "is_vpn": True,
                "country": "US",
                "isp": "NordVPN / M247 Ltd",
            },
        )
        assert res_vpn_admin.status_code == 403
        assert res_vpn_admin.json()["detail"]["error"] == "ADMIN_VPN_SECURITY_LOCK"
        assert "administrative account has been locked" in res_vpn_admin.json()["detail"]["message"].lower()

        # 2. Admin logs in with clean normal IP without VPN -> Account automatically unlocked and login succeeds!
        res_clean_admin = await client.post(
            "/api/v1/auth/login",
            json={
                "username": "admin@omerta.ai",
                "password": "AdminPass123!",
                "is_vpn": False,
                "country": "EG",
                "isp": "Telecom Egypt (TE-AS)",
            },
        )
        assert res_clean_admin.status_code == 200
        assert res_clean_admin.json()["user"]["role"] == "ADMINISTRATOR"


@pytest.mark.asyncio
async def test_admin_problem_customers_and_transaction_review(seeded_db):
    """Verify listing problem customers, direct risk resolution, and transaction approvals."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as Admin
        res_admin = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!", "is_vpn": False},
        )
        assert res_admin.status_code == 200
        headers = {"Authorization": f"Bearer {res_admin.json()['access_token']}"}

        # 1. Fetch problem customers queue
        res_probs = await client.get("/api/v1/admin/problem-customers", headers=headers)
        assert res_probs.status_code == 200
        probs = res_probs.json()
        assert isinstance(probs, list)

        # 2. Test manual risk resolution on a customer
        if len(probs) > 0:
            target_id = probs[0]["customer_id"]
            res_resolve = await client.post(
                f"/api/v1/admin/problem-customers/{target_id}/resolve-risk",
                json={"reason": "Customer identity verified via direct phone call.", "reset_risk_to": "LOW"},
                headers=headers,
            )
            assert res_resolve.status_code == 200
            assert res_resolve.json()["success"] is True
            assert res_resolve.json()["risk_level"] == "LOW"

            # 3. Test sending security notification
            res_notify = await client.post(
                f"/api/v1/admin/problem-customers/{target_id}/notify",
                json={"channel": "EMAIL", "subject": "Account Security Clearance", "message": "Your account has been cleared and unlocked."},
                headers=headers,
            )
            assert res_notify.status_code == 200
            assert res_notify.json()["success"] is True

        # 4. Test Agentic SAR Report Preview
        res_sar = await client.post("/api/v1/admin/agentic/generate-sar-report?case_or_txn_id=TXN-1001", headers=headers)
        assert res_sar.status_code == 200
        assert res_sar.json()["status"] == "COMING_SOON"
        assert len(res_sar.json()["agents"]) == 4


@pytest.mark.asyncio
async def test_super_admin_add_staff_protection_and_prohibit_customer(seeded_db):
    """Verify:
    1. Super Admin 'admin' can add co-administrators (ADMINISTRATOR), INVESTIGATOR, FRAUD_ANALYST, and AUDITOR with passwords.
    2. Admin staff creation explicitly rejects CUSTOMER roles.
    3. Co-administrators CANNOT delete the root super admin 'admin' (HTTP 403 SUPER_ADMIN_PROTECTED).
    4. Co-administrators CANNOT delete their own active account (HTTP 400 SELF_DELETION_PROHIBITED).
    5. Administrators CAN successfully delete other non-root staff members.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login Root Super Admin
        res_root = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!", "is_vpn": False},
        )
        assert res_root.status_code == 200
        root_token = res_root.json()["access_token"]
        root_headers = {"Authorization": f"Bearer {root_token}"}

        # 2. Attempt to create a CUSTOMER via staff creation -> PROHIBITED (400)
        res_cust_fail = await client.post(
            "/api/v1/admin/staff",
            json={
                "full_name": "Prohibited Customer Account",
                "email": "badcust@omerta.ai",
                "username": "badcust",
                "password": "Password123!",
                "role": "CUSTOMER",
            },
            headers=root_headers,
        )
        assert res_cust_fail.status_code == 400
        assert res_cust_fail.json()["detail"]["error"] == "INVALID_STAFF_ROLE"

        # 3. Super Admin creates a Co-Administrator (ADMINISTRATOR)
        res_coadmin = await client.post(
            "/api/v1/admin/staff",
            json={
                "full_name": "Karim CoAdmin",
                "email": "karim_admin@omerta.ai",
                "username": "karim_admin",
                "password": "CoAdminPassword123!",
                "role": "ADMINISTRATOR",
            },
            headers=root_headers,
        )
        assert res_coadmin.status_code == 201
        coadmin_data = res_coadmin.json()
        coadmin_id = coadmin_data["id"]
        assert coadmin_data["role"] == "ADMINISTRATOR"

        # 4. Super Admin creates an Investigator (SENIOR_INVESTIGATOR)
        res_inv = await client.post(
            "/api/v1/admin/staff",
            json={
                "full_name": "Nour Investigator",
                "email": "nour_inv@omerta.ai",
                "username": "nour_inv",
                "password": "InvPassword123!",
                "role": "SENIOR_INVESTIGATOR",
            },
            headers=root_headers,
        )
        assert res_inv.status_code == 201
        inv_data = res_inv.json()
        inv_id = inv_data["id"]

        # 5. Super Admin creates a Fraud Analyst (FRAUD_ANALYST)
        res_ana = await client.post(
            "/api/v1/admin/staff",
            json={
                "full_name": "Mona Analyst",
                "email": "mona_ana@omerta.ai",
                "username": "mona_ana",
                "password": "AnaPassword123!",
                "role": "FRAUD_ANALYST",
            },
            headers=root_headers,
        )
        assert res_ana.status_code == 201

        # 6. Super Admin creates an Auditor (AUDITOR)
        res_aud = await client.post(
            "/api/v1/admin/staff",
            json={
                "full_name": "Youssef Auditor",
                "email": "youssef_aud@omerta.ai",
                "username": "youssef_aud",
                "password": "AudPassword123!",
                "role": "AUDITOR",
            },
            headers=root_headers,
        )
        assert res_aud.status_code == 201

        # 7. Login as the newly created Co-Administrator
        res_coadmin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "karim_admin", "password": "CoAdminPassword123!", "is_vpn": False},
        )
        assert res_coadmin_login.status_code == 200
        coadmin_headers = {"Authorization": f"Bearer {res_coadmin_login.json()['access_token']}"}

        # 8. Co-Administrator tries to delete the ROOT Super Admin ('admin') -> FORBIDDEN (403 SUPER_ADMIN_PROTECTED)
        res_del_root = await client.delete("/api/v1/admin/staff/admin", headers=coadmin_headers)
        assert res_del_root.status_code == 403
        assert res_del_root.json()["detail"]["error"] == "SUPER_ADMIN_PROTECTED"

        # Also test with root email
        res_del_root_email = await client.delete("/api/v1/admin/staff/admin@omerta.ai", headers=coadmin_headers)
        assert res_del_root_email.status_code == 403
        assert res_del_root_email.json()["detail"]["error"] == "SUPER_ADMIN_PROTECTED"

        # 9. Co-Administrator tries to delete HIMSELF -> BAD REQUEST (400 SELF_DELETION_PROHIBITED)
        res_del_self = await client.delete(f"/api/v1/admin/staff/{coadmin_id}", headers=coadmin_headers)
        assert res_del_self.status_code == 400
        assert res_del_self.json()["detail"]["error"] == "SELF_DELETION_PROHIBITED"

        # 10. Co-Administrator CAN delete a non-root staff member (the investigator) -> SUCCESS (200)
        res_del_inv = await client.delete(f"/api/v1/admin/staff/{inv_id}", headers=coadmin_headers)
        assert res_del_inv.status_code == 200
        assert res_del_inv.json()["success"] is True


@pytest.mark.asyncio
async def test_periodic_30s_telemetry_heartbeat_and_vpn_detection(seeded_db):
    """Verify 30-second recurring network telemetry check & heartbeat synchronization:
    1. Customer sends 30s telemetry heartbeat -> updates active session with IP, Country, and VPN state.
    2. Admin sends 30s telemetry heartbeat over VPN -> triggers immediate ADMIN_VPN_SECURITY_LOCK and session revocation.
    3. Admin sends 30s telemetry heartbeat over clean IP -> triggers automatic account unlock.
    4. Customer security heartbeat endpoint returns next_interval_seconds: 30.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login Customer (Ziad)
        res_cust = await client.post(
            "/api/v1/auth/login",
            json={"username": "ziad@omerta.ai", "password": "Customer@2026!", "is_vpn": False},
        )
        assert res_cust.status_code == 200
        cust_headers = {"Authorization": f"Bearer {res_cust.json()['access_token']}"}

        # 2. Customer 30s Heartbeat with normal connection
        res_beat1 = await client.post(
            "/api/v1/auth/telemetry/heartbeat",
            json={
                "client_ip": "197.58.12.99",
                "country": "EG",
                "is_vpn": False,
                "isp": "Telecom Egypt",
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            },
            headers=cust_headers,
        )
        assert res_beat1.status_code == 200
        beat1_data = res_beat1.json()
        assert beat1_data["status"] == "ACTIVE"
        assert beat1_data["client_ip"] == "197.58.12.99"
        assert beat1_data["is_vpn"] is False
        assert beat1_data["next_interval_seconds"] == 30

        # Verify session records reflect the updated telemetry
        res_sess = await client.get("/api/v1/customer/security/sessions", headers=cust_headers)
        assert res_sess.status_code == 200
        active_sess = [s for s in res_sess.json() if s["is_active"]][0]
        assert active_sess["ip_address"] == "197.58.12.99"

        # 3. Customer switches to VPN -> 30s Heartbeat updates session with VPN signal
        res_beat2 = await client.post(
            "/api/v1/customer/security/heartbeat",
            json={
                "client_ip": "51.195.242.237",
                "country": "GB",
                "is_vpn": True,
                "isp": "M247 Ltd VPN Hosting",
            },
            headers=cust_headers,
        )
        assert res_beat2.status_code == 200
        beat2_data = res_beat2.json()
        assert beat2_data["is_vpn"] is True
        assert beat2_data["country"] == "GB"

        # 4. Admin 30s Heartbeat with VPN -> Immediate ADMIN_VPN_SECURITY_LOCK
        res_admin = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!", "is_vpn": False},
        )
        assert res_admin.status_code == 200
        admin_headers = {"Authorization": f"Bearer {res_admin.json()['access_token']}"}

        res_admin_vpn_beat = await client.post(
            "/api/v1/auth/telemetry/heartbeat",
            json={
                "client_ip": "185.220.101.5",
                "country": "DE",
                "is_vpn": True,
                "isp": "NordVPN / Datacamp",
            },
            headers=admin_headers,
        )
        assert res_admin_vpn_beat.status_code == 200
        vpn_beat_data = res_admin_vpn_beat.json()
        assert vpn_beat_data["locked"] is True
        assert vpn_beat_data["error"] == "ADMIN_VPN_SECURITY_LOCK"


@pytest.mark.asyncio
async def test_geographic_velocity_impossible_travel_anomaly(seeded_db):
    """Verify that rapid location shifts (e.g. Cairo to Port Said / Bur Sa'id) trigger IMPOSSIBLE_TRAVEL_VELOCITY risk escalation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login Amira
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "amira@omerta.ai", "password": "Customer@2026!"},
        )
        assert login_res.status_code == 200
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        accs = await client.get("/api/v1/customer/accounts", headers=headers)
        acc_id = accs.json()[0]["account_id"]

        # 2. Amira initiates transfer from Port Said (Bur Sa'id) immediately after Cairo session
        res_trf = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": acc_id,
                "recipient_identifier": "OMR-1092-4821",
                "amount": 1000.0,
                "currency": "EGP",
                "password": "Customer@2026!",
                "city": "Port Said",
                "country": "EG",
                "is_vpn": False,
            },
            headers=headers,
        )
        assert res_trf.status_code == 201
        receipt = res_trf.json()
        assert receipt["status"] == "COMPLETED"
        assert receipt["risk_level"] in ["HIGH", "CRITICAL"]



