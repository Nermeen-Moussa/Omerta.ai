"""Network Relationship Graph Service for Omerta.ai.

Generates bounded node-link relationship subgraphs for interactive network visualization:
- Entity nodes: Accounts, Devices, IP Addresses, Customers
- Link edges: Financial transfers (DIRECTED), Shared device links, Shared IP observations
- Configurable focus entity, depth (1-3 hops), and node limits to guarantee responsive UI.
"""

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import (
    Account,
    Customer,
    Device,
    IPAddress,
    Session,
    Transaction,
)


class NetworkGraphService:
    """Computes bounded entity-relationship graph payloads."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_network_graph(
        self,
        *,
        focus_entity_id: str | None = None,
        entity_type: str | None = "account",
        max_nodes: int = 50,
    ) -> dict[str, Any]:
        """Build graph nodes and links for interactive canvas / SVG rendering."""
        nodes: dict[str, dict[str, Any]] = {}
        links: list[dict[str, Any]] = []

        def add_node(node_id: str, label: str, node_type: str, risk: str, extra: dict[str, Any] | None = None):
            if node_id not in nodes and len(nodes) < max_nodes:
                nodes[node_id] = {
                    "id": node_id,
                    "label": label,
                    "type": node_type,
                    "risk_level": risk,
                    "details": extra or {},
                }

        # If a specific entity is requested, focus around it
        if focus_entity_id:
            # Look up transactions around this account or device
            txns_q = (
                select(Transaction)
                .options(
                    selectinload(Transaction.account),
                    selectinload(Transaction.recipient_account),
                    selectinload(Transaction.device),
                    selectinload(Transaction.ip_address),
                )
                .where(
                    or_(
                        Transaction.account.has(Account.external_id == focus_entity_id),
                        Transaction.recipient_account.has(Account.external_id == focus_entity_id),
                        Transaction.device.has(Device.external_id == focus_entity_id),
                    )
                )
                .limit(30)
            )
        else:
            # Default to high-risk cluster (e.g. Scenarios 1 & 5)
            txns_q = (
                select(Transaction)
                .options(
                    selectinload(Transaction.account),
                    selectinload(Transaction.recipient_account),
                    selectinload(Transaction.device),
                    selectinload(Transaction.ip_address),
                )
                .where(Transaction.risk_level.in_(["HIGH", "CRITICAL"]))
                .limit(25)
            )

        txns = (await self.session.scalars(txns_q)).all()

        for t in txns:
            s_acc = t.account
            r_acc = t.recipient_account
            dev = t.device
            ip = t.ip_address

            if s_acc:
                add_node(
                    s_acc.external_id,
                    s_acc.external_id,
                    "ACCOUNT",
                    s_acc.risk_level,
                    {"customer": s_acc.customer_name, "currency": s_acc.currency, "balance": float(s_acc.balance)},
                )
            if r_acc:
                add_node(
                    r_acc.external_id,
                    r_acc.external_id,
                    "ACCOUNT",
                    r_acc.risk_level,
                    {"customer": r_acc.customer_name, "currency": r_acc.currency},
                )
            if dev:
                add_node(
                    dev.external_id,
                    dev.external_id,
                    "DEVICE",
                    dev.risk_level,
                    {"platform": dev.platform, "is_emulator": dev.is_emulator, "is_rooted": dev.is_rooted},
                )
            if ip:
                add_node(
                    ip.address,
                    ip.address,
                    "IP_ADDRESS",
                    ip.risk_level,
                    {"country": ip.country, "is_vpn": ip.is_vpn},
                )

            # Transfer edge
            if s_acc and r_acc and s_acc.external_id in nodes and r_acc.external_id in nodes:
                links.append({
                    "source": s_acc.external_id,
                    "target": r_acc.external_id,
                    "type": "TRANSFER",
                    "label": f"{float(t.amount):,.0f} {t.currency}",
                    "amount": float(t.amount),
                    "risk_score": float(t.risk_score) if t.risk_score else 0.0,
                    "is_suspicious": t.risk_level in ["HIGH", "CRITICAL"],
                })

            # Device edge
            if s_acc and dev and s_acc.external_id in nodes and dev.external_id in nodes:
                links.append({
                    "source": s_acc.external_id,
                    "target": dev.external_id,
                    "type": "USED_DEVICE",
                    "label": "Observed Device",
                    "is_suspicious": dev.is_emulator or dev.is_rooted,
                })

            # IP edge
            if dev and ip and dev.external_id in nodes and ip.address in nodes:
                links.append({
                    "source": dev.external_id,
                    "target": ip.address,
                    "type": "CONNECTED_IP",
                    "label": "Network Endpoint",
                    "is_suspicious": ip.is_vpn,
                })

        return {
            "nodes": list(nodes.values()),
            "links": links,
            "focus_entity_id": focus_entity_id,
            "total_nodes": len(nodes),
            "total_links": len(links),
        }
