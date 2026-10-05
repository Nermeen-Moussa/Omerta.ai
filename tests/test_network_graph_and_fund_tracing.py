"""Integration tests for Network Relationship Graph Service and Fund Tracing.

Validates:
1. Entity Search by Customer Name (e.g., Mohamed El-Sayed, Kareem Fathy), Omerta User Number, Account, Device, and IP.
2. Inflow / Fund Source Tracing ("From Where Got Money") with itemized sender list and amounts.
3. Outflow / Fund Destination Tracing ("Where Money Went") with itemized recipient list and amounts.
4. AML Risk diagnostics (pass-through velocity, shared device hopping, emulated hardware, VPN usage).
5. Network Graph API endpoint integration (`/api/v1/network/graph`).
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.main import app
from domain.services.network_graph_service import NetworkGraphService
from infrastructure.database.models import Account, Customer, Transaction, User
from infrastructure.security.jwt_auth import create_access_token


@pytest.mark.asyncio
async def test_network_graph_search_by_customer_name(db_session: AsyncSession, seeded_db):
    """Verify searching by Customer Full Name returns the customer's account and connected transactions."""
    service = NetworkGraphService(db_session)
    result = await service.get_network_graph(focus_entity_id="Mohamed El-Sayed")

    assert result["total_nodes"] > 0
    node_ids = {n["id"] for n in result["nodes"]}
    assert "ACC-0001" in node_ids

    # Check node details
    acc_node = next(n for n in result["nodes"] if n["id"] == "ACC-0001")
    assert acc_node["customer_name"] == "Mohamed El-Sayed"
    assert acc_node["type"] == "ACCOUNT"
    assert acc_node["balance"] >= 100000.0
    assert "inflow_sources" in acc_node["details"]
    assert "outflow_destinations" in acc_node["details"]


@pytest.mark.asyncio
async def test_network_graph_mule_inflow_and_outflow_fund_tracing(db_session: AsyncSession, seeded_db):
    """Verify fund tracing for Kareem Fathy shows inbound smurfing sources and outbound funneling."""
    service = NetworkGraphService(db_session)
    result = await service.get_network_graph(focus_entity_id="Kareem Fathy")

    assert result["total_nodes"] > 0
    node_ids = {n["id"] for n in result["nodes"]}
    assert "ACC-7001" in node_ids

    mule_node = next(n for n in result["nodes"] if n["id"] == "ACC-7001")
    assert mule_node["customer_name"] == "Kareem Fathy"

    # Verify Inflow sources ("From where got money")
    inflow_sources = mule_node["details"]["inflow_sources"]
    assert len(inflow_sources) >= 1
    senders = {s["sender_account"] for s in inflow_sources}
    assert "ACC-0001" in senders or "ACC-6001" in senders or "ACC-8001" in senders

    # Verify Outflow destinations ("Where money went")
    outflow_destinations = mule_node["details"]["outflow_destinations"]
    assert len(outflow_destinations) >= 1
    recipients = {d["recipient_account"] for d in outflow_destinations}
    assert "ACC-9001" in recipients

    # Verify Risk Diagnostics
    risk_factors = mule_node["details"]["risk_factors"]
    assert len(risk_factors) > 0


@pytest.mark.asyncio
async def test_network_graph_search_by_shared_device(db_session: AsyncSession, seeded_db):
    """Verify searching for shared device DEV-0098 identifies multiple co-located accounts."""
    service = NetworkGraphService(db_session)
    result = await service.get_network_graph(focus_entity_id="DEV-0098")

    assert result["total_nodes"] > 0
    dev_node = next((n for n in result["nodes"] if n["id"] == "DEV-0098"), None)
    assert dev_node is not None
    assert dev_node["type"] == "DEVICE"
    assert dev_node["risk_level"] in ("HIGH", "CRITICAL")
    assert dev_node["details"]["is_emulator"] is True or dev_node["details"]["is_rooted"] is True


@pytest.mark.asyncio
async def test_network_graph_search_by_ip_address(db_session: AsyncSession, seeded_db):
    """Verify searching by IP address returns network endpoint with VPN diagnostics."""
    service = NetworkGraphService(db_session)
    result = await service.get_network_graph(focus_entity_id="198.51.100.23")

    assert result["total_nodes"] > 0
    ip_node = next((n for n in result["nodes"] if n["id"] == "198.51.100.23"), None)
    assert ip_node is not None
    assert ip_node["type"] == "IP_ADDRESS"
    assert ip_node["details"]["is_vpn"] is True


