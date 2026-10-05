"""End-to-End Test Suite for Omerta.ai Banking Intelligence Platform Foundation."""

import pytest
from httpx import ASGITransport, AsyncClient
from apps.api.main import app
from infrastructure.security.jwt_auth import create_access_token, verify_password, hash_password


@pytest.mark.asyncio
async def test_password_hashing_and_jwt_tokens():
    """Verify secure password hashing and JWT token issuance."""
    raw_pass = "SecureAnalystPassword123!"
    hashed = hash_password(raw_pass)
    assert hashed != raw_pass
    assert verify_password(raw_pass, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False

    token = create_access_token(
        user_id="USR-1001",
        username="analyst@omerta.ai",
        role="FRAUD_ANALYST",
        full_name="Tariq Mansour",
    )
    assert isinstance(token, str)
    assert len(token) > 20


@pytest.mark.asyncio
async def test_health_and_settings_endpoints():
    """Verify health and system diagnostic settings endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["service"] == "omerta-api"

        # System settings & integration diagnostics
        res_settings = await client.get("/api/v1/settings")
        assert res_settings.status_code == 200
        s_data = res_settings.json()
        assert "thresholds" in s_data
        assert s_data["thresholds"]["human_review_threshold"] == 40.0
        assert s_data["system_status"]["postgres"] in ["ok", "unreachable"]
        assert s_data["review_rule"] == "risk_score > 40.00%"


@pytest.mark.asyncio
async def test_dashboard_and_analytics_apis(seeded_db):
    """Verify dashboard summary KPIs, charts, and activity feeds."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/dashboard/summary")
        assert res.status_code == 200
        summary = res.json()
        assert "total_transactions" in summary
        assert "total_volume" in summary
        assert "transactions_requiring_review" in summary
        assert "high_risk_transactions" in summary
        assert "open_investigations" in summary
        assert "average_risk_score" in summary

        res_charts = await client.get("/api/v1/dashboard/charts")
        assert res_charts.status_code == 200
        charts = res_charts.json()
        assert "volume_trend" in charts
        assert "risk_distribution" in charts


@pytest.mark.asyncio
async def test_transactions_and_human_review_threshold(seeded_db):
    """Verify transaction querying and strict human review threshold (> 40.00%)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/transactions?page=1&page_size=10")
        assert res.status_code == 200
        txns = res.json()
        assert "items" in txns
        assert len(txns["items"]) > 0

        # Test risk monitoring queue (score > 40.00%)
        res_queue = await client.get("/api/v1/risk/monitoring?page=1&page_size=10")
        assert res_queue.status_code == 200
        queue = res_queue.json()
        assert "items" in queue
        assert queue["rule"] == "risk_score > 40.00%"
        for item in queue["items"]:
            assert item["risk_score"] > 40.0


@pytest.mark.asyncio
async def test_customer_and_account_profiles(seeded_db):
    """Verify Customer 360 and Account detail APIs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Customers list
        res_c = await client.get("/api/v1/customers?page=1&page_size=5")
        assert res_c.status_code == 200
        custs = res_c.json()
        assert "items" in custs
        assert len(custs["items"]) > 0
        first_cust = custs["items"][0]

        # Customer 360
        res_c360 = await client.get(f"/api/v1/customers/{first_cust['external_id']}")
        assert res_c360.status_code == 200
        c360 = res_c360.json()
        assert "customer" in c360
        assert "accounts" in c360

        # Accounts list
        res_a = await client.get("/api/v1/accounts?page=1&page_size=5")
        assert res_a.status_code == 200
        accs = res_a.json()
        assert len(accs["items"]) > 0
        first_acc = accs["items"][0]

        # Account detail
        res_adetail = await client.get(f"/api/v1/accounts/{first_acc['external_id']}")
        assert res_adetail.status_code == 200
        adetail = res_adetail.json()
        assert "account" in adetail


@pytest.mark.asyncio
async def test_compliance_reports_and_csv_export(seeded_db):
    """Verify reporting endpoints and CSV file generation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Types
        res_types = await client.get("/api/v1/reports/types")
        assert res_types.status_code == 200
        types = res_types.json()
        assert len(types) >= 4

        # Generate report
        res_gen = await client.get("/api/v1/reports/generate?report_type=risk-distribution")
        assert res_gen.status_code == 200
        r_data = res_gen.json()
        assert "data" in r_data

        # Export CSV
        res_exp = await client.get("/api/v1/reports/export?report_type=risk-distribution")
        assert res_exp.status_code == 200
        assert "text/csv" in res_exp.headers.get("content-type", "")
        assert "Omerta.ai Compliance Report" in res_exp.text


@pytest.mark.asyncio
async def test_audit_ledger_and_governance(seeded_db):
    """Verify chronological audit trail ledger."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_audit = await client.get("/api/v1/audit/logs?page=1&page_size=10")
        assert res_audit.status_code == 200
        audit_data = res_audit.json()
        assert "items" in audit_data
        assert "total" in audit_data
