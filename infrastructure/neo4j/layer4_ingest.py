"""Layer 4 step 1: ingest ONE confirmed transaction into the relationship graph.

Uses the same schema/namespace as infrastructure.neo4j.projection so the network
graph screen shows live transfers:
    (Account)-[:SENT]->(Transaction)-[:RECEIVED_BY]->(Account)
Idempotent MERGEs. Best-effort: callers must tolerate Neo4j being down.
"""

from typing import Any

from infrastructure.neo4j import client as graph_client


async def ingest_confirmed_transaction(
    *, txn_external_id: str, sender_account_id: str, recipient_account_id: str,
    amount: float, currency: str, timestamp_iso: str, risk_score: float | None = None,
) -> dict[str, Any]:
    ns = {"projection": graph_client.projection()}
    await graph_client.write_query(
        "MERGE (a:Account {projection: $projection, external_id: $sender}) "
        "MERGE (b:Account {projection: $projection, external_id: $recipient}) "
        "MERGE (t:Transaction {projection: $projection, external_id: $txn}) "
        "SET t.amount = $amount, t.currency = $currency, t.timestamp = $ts, "
        "    t.risk_score = $risk, t.source = 'layer4_live' "
        "MERGE (a)-[:SENT]->(t) "
        "MERGE (t)-[:RECEIVED_BY]->(b)",
        {**ns, "sender": sender_account_id, "recipient": recipient_account_id,
         "txn": txn_external_id, "amount": amount, "currency": currency,
         "ts": timestamp_iso, "risk": risk_score},
    )
    return {"ingested": txn_external_id}
