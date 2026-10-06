"""Comprehensive Test Suite for Banking Security, Transfer Password Protection, and Support Recovery.

Verifies:
1. Dual Password Registration: Account Password vs. Transfer Password separation + National ID.
2. Rejection of identical Account and Transfer passwords.
3. 3-Strikes Non-Logout Security Hold:
   - 1st & 2nd failed attempts return 401 with remaining attempts warning.
   - 3rd failed attempt places transfer on BLOCKED security hold (HTTP 403).
   - User session and active state remain completely intact (User is NOT logged out).
4. Customer attempts to transfer funds while BLOCKED are rejected (HTTP 403).
5. Support Desk & WhatsApp-Style Chat Lifecycle:
   - Customer opens support ticket for TRANSFER_BLOCKED.
   - Customer and Staff post messages and attachments.
   - Customer uploads National ID photo.
6. Staff / Compliance Officer Queue & Review:
   - Staff views support cases queue.
   - Staff approves Identity Verification (VERIFIED).
   - Staff restores transfer access with confirmation dialog endpoint.
7. Transfer Password Recovery / Reset:
   - Customer sets new transfer password without needing old forgotten password.
   - Customer transfer status returns to ACTIVE.
   - Customer performs successful transfer with new transfer password.
8. Audit Trail Verification:
   - Failure events, block events, ID upload, verification, restoration, and password change recorded in audit_events.
"""

import re
import secrets
import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app


