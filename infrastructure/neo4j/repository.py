"""Neo4j repository: all Cypher for graph investigations lives here.

Design: several small, individually bounded Cypher queries composed in the
service layer, instead of one giant query. Every query is parameterized and
scoped to the current ``projection`` namespace. MCP tools never see Cypher.
"""

from typing import Any

from infrastructure.neo4j import client as graph_client

# --- Cypher templates -------------------------------------------------------
# All templates receive :projection and are read-only MATCH/RETURN queries.

_ACCOUNT_EXISTS = (
    "MATCH (a:Account {projection: $projection, external_id: $external_id}) RETURN true AS exists"
)

_NEIGHBORS_DIRECT = (
    "MATCH (a:Account {projection: $projection, external_id: $account_id})-[r]-(n) "
    "WHERE n.projection = $projection "
    "RETURN DISTINCT labels(n)[0] AS type, "
    "coalesce(n.external_id, n.address) AS id, "
    "type(r) AS relationship, "
    "CASE WHEN startNode(r) = a THEN 'OUTGOING' ELSE 'INCOMING' END AS direction"
)

# Two-hop expansion: devices, IPs, and counterparty accounts sit one edge
# beyond the account's transactions in the projected model.
_NEIGHBORS_TWO_HOP = (
    "MATCH (a:Account {projection: $projection, external_id: $account_id})-[r1]-(m)-[r2]-(n) "
    "WHERE n.projection = $projection AND n <> a "
    "RETURN DISTINCT labels(n)[0] AS type, "
    "coalesce(n.external_id, n.address) AS id, "
    "type(r2) AS relationship, "
    "CASE WHEN startNode(r1) = a THEN 'OUTGOING' ELSE 'INCOMING' END AS direction"
)

_CONNECTED_BY_TRANSACTION = (
    "MATCH (a:Account {projection: $projection, external_id: $account_id})"
    "-[:SENT|RECEIVED_BY]-(t:Transaction)"
    "-[:SENT|RECEIVED_BY]-(other:Account) "
    "WHERE other.projection = $projection AND other <> a "
    "RETURN DISTINCT other.external_id AS account_id "
    "LIMIT $limit"
)

_CONNECTED_BY_DEVICE = (
    "MATCH (a:Account {projection: $projection, external_id: $account_id})"
    "-[:SENT]->(:Transaction)-[:USED_DEVICE]->(d:Device) "
    "WHERE d.projection = $projection "
    "MATCH (d)<-[:USED_DEVICE]-(t2:Transaction)<-[:SENT]-(other:Account) "
    "WHERE t2.projection = $projection AND other.projection = $projection "
    "AND other <> a "
    "RETURN DISTINCT other.external_id AS account_id, d.external_id AS device_id "
    "LIMIT $limit"
)

_CONNECTED_BY_IP = (
    "MATCH (a:Account {projection: $projection, external_id: $account_id})"
    "-[:SENT]->(:Transaction)-[:USED_IP]->(i:IP) "
    "WHERE i.projection = $projection "
    "MATCH (i)<-[:USED_IP]-(t2:Transaction)<-[:SENT]-(other:Account) "
    "WHERE t2.projection = $projection AND other.projection = $projection "
    "AND other <> a "
    "RETURN DISTINCT other.external_id AS account_id, i.address AS ip_address "
    "LIMIT $limit"
)

_SHARED_DEVICES = (
    "MATCH (a:Account {projection: $projection, external_id: $account_id})"
    "-[:SENT]->(:Transaction)-[:USED_DEVICE]->(d:Device) "
    "WHERE d.projection = $projection "
    "MATCH (d)<-[:USED_DEVICE]-(t2:Transaction)<-[:SENT]-(other:Account) "
    "WHERE t2.projection = $projection AND other.projection = $projection "
    "AND other <> a "
    "RETURN d.external_id AS device_id, "
    "collect(DISTINCT other.external_id) AS other_accounts "
    "ORDER BY device_id "
    "LIMIT $limit"
)

_SHARED_IPS = (
    "MATCH (a:Account {projection: $projection, external_id: $account_id})"
    "-[:SENT]->(:Transaction)-[:USED_IP]->(i:IP) "
    "WHERE i.projection = $projection "
    "MATCH (i)<-[:USED_IP]-(t2:Transaction)<-[:SENT]-(other:Account) "
    "WHERE t2.projection = $projection AND other.projection = $projection "
    "AND other <> a "
    "RETURN i.address AS ip_address, "
    "collect(DISTINCT other.external_id) AS other_accounts "
    "ORDER BY ip_address "
    "LIMIT $limit"
)

