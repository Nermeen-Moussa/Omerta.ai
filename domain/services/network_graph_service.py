"""Network Relationship Graph Service for Omerta.ai.

Generates dynamic entity-relationship subgraphs for interactive financial crime network visualization:
- Universal Search across any registered user/customer (by Full Name, First/Last Name, Username, Email, Omerta ID, Account Number, National ID, Phone, Device ID, or IP Address).
- Comprehensive multi-hop fund flow tracing: calculates "from where got money" (Inflows) and "where money went" (Outflows) from BOTH peer-to-peer Transfers and direct Transactions.
- Guarantees that any searched customer/account is dynamically graphed even if brand new or without previous transactions.
- Detects shared devices, emulator/rooting indicators, shared VPN/Proxy IP endpoints, and smurfing/mule syndicates.
- Provides dynamic search suggestions / autocomplete for instant customer and account lookup.
"""

from decimal import Decimal
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
    Transfer,
    User,
)


class NetworkGraphService:
    """Computes bounded entity-relationship graph payloads from database records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_search_suggestions(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return auto-complete suggestions matching Customer Name, Username, Omerta ID, Account, Device, or IP."""
        if not query or not query.strip():
            return []

        q = query.strip()
        tokens = [t for t in q.split() if len(t) > 1]
        suggestions: list[dict[str, Any]] = []
        seen_keys: set[str] = set()

        # 1. Search Customers & linked Users
        cust_filters = [
            Customer.name.ilike(f"%{q}%"),
            Customer.omerta_user_number.ilike(f"%{q}%"),
            Customer.email.ilike(f"%{q}%"),
            Customer.external_id.ilike(f"%{q}%"),
            Customer.national_id_number.ilike(f"%{q}%"),
            Customer.phone.ilike(f"%{q}%"),
        ]
        for t in tokens:
            cust_filters.append(Customer.name.ilike(f"%{t}%"))
            cust_filters.append(Customer.email.ilike(f"%{t}%"))

        cust_stmt = (
            select(Customer)
            .options(selectinload(Customer.accounts), selectinload(Customer.user))
            .where(or_(*cust_filters))
            .limit(limit)
        )
        customers = (await self.session.scalars(cust_stmt)).all()
        for c in customers:
            key = f"CUST:{c.id}"
            if key not in seen_keys:
                seen_keys.add(key)
                acc_labels = [f"{a.external_id} ({float(a.balance):,.2f} {a.currency})" for a in c.accounts]
                acc_desc = " • ".join(acc_labels) if acc_labels else "No accounts"
                suggestions.append({
                    "id": c.external_id,
                    "title": c.name,
                    "subtitle": f"Customer • {c.omerta_user_number} • {acc_desc}",
                    "type": "ACCOUNT",
                    "risk_level": c.risk_level or "LOW",
                    "query_value": c.name,
                })

        # 2. Search Users directly
        user_filters = [
            User.full_name.ilike(f"%{q}%"),
            User.username.ilike(f"%{q}%"),
            User.email.ilike(f"%{q}%"),
        ]
        for t in tokens:
            user_filters.append(User.full_name.ilike(f"%{t}%"))
            user_filters.append(User.username.ilike(f"%{t}%"))

        user_stmt = select(User).options(selectinload(User.customer)).where(or_(*user_filters)).limit(limit)
        users = (await self.session.scalars(user_stmt)).all()
        for u in users:
            c_name = u.customer.name if u.customer else u.full_name
            key = f"USER:{u.id}"
            if key not in seen_keys:
                seen_keys.add(key)
                suggestions.append({
                    "id": u.external_id,
                    "title": u.full_name,
                    "subtitle": f"User ({u.role}) • {u.email} • {u.username}",
                    "type": "ACCOUNT",
                    "risk_level": "LOW",
                    "query_value": c_name or u.full_name,
                })

        # 3. Search Accounts
        acc_stmt = (
            select(Account)
            .options(selectinload(Account.customer))
            .where(
                or_(
                    Account.external_id.ilike(f"%{q}%"),
                    Account.customer_name.ilike(f"%{q}%"),
                )
            )
            .limit(limit)
        )
        accounts = (await self.session.scalars(acc_stmt)).all()
        for acc in accounts:
            key = f"ACC:{acc.id}"
            if key not in seen_keys:
                seen_keys.add(key)
                c_name = acc.customer_name or (acc.customer.name if acc.customer else "Customer")
                suggestions.append({
                    "id": acc.external_id,
                    "title": acc.external_id,
                    "subtitle": f"Account • {c_name} • {float(acc.balance):,.2f} {acc.currency}",
                    "type": "ACCOUNT",
                    "risk_level": acc.risk_level or "LOW",
                    "query_value": acc.external_id,
                })

        # 4. Search Devices
        dev_stmt = select(Device).where(Device.external_id.ilike(f"%{q}%")).limit(limit)
        devices = (await self.session.scalars(dev_stmt)).all()
        for dev in devices:
            key = f"DEV:{dev.id}"
            if key not in seen_keys:
                seen_keys.add(key)
                suggestions.append({
                    "id": dev.external_id,
                    "title": dev.external_id,
                    "subtitle": f"Device • {dev.platform} {'[Emulated/Rooted]' if dev.is_emulator or dev.is_rooted else ''}",
                    "type": "DEVICE",
                    "risk_level": "HIGH" if (dev.is_emulator or dev.is_rooted) else (dev.risk_level or "LOW"),
                    "query_value": dev.external_id,
                })

        # 5. Search IPs
        ip_stmt = select(IPAddress).where(IPAddress.address.ilike(f"%{q}%")).limit(limit)
        ips = (await self.session.scalars(ip_stmt)).all()
        for ip in ips:
            key = f"IP:{ip.id}"
            if key not in seen_keys:
                seen_keys.add(key)
                suggestions.append({
                    "id": ip.address,
                    "title": ip.address,
                    "subtitle": f"IP Endpoint • {ip.country} {'[VPN/Proxy]' if ip.is_vpn else ''}",
                    "type": "IP_ADDRESS",
                    "risk_level": "HIGH" if ip.is_vpn else (ip.risk_level or "LOW"),
                    "query_value": ip.address,
                })

        return suggestions[:limit]

    async def get_network_graph(
        self,
        *,
        focus_entity_id: str | None = None,
        entity_type: str | None = "account",
        max_nodes: int = 50,
    ) -> dict[str, Any]:
        """Build dynamic entity-relationship graph with guaranteed customer resolution and full fund flow tracing."""
        nodes: dict[str, dict[str, Any]] = {}
        links: list[dict[str, Any]] = []

        inflows: dict[str, list[dict[str, Any]]] = {}
        outflows: dict[str, list[dict[str, Any]]] = {}
        account_devices: dict[str, list[dict[str, Any]]] = {}
        account_ips: dict[str, list[dict[str, Any]]] = {}
        device_accounts: dict[str, list[str]] = {}
        ip_accounts: dict[str, list[str]] = {}

        # 1. Resolve Focus Entity & All Matching Accounts / Customers
        target_account_ids: set[int] = set()
        target_account_exts: set[str] = set()
        target_device_ids: set[int] = set()
        target_ip_ids: set[int] = set()
        focus_meta: dict[str, Any] = {}
        matched_accounts_map: dict[str, Account] = {}

        if focus_entity_id and focus_entity_id.strip():
            query = focus_entity_id.strip()
            tokens = [t for t in query.split() if len(t) > 1]

            # A. Search Customers
            cust_filters = [
                Customer.name.ilike(f"%{query}%"),
                Customer.omerta_user_number.ilike(f"%{query}%"),
                Customer.email.ilike(f"%{query}%"),
                Customer.external_id.ilike(f"%{query}%"),
                Customer.national_id_number.ilike(f"%{query}%"),
                Customer.phone.ilike(f"%{query}%"),
            ]
            for t in tokens:
                cust_filters.append(Customer.name.ilike(f"%{t}%"))
                cust_filters.append(Customer.email.ilike(f"%{t}%"))

            cust_stmt = (
                select(Customer)
                .options(selectinload(Customer.accounts))
                .where(or_(*cust_filters))
            )
            matched_customers = (await self.session.scalars(cust_stmt)).all()
            for c in matched_customers:
                focus_meta["customer_name"] = c.name
                focus_meta["omerta_user_number"] = c.omerta_user_number
                for acc in c.accounts:
                    target_account_ids.add(acc.id)
                    target_account_exts.add(acc.external_id)
                    matched_accounts_map[acc.external_id] = acc

            # B. Search Users
            user_filters = [
                User.full_name.ilike(f"%{query}%"),
                User.username.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%"),
            ]
            for t in tokens:
                user_filters.append(User.full_name.ilike(f"%{t}%"))
                user_filters.append(User.username.ilike(f"%{t}%"))

            user_stmt = (
                select(User)
                .options(selectinload(User.customer).selectinload(Customer.accounts))
                .where(or_(*user_filters))
            )
            matched_users = (await self.session.scalars(user_stmt)).all()
            for u in matched_users:
                if u.customer:
                    focus_meta["customer_name"] = u.customer.name
                    focus_meta["omerta_user_number"] = u.customer.omerta_user_number
                    for acc in u.customer.accounts:
                        target_account_ids.add(acc.id)
                        target_account_exts.add(acc.external_id)
                        matched_accounts_map[acc.external_id] = acc

            # C. Search Accounts Directly
            acc_filters = [
                Account.external_id.ilike(f"%{query}%"),
                Account.customer_name.ilike(f"%{query}%"),
            ]
            for t in tokens:
                acc_filters.append(Account.customer_name.ilike(f"%{t}%"))

            acc_stmt = (
                select(Account)
                .options(selectinload(Account.customer))
                .where(or_(*acc_filters))
            )
            matched_accounts = (await self.session.scalars(acc_stmt)).all()
            for acc in matched_accounts:
                target_account_ids.add(acc.id)
                target_account_exts.add(acc.external_id)
                matched_accounts_map[acc.external_id] = acc
                if acc.customer:
                    focus_meta["customer_name"] = acc.customer.name
                    focus_meta["omerta_user_number"] = acc.customer.omerta_user_number

            # D. Search Devices
            dev_stmt = select(Device).where(Device.external_id.ilike(f"%{query}%"))
            matched_devices = (await self.session.scalars(dev_stmt)).all()
            for d in matched_devices:
                target_device_ids.add(d.id)

            # E. Search IPs
            ip_stmt = select(IPAddress).where(IPAddress.address.ilike(f"%{query}%"))
            matched_ips = (await self.session.scalars(ip_stmt)).all()
            for ip in matched_ips:
                target_ip_ids.add(ip.id)

        # 2. Query Sessions to link Accounts with Devices & IPs
        sessions_stmt = select(Session).options(
            selectinload(Session.account),
            selectinload(Session.device),
            selectinload(Session.ip_address),
        )
        sessions = (await self.session.scalars(sessions_stmt)).all()
        for s in sessions:
            if s.account and s.device:
                acc_ext = s.account.external_id
                dev_ext = s.device.external_id
                account_devices.setdefault(acc_ext, []).append({
                    "device_id": dev_ext,
                    "platform": s.device.platform,
                    "is_emulator": s.device.is_emulator,
                    "is_rooted": s.device.is_rooted,
                    "risk_level": s.device.risk_level,
                })
                device_accounts.setdefault(dev_ext, []).append(acc_ext)

            if s.account and s.ip_address:
                acc_ext = s.account.external_id
                ip_addr = s.ip_address.address
                account_ips.setdefault(acc_ext, []).append({
                    "ip_address": ip_addr,
                    "country": s.ip_address.country,
                    "is_vpn": s.ip_address.is_vpn,
                    "risk_level": s.ip_address.risk_level,
                })
                ip_accounts.setdefault(ip_addr, []).append(acc_ext)

        # 3. Query Transfers (Customer peer-to-peer transfers)
        transfers_stmt = (
            select(Transfer)
            .options(
                selectinload(Transfer.sender_account).selectinload(Account.customer),
                selectinload(Transfer.recipient_account).selectinload(Account.customer),
                selectinload(Transfer.sender_customer),
                selectinload(Transfer.recipient_customer),
                selectinload(Transfer.transaction),
            )
            .order_by(Transfer.created_at.desc())
        )
        all_transfers = (await self.session.scalars(transfers_stmt)).all()

        # 4. Query Transactions (Direct banking ledger transactions)
        txns_stmt = (
            select(Transaction)
            .options(
                selectinload(Transaction.account).selectinload(Account.customer),
                selectinload(Transaction.recipient_account).selectinload(Account.customer),
                selectinload(Transaction.device),
                selectinload(Transaction.ip_address),
            )
            .order_by(Transaction.timestamp.desc())
        )
        all_txns = (await self.session.scalars(txns_stmt)).all()

        # Filter relevant activities
        is_filtered = bool(target_account_ids or target_device_ids or target_ip_ids)
        active_transfers: list[Transfer] = []
        active_txns: list[Transaction] = []

        if is_filtered:
            # First hop transfers
            for tr in all_transfers:
                if tr.sender_account_id in target_account_ids or tr.recipient_account_id in target_account_ids:
                    active_transfers.append(tr)

            # First hop transactions
            for tx in all_txns:
                if (
                    tx.account_id in target_account_ids
                    or tx.recipient_account_id in target_account_ids
                    or tx.device_id in target_device_ids
                    or tx.ip_address_id in target_ip_ids
                ):
                    active_txns.append(tx)

            # Discovered counterparty accounts
            discovered_acc_ids = set(target_account_ids)
            for tr in active_transfers:
                if tr.sender_account_id:
                    discovered_acc_ids.add(tr.sender_account_id)
                if tr.recipient_account_id:
                    discovered_acc_ids.add(tr.recipient_account_id)
            for tx in active_txns:
                if tx.account_id:
                    discovered_acc_ids.add(tx.account_id)
                if tx.recipient_account_id:
                    discovered_acc_ids.add(tx.recipient_account_id)

            # Second hop: connect discovered counterparties
            for tr in all_transfers:
                if tr not in active_transfers and (
                    tr.sender_account_id in discovered_acc_ids and tr.recipient_account_id in discovered_acc_ids
                ):
                    active_transfers.append(tr)

            for tx in all_txns:
                if tx not in active_txns and (
                    tx.account_id in discovered_acc_ids and tx.recipient_account_id in discovered_acc_ids
                ):
                    active_txns.append(tx)
        else:
            active_transfers = all_transfers[:max_nodes]
            active_txns = all_txns[:max_nodes]

        # 5. Helper function to safely register or update graph nodes
        def register_account_node(acc: Account, extra_risk_level: str | None = None):
            if not acc:
                return
            acc_ext = acc.external_id
            c_name = acc.customer_name or (acc.customer.name if acc.customer else "Customer")
            omerta_id = acc.customer.omerta_user_number if acc.customer else "N/A"
            bal = float(acc.balance)

            if acc_ext not in nodes:
                nodes[acc_ext] = {
                    "id": acc_ext,
                    "label": f"{acc_ext}\n({c_name})",
                    "type": "ACCOUNT",
                    "risk_level": extra_risk_level or acc.risk_level or "LOW",
                    "risk_score": 10.0,
                    "customer_name": c_name,
                    "omerta_user_number": omerta_id,
                    "balance": bal,
                    "currency": acc.currency,
                    "details": {
                        "customer": c_name,
                        "omerta_id": omerta_id,
                        "balance": bal,
                        "currency": acc.currency,
                        "status": acc.status,
                        "inflow_total": 0.0,
                        "inflow_count": 0,
                        "inflow_sources": [],
                        "outflow_total": 0.0,
                        "outflow_count": 0,
                        "outflow_destinations": [],
                        "net_flow": 0.0,
                        "shared_devices": account_devices.get(acc_ext, []),
                        "shared_ips": account_ips.get(acc_ext, []),
                        "risk_factors": [],
                    },
                }

        # Guaranteed inclusion: register all searched target accounts immediately
        for acc in matched_accounts_map.values():
            register_account_node(acc)

        # Ingest Transfers into Inflows & Outflows
        seen_transfer_keys = set()
        for tr in active_transfers:
            s_acc = tr.sender_account
            r_acc = tr.recipient_account
            amt = float(tr.amount)
            ts = tr.created_at.isoformat() if tr.created_at else ""

            if s_acc:
                register_account_node(s_acc)
            if r_acc:
                register_account_node(r_acc)

            if s_acc and r_acc:
                s_ext = s_acc.external_id
                r_ext = r_acc.external_id
                s_name = s_acc.customer_name or (tr.sender_customer.name if tr.sender_customer else "Unknown")
                r_name = r_acc.customer_name or (tr.recipient_customer.name if tr.recipient_customer else "Unknown")

                # Record Outflow for Sender
                outflows.setdefault(s_ext, []).append({
                    "recipient_name": r_name,
                    "recipient_account": r_ext,
                    "amount": amt,
                    "currency": tr.currency,
                    "timestamp": ts,
                    "status": tr.status,
                    "note": tr.note or "Peer Transfer",
                    "risk_score": 15.0,
                    "risk_level": "LOW",
                })

                # Record Inflow for Recipient ("From Where Got Money")
                inflows.setdefault(r_ext, []).append({
                    "sender_name": s_name,
                    "sender_account": s_ext,
                    "amount": amt,
                    "currency": tr.currency,
                    "timestamp": ts,
                    "status": tr.status,
                    "note": tr.note or "Peer Transfer",
                    "risk_score": 15.0,
                    "risk_level": "LOW",
                })

                # Add Graph Link
                link_key = f"TRANSFER:{s_ext}->{r_ext}:{tr.external_id}"
                if link_key not in seen_transfer_keys:
                    seen_transfer_keys.add(link_key)
                    links.append({
                        "source": s_ext,
                        "target": r_ext,
                        "type": "TRANSFER",
                        "label": f"{amt:,.0f} {tr.currency}",
                        "amount": amt,
                        "currency": tr.currency,
                        "risk_score": 15.0,
                        "is_suspicious": False,
                        "timestamp": ts,
                    })

        # Ingest Transactions into Inflows & Outflows
        for tx in active_txns:
            s_acc = tx.account
            r_acc = tx.recipient_account
            dev = tx.device
            ip = tx.ip_address
            amt = float(tx.amount)
            r_score = float(tx.risk_score) if tx.risk_score else 0.0
            ts = tx.timestamp.isoformat() if tx.timestamp else ""
            is_susp = (tx.risk_level in ("HIGH", "CRITICAL")) or (r_score > 40.0)

            if s_acc:
                register_account_node(s_acc, tx.risk_level if is_susp else None)
            if r_acc:
                register_account_node(r_acc, tx.risk_level if is_susp else None)

            if s_acc and r_acc:
                s_ext = s_acc.external_id
                r_ext = r_acc.external_id
                s_name = s_acc.customer_name or (s_acc.customer.name if s_acc.customer else "Unknown")
                r_name = r_acc.customer_name or (r_acc.customer.name if r_acc.customer else "Unknown")

                # De-duplicate if already recorded via Transfer
                already_in_outflows = any(
                    x["recipient_account"] == r_ext and abs(x["amount"] - amt) < 0.01 for x in outflows.get(s_ext, [])
                )
                if not already_in_outflows:
                    outflows.setdefault(s_ext, []).append({
                        "recipient_name": r_name,
                        "recipient_account": r_ext,
                        "amount": amt,
                        "currency": tx.currency,
                        "timestamp": ts,
                        "risk_score": r_score,
                        "risk_level": tx.risk_level,
                    })

                    inflows.setdefault(r_ext, []).append({
                        "sender_name": s_name,
                        "sender_account": s_ext,
                        "amount": amt,
                        "currency": tx.currency,
                        "timestamp": ts,
                        "risk_score": r_score,
                        "risk_level": tx.risk_level,
                    })

                    link_key = f"TXN:{s_ext}->{r_ext}:{tx.id}"
                    if link_key not in seen_transfer_keys:
                        seen_transfer_keys.add(link_key)
                        links.append({
                            "source": s_ext,
                            "target": r_ext,
                            "type": "TRANSFER",
                            "label": f"{amt:,.0f} {tx.currency}",
                            "amount": amt,
                            "currency": tx.currency,
                            "risk_score": r_score,
                            "is_suspicious": is_susp,
                            "timestamp": ts,
                        })

        # Ingest Sessions for all active accounts into nodes and links (Device & IP bindings)
        for s in sessions:
            acc = s.account
            dev = s.device
            ip = s.ip_address

            if acc and acc.external_id in nodes:
                acc_ext = acc.external_id

                # Record Device node & edge
                if dev:
                    dev_ext = dev.external_id
                    linked_accs = device_accounts.get(dev_ext, [])
                    d_risk = "CRITICAL" if len(set(linked_accs)) >= 3 else ("HIGH" if (dev.is_emulator or dev.is_rooted or len(set(linked_accs)) > 1) else dev.risk_level)
                    if dev_ext not in nodes:
                        nodes[dev_ext] = {
                            "id": dev_ext,
                            "label": f"{dev_ext}\n({dev.platform})",
                            "type": "DEVICE",
                            "risk_level": d_risk,
                            "risk_score": 90.0 if d_risk == "CRITICAL" else (80.0 if d_risk == "HIGH" else 15.0),
                            "details": {
                                "device_id": dev_ext,
                                "platform": dev.platform,
                                "is_emulator": dev.is_emulator,
                                "is_rooted": dev.is_rooted,
                                "linked_accounts": list(set(linked_accs)),
                            },
                        }
                    link_key = f"DEVICE:{acc_ext}->{dev_ext}"
                    if link_key not in seen_transfer_keys:
                        seen_transfer_keys.add(link_key)
                        links.append({
                            "source": acc_ext,
                            "target": dev_ext,
                            "type": "USED_DEVICE",
                            "label": f"Shared Device ({len(set(linked_accs))} Accounts)" if len(set(linked_accs)) > 1 else "Observed Device",
                            "is_suspicious": dev.is_emulator or dev.is_rooted or len(set(linked_accs)) > 1,
                        })

                # Record IP node & edge
                if ip:
                    ip_addr = ip.address
                    linked_accs = ip_accounts.get(ip_addr, [])
                    ip_risk = "HIGH" if (ip.is_vpn or ip.is_datacenter) else ip.risk_level
                    if ip_addr not in nodes:
                        nodes[ip_addr] = {
                            "id": ip_addr,
                            "label": ip_addr,
                            "type": "IP_ADDRESS",
                            "risk_level": ip_risk,
                            "risk_score": 75.0 if ip_risk in ("HIGH", "CRITICAL") else 10.0,
                            "details": {
                                "ip_address": ip_addr,
                                "country": ip.country,
                                "is_vpn": ip.is_vpn,
                                "is_datacenter": ip.is_datacenter,
                                "linked_accounts": list(set(linked_accs)),
                            },
                        }
                    if dev and dev.external_id in nodes:
                        link_key = f"IP:{dev.external_id}->{ip_addr}"
                        if link_key not in seen_transfer_keys:
                            seen_transfer_keys.add(link_key)
                            links.append({
                                "source": dev.external_id,
                                "target": ip_addr,
                                "type": "CONNECTED_IP",
                                "label": "VPN Endpoint" if ip.is_vpn else "Network Endpoint",
                                "is_suspicious": ip.is_vpn,
                            })

        # 6. Recompute Node Risk Factors, Total Inflow, Total Outflow, and AML Diagnostics
        for n_id, n_obj in nodes.items():
            if n_obj["type"] == "ACCOUNT":
                n_in = inflows.get(n_id, [])
                n_out = outflows.get(n_id, [])
                in_sum = sum(x["amount"] for x in n_in)
                out_sum = sum(x["amount"] for x in n_out)

                risk_factors: list[str] = []
                current_risk = n_obj["risk_level"]

                # A. Rapid Pass-Through Mule Velocity (Inbound received & immediately outbound dispatched)
                if in_sum > 0 and out_sum > 0:
                    pass_ratio = min(in_sum, out_sum) / max(in_sum, out_sum, 1.0)
                    if pass_ratio > 0.65 and in_sum >= 2000:
                        current_risk = "CRITICAL"
                        risk_factors.append(f"Rapid pass-through mule velocity ({pass_ratio * 100:.0f}% fund fan-out)")

                # B. Structuring / Smurfing Collector Node (Multiple feeders)
                if in_sum >= 4000 and len(n_in) >= 2:
                    current_risk = "CRITICAL"
                    risk_factors.append(f"Structuring aggregation node: {len(n_in)} inbound feeder transfers ({in_sum:,.2f} EGP)")

                # C. Check shared hardware device hopping (Multi-account co-location)
                s_devs = account_devices.get(n_id, [])
                for d_info in s_devs:
                    other_accs = [a for a in device_accounts.get(d_info["device_id"], []) if a != n_id]
                    if len(other_accs) >= 2:
                        current_risk = "CRITICAL"
                        risk_factors.append(f"Multi-account hardware co-location: device {d_info['device_id']} shared with {len(other_accs)} other accounts ({', '.join(other_accs)})")
                    elif len(other_accs) == 1:
                        if current_risk == "LOW":
                            current_risk = "HIGH"
                        risk_factors.append(f"Shared hardware device {d_info['device_id']} co-located with account {other_accs[0]}")
                    if d_info.get("is_emulator") or d_info.get("is_rooted"):
                        current_risk = "CRITICAL"
                        risk_factors.append(f"Emulated/Rooted hardware detected ({d_info['device_id']})")

                # D. Check VPN / Datacenter Proxy Usage
                s_ips = account_ips.get(n_id, [])
                for ip_info in s_ips:
                    if ip_info.get("is_vpn"):
                        risk_factors.append(f"Accessed via VPN/Datacenter proxy ({ip_info['ip_address']})")
                        if current_risk == "LOW":
                            current_risk = "HIGH"

                n_obj["risk_level"] = current_risk
                n_obj["inflow_total"] = in_sum
                n_obj["inflow_count"] = len(n_in)
                n_obj["inflow_sources"] = n_in
                n_obj["outflow_total"] = out_sum
                n_obj["outflow_count"] = len(n_out)
                n_obj["outflow_destinations"] = n_out
                n_obj["net_flow"] = in_sum - out_sum

                # Synchronize inside details dictionary
                det = n_obj["details"]
                det["inflow_total"] = in_sum
                det["inflow_count"] = len(n_in)
                det["inflow_sources"] = n_in
                det["outflow_total"] = out_sum
                det["outflow_count"] = len(n_out)
                det["outflow_destinations"] = n_out
                det["net_flow"] = in_sum - out_sum
                det["risk_factors"] = risk_factors

        return {
            "nodes": list(nodes.values()),
            "links": links,
            "focus_entity_id": focus_entity_id,
            "focus_meta": focus_meta,
            "total_nodes": len(nodes),
            "total_links": len(links),
        }