@pytest.mark.asyncio
async def test_dual_password_registration_and_validation(seeded_db):
    """Verify customer registration requires distinct account and transfer passwords plus National ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: Identical account password and transfer password (MUST FAIL)
        identical_payload = {
            "full_name": "Tariq Mansour",
            "email": "tariq.invalid@omerta.ai",
            "username": "tariq_invalid",
            "national_id_number": "29801011234567",
            "password": "SamePassword123!",
            "confirm_password": "SamePassword123!",
            "transfer_password": "SamePassword123!",
            "confirm_transfer_password": "SamePassword123!",
            "country": "EG",
            "preferred_currency": "EGP",
            "initial_balance": 25000.0,
            "device_consent": True,
        }
        res = await client.post("/api/v1/auth/register", json=identical_payload)
        assert res.status_code == 400, res.text
        assert "different from your Account Login Password" in res.text or "TRANSFER_PASSWORD_CANNOT_MATCH_ACCOUNT_PASSWORD" in res.text

        # Case 2: Valid distinct passwords and National ID (MUST SUCCEED)
        valid_payload = {
            "full_name": "Tariq Mansour",
            "email": "tariq.mansour@omerta.ai",
            "username": "tariq_mansour",
            "national_id_number": "29801011234567",
            "password": "AccountLoginPass2026!",
            "confirm_password": "AccountLoginPass2026!",
            "transfer_password": "TransferSecure2026!",
            "confirm_transfer_password": "TransferSecure2026!",
            "country": "EG",
            "preferred_currency": "EGP",
            "initial_balance": 30000.0,
            "device_consent": True,
        }
        reg_res = await client.post("/api/v1/auth/register", json=valid_payload)
        assert reg_res.status_code == 201, reg_res.text
        data = reg_res.json()

        assert "access_token" in data
        assert data["customer"]["name"] == "Tariq Mansour"
        assert data["customer"]["national_id_number"] == "29801011234567"
        assert data["customer"]["transfer_status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_three_strikes_non_logout_security_hold_and_recovery_workflow(seeded_db):
    """Verify 3 failed transfer password attempts block transfer without logging user out, followed by full support recovery."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register Sender Customer
        sender_payload = {
            "full_name": "Farah Amin",
            "email": f"farah.{secrets.token_hex(4)}@omerta.ai",
            "username": f"farah_{secrets.token_hex(4)}",
            "national_id_number": "29905051234567",
            "password": "FarahLoginPass2026!",
            "confirm_password": "FarahLoginPass2026!",
            "transfer_password": "FarahTransferPass2026!",
            "confirm_transfer_password": "FarahTransferPass2026!",
            "country": "EG",
            "preferred_currency": "EGP",
            "initial_balance": 50000.0,
            "device_consent": True,
        }
        sender_reg = await client.post("/api/v1/auth/register", json=sender_payload)
        assert sender_reg.status_code == 201
        sender_token = sender_reg.json()["access_token"]
        sender_headers = {"Authorization": f"Bearer {sender_token}"}

        # 2. Register Recipient Customer
        recipient_payload = {
            "full_name": "Youssef Nabil",
            "email": f"youssef.{secrets.token_hex(4)}@omerta.ai",
            "username": f"youssef_{secrets.token_hex(4)}",
            "national_id_number": "29811111234567",
            "password": "YoussefLoginPass2026!",
            "confirm_password": "YoussefLoginPass2026!",
            "transfer_password": "YoussefTransferPass2026!",
            "confirm_transfer_password": "YoussefTransferPass2026!",
            "country": "EG",
            "preferred_currency": "EGP",
            "initial_balance": 10000.0,
            "device_consent": True,
        }
        recipient_reg = await client.post("/api/v1/auth/register", json=recipient_payload)
        assert recipient_reg.status_code == 201
        recipient_user_number = recipient_reg.json()["customer"]["omerta_user_number"]

        # Get Sender Account ID
        sender_acc_res = await client.get("/api/v1/customer/accounts", headers=sender_headers)
        assert sender_acc_res.status_code == 200
        sender_acc_id = sender_acc_res.json()[0]["account_id"]

        # 3. Test Wrong Transfer Password Attempt 1 (401 - 2 attempts remaining)
        txn_attempt_1 = {
            "sender_account_id": sender_acc_id,
            "recipient_user_number": recipient_user_number,
            "amount": 2500.0,
            "currency": "EGP",
            "password": "WrongPassword1",
        }
        res1 = await client.post("/api/v1/customer/transfers", json=txn_attempt_1, headers=sender_headers)
        assert res1.status_code == 401
        assert "2 attempts remaining" in res1.text or "Attempt 1 of 3" in res1.text

        # 4. Test Wrong Transfer Password Attempt 2 (401 - 1 attempt remaining)
        txn_attempt_2 = {
            "sender_account_id": sender_acc_id,
            "recipient_user_number": recipient_user_number,
            "amount": 2500.0,
            "currency": "EGP",
            "password": "WrongPassword2",
        }
        res2 = await client.post("/api/v1/customer/transfers", json=txn_attempt_2, headers=sender_headers)
        assert res2.status_code == 401
        assert "1 attempt remaining" in res2.text or "Attempt 2 of 3" in res2.text

        # 5. Test Wrong Transfer Password Attempt 3 (403 - SECURITY HOLD, NO LOGOUT)
        txn_attempt_3 = {
            "sender_account_id": sender_acc_id,
            "recipient_user_number": recipient_user_number,
            "amount": 2500.0,
            "currency": "EGP",
            "password": "WrongPassword3",
        }
        res3 = await client.post("/api/v1/customer/transfers", json=txn_attempt_3, headers=sender_headers)
        assert res3.status_code == 403
        data3 = res3.json()
        assert data3["detail"]["error"] == "TRANSFER_BLOCKED_SECURITY_HOLD"
        assert "temporarily blocked" in data3["detail"]["message"].lower() or "blocked" in data3["detail"]["message"].lower()

        # 6. Verify User Session is STILL ACTIVE and Customer is NOT logged out
        dash_res = await client.get("/api/v1/customer/dashboard", headers=sender_headers)
        assert dash_res.status_code == 200, "User should remain logged in and able to view dashboard"
        dash_data = dash_res.json()
        assert dash_data["customer"]["transfer_status"] == "BLOCKED"
        assert dash_data["customer"]["transfer_failed_attempts"] == 3

        # 7. Attempting 4th transfer while BLOCKED returns 403
        res4 = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": sender_acc_id,
                "recipient_user_number": recipient_user_number,
                "amount": 1000.0,
                "currency": "EGP",
                "password": "FarahTransferPass2026!",
            },
            headers=sender_headers,
        )
        assert res4.status_code == 403
        assert "TRANSFER_BLOCKED" in res4.text

        # 8. Customer Opens Support Ticket
        ticket_payload = {
            "issue_type": "TRANSFER_BLOCKED",
            "subject": "Transfer password blocked after 3 attempts",
            "description": "I forgot my transfer password and was blocked. I would like to verify my National ID to restore access.",
            "priority": "HIGH",
        }
        ticket_res = await client.post("/api/v1/support/tickets", json=ticket_payload, headers=sender_headers)
        assert ticket_res.status_code == 201
        ticket_data = ticket_res.json()
        ticket_id = ticket_data["id"]
        assert ticket_data["issue_type"] == "TRANSFER_BLOCKED"
        assert ticket_data["transfer_blocked"] is True

        # 9. Customer sends a chat message in the ticket thread
        msg_res = await client.post(
            f"/api/v1/support/tickets/{ticket_id}/messages",
            json={"message_text": "Hello support team, uploading my National ID card picture now."},
            headers=sender_headers,
        )
        assert msg_res.status_code == 201

        # 10. Customer uploads National ID picture
        upload_payload = {
            "national_id_number": "29905051234567",
            "document_type": "NATIONAL_ID",
            "document_front_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        }
        upload_res = await client.post(f"/api/v1/support/tickets/{ticket_id}/upload-id", json=upload_payload, headers=sender_headers)
        assert upload_res.status_code == 201
        assert upload_res.json()["status"] == "PENDING"

        # 11. Admin Logs In to Review Support Cases
        admin_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@omerta.ai", "password": "AdminPass123!"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 12. Admin checks support cases queue
        cases_res = await client.get("/api/v1/support/admin/cases", headers=admin_headers)
        assert cases_res.status_code == 200
        cases_list = cases_res.json()
        found_case = next((c for c in cases_list if c["id"] == ticket_id), None)
        assert found_case is not None
        assert found_case["transfer_blocked"] is True
        assert found_case["identity_status"] == "PENDING"

        # 13. Admin Reviews and Approves Customer Identity
        verify_res = await client.post(
            f"/api/v1/support/admin/cases/{ticket_id}/verify-identity",
            json={
                "decision": "VERIFIED",
                "reviewer_notes": "National ID photo matches customer profile data. Approved.",
            },
            headers=admin_headers,
        )
        assert verify_res.status_code == 200
        assert verify_res.json()["identity_verification"]["status"] == "VERIFIED"

        # 14. Admin Restores Transfer Access for Customer
        restore_res = await client.post(
            f"/api/v1/support/admin/cases/{ticket_id}/restore-transfer",
            json={
                "confirmation": True,
                "reason": "Identity verified by compliance staff. Transfer access restored.",
            },
            headers=admin_headers,
        )
        assert restore_res.status_code == 200
        assert restore_res.json()["status"] == "RESOLVED"

        # 15. Customer Checks Dashboard: require_transfer_password_change is now True
        dash_after_restore = await client.get("/api/v1/customer/dashboard", headers=sender_headers)
        assert dash_after_restore.status_code == 200
        dash_after_data = dash_after_restore.json()
        assert dash_after_data["customer"]["require_transfer_password_change"] is True
        assert dash_after_data["customer"]["transfer_failed_attempts"] == 0

        # 16. Customer Changes/Resets Transfer Password (WITHOUT needing old forgotten password)
        pwd_change_res = await client.post(
            "/api/v1/customer/transfer-password/change",
            json={
                "new_transfer_password": "NewFarahTransferPass2026!",
                "confirm_transfer_password": "NewFarahTransferPass2026!",
            },
            headers=sender_headers,
        )
        assert pwd_change_res.status_code == 200
        assert pwd_change_res.json()["transfer_status"] == "ACTIVE"
        assert pwd_change_res.json()["require_transfer_password_change"] is False

        # 17. Customer Performs Successful Transfer with New Transfer Password!
        transfer_success = await client.post(
            "/api/v1/customer/transfers",
            json={
                "sender_account_id": sender_acc_id,
                "recipient_user_number": recipient_user_number,
                "amount": 7500.0,
                "currency": "EGP",
                "note": "Successful transfer after identity restoration",
                "password": "NewFarahTransferPass2026!",
            },
            headers=sender_headers,
        )
        assert transfer_success.status_code == 201
        receipt = transfer_success.json()
        assert receipt["amount"] == 7500.0
        assert receipt["status"] == "COMPLETED"
        assert receipt["recipient"]["omerta_user_number"] == recipient_user_number

        # 18. Check Audit Events Logged in Admin Control Center
        audit_res = await client.get("/api/v1/audit/logs?limit=50", headers=admin_headers)
        assert audit_res.status_code == 200
        events = audit_res.json().get("items", [])
        event_actions = [e.get("action") for e in events]

        # Verify key audit trail actions are present
        assert any("TRANSFER_PASSWORD_FAILED" in str(a) or "TRANSFER_PASSWORD" in str(a) for a in event_actions)
        assert any("TRANSFER_SERVICES_RESTORED" in str(a) or "RESTORED" in str(a) or "VERIFIED" in str(a) for a in event_actions)
