"""Graph service tests against the seeded test projection.

Validates evidence-shaped outputs (never fraud verdicts), bounded traversals,
deterministic ordering, and structured errors - mirroring the Phase 5 suite.
"""

import pytest
from domain.errors import NotFoundError, ValidationError
from domain.services.graph_service import MAX_DEPTH, GraphService
from infrastructure.database.seed import SAFE_DOC_IP

pytestmark = pytest.mark.graph


def _run(coro_fn):
    from tests.conftest import run_with_graph

    return run_with_graph(coro_fn)


def test_get_account_neighbors(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().get_account_neighbors("ACC-1001")

    result = _run(_call)
    assert result.account_id == "ACC-1001"
    assert result.count == len(result.neighbors)
    ids = {n.id for n in result.neighbors}
    assert "TXN-001" in ids and "DEV-123" in ids and SAFE_DOC_IP in ids
    assert any(n.type == "ACCOUNT" for n in result.neighbors)
    assert all(n.relationship for n in result.neighbors)


def test_get_account_neighbors_nonexistent(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().get_account_neighbors("ACC-999")

    try:
        _run(_call)
        raised = None
    except NotFoundError as exc:
        raised = exc
    assert raised is not None
    assert raised.payload["resource"] == "account"


def test_find_connected_accounts_with_reasons(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().find_connected_accounts("ACC-1001")

    result = _run(_call)
    pairs = {(c.account_id, c.via) for c in result.connections}
    # Direct transaction counterparties from the seed:
    assert ("ACC-9001", "DIRECT_TRANSACTION") in pairs
    assert ("ACC-3001", "DIRECT_TRANSACTION") in pairs
    assert ("ACC-2001", "DIRECT_TRANSACTION") in pairs
    # Shared infrastructure with ACC-3001 via TXN-1006:
    assert ("ACC-3001", "SHARED_DEVICE") in pairs
    assert ("ACC-3001", "SHARED_IP") in pairs
    # Every shared connection names its entity:
    for conn in result.connections:
        if conn.via in {"SHARED_DEVICE", "SHARED_IP"}:
            assert conn.via_entity


def test_find_connected_accounts_limit(graph_seeded: None) -> None:
    async def _full():
        return await GraphService().find_connected_accounts("ACC-1001")

    async def _limited():
        return await GraphService().find_connected_accounts("ACC-1001", limit=3)

    full = _run(_full)
    limited = _run(_limited)
    assert limited.count == 3
    assert {c.account_id for c in limited.connections}.issubset(
        {c.account_id for c in full.connections}
    )


def test_find_connected_accounts_nonexistent(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().find_connected_accounts("ACC-999")

    try:
        _run(_call)
        ok = False
    except NotFoundError:
        ok = True
    assert ok


def test_find_shared_devices_seed_scenario(graph_seeded: None) -> None:
    """DEV-123 is shared between ACC-1001 and ACC-3001."""

    async def _call():
        return await GraphService().find_shared_devices("ACC-1001")

    result = _run(_call)
    by_device = {d.device_id: d.other_accounts for d in result.shared_devices}
    assert by_device["DEV-123"] == ["ACC-3001"]


def test_find_shared_ips_seed_scenario(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().find_shared_ips("ACC-1001")

    result = _run(_call)
    by_ip = {i.ip_address: i.other_accounts for i in result.shared_ips}
    assert by_ip[SAFE_DOC_IP] == ["ACC-3001"]  # shared with ACC-3001 via TXN-1006


def test_find_shared_devices_nonexistent(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().find_shared_devices("DEV-999")

    try:
        _run(_call)
        ok = False
    except NotFoundError:
        ok = True
    assert ok


def test_find_transaction_paths_direct(graph_seeded: None) -> None:
    """ACC-1001 -> ACC-9001 has a direct 2-edge path via TXN-001."""

    async def _call():
        return await GraphService().find_transaction_paths("ACC-1001", "ACC-9001")

    result = _run(_call)
    assert result.count >= 1
    first = result.paths[0]  # ordered by edge count
    assert first.edges == 2
    assert [n.id for n in first.nodes] == ["ACC-1001", "TXN-001", "ACC-9001"]
    assert first.relationships == ["SENT", "RECEIVED_BY"]


def test_find_transaction_paths_multi_hop(graph_seeded: None) -> None:
    """A known multi-hop path: ACC-1001 -> ACC-3001 -> ACC-9001."""

    async def _call():
        return await GraphService().find_transaction_paths("ACC-1001", "ACC-3001")

    result = _run(_call)
    assert result.count >= 1
    direct = result.paths[0]
    assert direct.edges == 2
    assert {n.id for n in direct.nodes} == {"ACC-1001", "TXN-1001", "ACC-3001"}


def test_find_transaction_paths_depth_validation(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().find_transaction_paths(
            "ACC-1001", "ACC-9001", max_depth=MAX_DEPTH + 1
        )

    try:
        _run(_call)
        ok = False
    except ValidationError as exc:
        ok = exc.payload.get("field") == "max_depth"
    assert ok


def test_find_transaction_paths_nonexistent(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().find_transaction_paths("ACC-1001", "ACC-999")

    try:
        _run(_call)
        ok = False
    except NotFoundError:
        ok = True
    assert ok


def test_find_fraud_ring_signals_not_verdicts(graph_seeded: None) -> None:
    """ACC-9001 exhibits shared-infra and pass-through structure in the seed."""

    async def _call():
        return await GraphService().find_fraud_ring("ACC-9001")

    result = _run(_call)
    types = {s.type for s in result.signals}
    assert "SHARED_DEVICE" in types  # DEV-789 shared with ACC-4001
    assert "SHARED_IP" in types  # 198.51.100.23 shared with ACC-4001/ACC-1001
    assert "PASS_THROUGH" in types  # received from ACC-1001/ACC-3001, sent to ACC-4001
    for signal in result.signals:
        assert signal.connected_accounts
        assert signal.description
    # Explicit non-verdict provenance:
    assert "not a fraud determination" in result.note


def test_find_fraud_ring_nonexistent(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().find_fraud_ring("ACC-999")

    try:
        _run(_call)
        ok = False
    except NotFoundError:
        ok = True
    assert ok


def test_find_fraud_ring_depth_validation(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().find_fraud_ring("ACC-1001", max_depth=0)

    try:
        _run(_call)
        ok = False
    except ValidationError as exc:
        ok = exc.payload.get("field") == "max_depth"
    assert ok


def test_empty_account_id_is_validation_error(graph_seeded: None) -> None:
    async def _call():
        return await GraphService().get_account_neighbors("   ")

    try:
        _run(_call)
        ok = False
    except ValidationError as exc:
        ok = exc.payload.get("field") == "account_id"
    assert ok