@pytest.mark.asyncio
async def test_network_graph_api_endpoint(seeded_db):
    """Verify HTTP API GET /api/v1/network/graph with auth token returns graph payload."""
    transport = ASGITransport(app=app)
    admin_token = create_access_token(
        user_id="USR-1000",
        username="admin@omerta.ai",
        role="ADMINISTRATOR",
        full_name="Admin User",
    )

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Search without focus
        res = await client.get("/api/v1/network/graph", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert "nodes" in data
        assert "links" in data
        assert len(data["nodes"]) > 0

        # 2. Search with Customer Focus
        res_focus = await client.get(
            "/api/v1/network/graph?focus_entity_id=Mohamed+El-Sayed",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res_focus.status_code == 200
        focus_data = res_focus.json()
        assert any(n["id"] == "ACC-0001" for n in focus_data["nodes"])


@pytest.mark.asyncio
async def test_network_search_suggestions_api(seeded_db):
    """Verify live search autocomplete suggestions API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Search for "Mohamed"
        res = await client.get("/api/v1/network/search-suggestions?q=Mohamed")
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        assert any("Mohamed" in item["title"] for item in data)

        # Search for "DEV"
        res_dev = await client.get("/api/v1/network/search-suggestions?q=DEV")
        assert res_dev.status_code == 200
        dev_data = res_dev.json()
        assert any(item["type"] == "DEVICE" for item in dev_data)


@pytest.mark.asyncio
async def test_dynamic_new_user_registration_and_fund_flow_tracing(seeded_db):
    """Verify that any newly registered customer (e.g., Abdelrahman Haaland) is dynamically searchable with live money flows."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register new customer "Abdelrahman Haaland"
        reg_payload = {
            "full_name": "Abdelrahman Haaland",
            "email": "abdelrahman.haaland@test.com",
            "username": "abdo_haaland",
            "password": "SecurePass2026!",
            "confirm_password": "SecurePass2026!",
            "transfer_password": "TxSecureTransfer2026!",
            "confirm_transfer_password": "TxSecureTransfer2026!",
            "country": "EG",
            "preferred_currency": "EGP",
            "initial_balance": 95000.0,
            "device_consent": True,
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        abdo_token = reg_res.json()["access_token"]
        abdo_omerta = reg_res.json()["customer"]["omerta_user_number"]

        # 2. Get Abdelrahman's account external ID
        abdo_accs = (await client.get("/api/v1/customer/accounts", headers={"Authorization": f"Bearer {abdo_token}"})).json()
        assert len(abdo_accs) > 0
        abdo_acc_id = abdo_accs[0]["account_id"]

        # 3. Get Layla's Omerta ID to send a transfer to
        layla_login = await client.post("/api/v1/auth/login", json={"username": "layla@omerta.ai", "password": "Customer@2026!"})
        assert layla_login.status_code == 200
        layla_token = layla_login.json()["access_token"]
        layla_prof = (await client.get("/api/v1/customer/profile", headers={"Authorization": f"Bearer {layla_token}"})).json()
        layla_omerta = layla_prof["omerta_user_number"]

        # 4. Abdelrahman executes a peer transfer of 15,000 EGP to Layla
        xfer_payload = {
            "sender_account_id": abdo_acc_id,
            "recipient_identifier": layla_omerta,
            "amount": 15000.0,
            "note": "Payment for software consulting",
            "password": "TxSecureTransfer2026!",
            "idempotency_key": "idemp-abdo-haaland-9999",
        }
        xfer_res = await client.post("/api/v1/customer/transfers", json=xfer_payload, headers={"Authorization": f"Bearer {abdo_token}"})
        assert xfer_res.status_code == 201

        # 4. Investigate "Abdelrahman Haaland" in Network Graph API
        admin_token = create_access_token(user_id="USR-1000", username="admin@omerta.ai", role="ADMINISTRATOR", full_name="Admin User")
        graph_res = await client.get("/api/v1/network/graph?focus_entity_id=Abdelrahman+Haaland", headers={"Authorization": f"Bearer {admin_token}"})
        assert graph_res.status_code == 200
        graph_data = graph_res.json()

        # Abdelrahman's node must be in graph
        matched_node = next((n for n in graph_data["nodes"] if n["customer_name"] == "Abdelrahman Haaland"), None)
        assert matched_node is not None
        assert matched_node["omerta_user_number"] == abdo_omerta
        assert matched_node["balance"] == 80000.0  # 95,000 - 15,000

        # Outflow destination must show Layla
        outflows = matched_node["details"]["outflow_destinations"]
        assert len(outflows) >= 1
        assert any(o["amount"] == 15000.0 and o["recipient_name"] == "Layla Hassan" for o in outflows)

        # Inflow on Layla's node must show Abdelrahman
        layla_node = next((n for n in graph_data["nodes"] if n["customer_name"] == "Layla Hassan"), None)
        assert layla_node is not None
        layla_inflows = layla_node["details"]["inflow_sources"]
        assert any(i["amount"] == 15000.0 and i["sender_name"] == "Abdelrahman Haaland" for i in layla_inflows)