# Neo4j does not accept parameters in variable-length bounds (`[*1..$n]`), so
# the (strictly validated, small) depth is inlined via the __MAX_EDGES__ token.
_TRANSACTION_PATHS_TEMPLATE = (
    "MATCH p = (a:Account {projection: $projection, external_id: $source_account_id})"
    "-[*1..__MAX_EDGES__]-"
    "(b:Account {projection: $projection, external_id: $target_account_id}) "
    "WHERE all(n IN nodes(p) WHERE n.projection = $projection) "
    "RETURN [n IN nodes(p) | {type: labels(n)[0], id: coalesce(n.external_id, n.address)}]"
    " AS nodes, "
    "[r IN relationships(p) | type(r)] AS relationships, "
    "length(p) AS edges "
    "ORDER BY edges "
    "LIMIT $limit"
)

# Pass-through structure: the account received from one account and sent to a
# different account (funds flowed through it). Purely structural evidence.
_PASS_THROUGH = (
    "MATCH (a:Account {projection: $projection, external_id: $account_id})"
    "-[:RECEIVED_BY]-(tin:Transaction)<-[:SENT]-(sender:Account) "
    "WHERE sender.projection = $projection "
    "MATCH (a)-[:SENT]->(tout:Transaction)-[:RECEIVED_BY]->(receiver:Account) "
    "WHERE receiver.projection = $projection AND receiver <> sender "
    "RETURN sender.external_id AS from_account, "
    "tin.external_id AS in_txn, "
    "receiver.external_id AS to_account, "
    "tout.external_id AS out_txn "
    "ORDER BY in_txn "
    "LIMIT $limit"
)


async def _read(query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    params.setdefault("projection", graph_client.projection())
    return await graph_client.read_query(query, params)


async def account_exists(external_id: str) -> bool:
    rows = await _read(_ACCOUNT_EXISTS, {"external_id": external_id})
    return bool(rows)


async def account_neighbors(account_id: str, limit: int) -> list[dict[str, Any]]:
    """Direct (1-hop) neighbors merged with 2-hop devices/IPs/counterparties.

    The projected model puts transactions directly on the account; devices,
    IPs, and counterparty accounts sit one edge further. Deduplicated and
    deterministically ordered, bounded by ``limit``.
    """
    direct = await _read(_NEIGHBORS_DIRECT, {"account_id": account_id, "limit": limit * 4})
    two_hop = await _read(_NEIGHBORS_TWO_HOP, {"account_id": account_id, "limit": limit * 4})
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for row in direct + two_hop:
        key = (row["type"], row["id"])
        seen.setdefault(key, row)
    ordered = sorted(seen.values(), key=lambda row: (row["relationship"], row["id"]))
    return ordered[:limit]


async def accounts_connected_by_transaction(account_id: str, limit: int) -> list[dict[str, Any]]:
    return await _read(_CONNECTED_BY_TRANSACTION, {"account_id": account_id, "limit": limit})


async def accounts_connected_by_device(account_id: str, limit: int) -> list[dict[str, Any]]:
    return await _read(_CONNECTED_BY_DEVICE, {"account_id": account_id, "limit": limit})


async def accounts_connected_by_ip(account_id: str, limit: int) -> list[dict[str, Any]]:
    return await _read(_CONNECTED_BY_IP, {"account_id": account_id, "limit": limit})


async def shared_devices(account_id: str, limit: int) -> list[dict[str, Any]]:
    return await _read(_SHARED_DEVICES, {"account_id": account_id, "limit": limit})


async def shared_ips(account_id: str, limit: int) -> list[dict[str, Any]]:
    return await _read(_SHARED_IPS, {"account_id": account_id, "limit": limit})


async def transaction_paths(
    source_account_id: str, target_account_id: str, max_edges: int, limit: int
) -> list[dict[str, Any]]:
    """``max_edges`` must already be validated (1..10) by the service layer."""
    query = _TRANSACTION_PATHS_TEMPLATE.replace("__MAX_EDGES__", str(int(max_edges)))
    return await _read(
        query,
        {
            "source_account_id": source_account_id,
            "target_account_id": target_account_id,
            "limit": limit,
        },
    )


async def pass_through_links(account_id: str, limit: int) -> list[dict[str, Any]]:
    return await _read(_PASS_THROUGH, {"account_id": account_id, "limit": limit})
