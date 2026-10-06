"""Graph service: business layer between graph MCP tools and the Neo4j repository.

Responsibilities:
- validate inputs (ids, limits, depths) with the same rules as Phase 5,
- verify the account exists (structured NOT_FOUND otherwise),
- compose small repository queries into evidence-shaped responses,
- never emit fraud verdicts - only structural signals for the future agent.
"""

from infrastructure.neo4j import repository as graph_repository

from domain import schemas
from domain.errors import NotFoundError, ValidationError
from domain.services.transaction_service import validate_external_id, validate_limit

# Limits: identical philosophy to Phase 5 (bounded, deterministic).
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MIN_LIMIT = 1

# Traversal safety: paths and ring analysis are depth-bounded.
DEFAULT_MAX_DEPTH = 2
MAX_DEPTH = 5
MIN_DEPTH = 1
# Graph edges per hop in the property graph: Account-Transaction-Account is
# two edges, so a logical depth of N translates to 2N edges for paths.
_EDGES_PER_HOP = 2


def validate_depth(value: int | None, *, default: int = DEFAULT_MAX_DEPTH) -> int:
    """Validate a traversal depth (1..MAX_DEPTH)."""
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("max_depth must be an integer", field="max_depth")
    if value < MIN_DEPTH:
        raise ValidationError(
            f"max_depth must be between {MIN_DEPTH} and {MAX_DEPTH}",
            field="max_depth",
            value=value,
        )
    if value > MAX_DEPTH:
        raise ValidationError(
            f"max_depth must be between {MIN_DEPTH} and {MAX_DEPTH}",
            field="max_depth",
            value=value,
        )
    return value


def _split_page(rows: list, limit: int) -> tuple[list, bool]:
    return rows[:limit], len(rows) > limit


async def _account_exists_in_graph(account_id: str) -> bool:
    return await graph_repository.account_exists(account_id)


class GraphService:
    """Relationship intelligence over the projected graph (read-only)."""

    # ------------------------------------------------------------------ #
    # get_account_neighbors
    # ------------------------------------------------------------------ #
    async def get_account_neighbors(
        self, account_id: str, limit: int | None = None
    ) -> schemas.AccountNeighbors:
        acct_id = validate_external_id(account_id, field="account_id")
        validated_limit = validate_limit(limit)
        if not await _account_exists_in_graph(acct_id):
            raise NotFoundError("account", acct_id)
        rows = await graph_repository.account_neighbors(acct_id, validated_limit + 1)
        page, truncated = _split_page(rows, validated_limit)
        neighbors = [
            schemas.Neighbor(
                type=row["type"].upper(),
                id=row["id"],
                relationship=row["relationship"],
                direction=row["direction"],
            )
            for row in page
        ]
        return schemas.AccountNeighbors(
            account_id=acct_id, neighbors=neighbors, count=len(neighbors), truncated=truncated
        )

    # ------------------------------------------------------------------ #
    # find_connected_accounts
    # ------------------------------------------------------------------ #
    async def find_connected_accounts(
        self, account_id: str, limit: int | None = None
    ) -> schemas.ConnectedAccounts:
        acct_id = validate_external_id(account_id, field="account_id")
        validated_limit = validate_limit(limit)
        if not await _account_exists_in_graph(acct_id):
            raise NotFoundError("account", acct_id)

        connections: list[schemas.Connection] = []
        # Each source is a separate bounded query; each carries the reason.
        by_txn = await graph_repository.accounts_connected_by_transaction(acct_id, validated_limit)
        connections += [
            schemas.Connection(
                account_id=r["account_id"], via="DIRECT_TRANSACTION", via_entity=None
            )
            for r in by_txn
        ]
        by_device = await graph_repository.accounts_connected_by_device(acct_id, validated_limit)
        connections += [
            schemas.Connection(
                account_id=r["account_id"], via="SHARED_DEVICE", via_entity=r["device_id"]
            )
            for r in by_device
        ]
        by_ip = await graph_repository.accounts_connected_by_ip(acct_id, validated_limit)
        connections += [
            schemas.Connection(
                account_id=r["account_id"], via="SHARED_IP", via_entity=r["ip_address"]
            )
            for r in by_ip
        ]

        # Deduplicate but keep all distinct reasons.
        seen: dict[tuple[str, str, str | None], schemas.Connection] = {}
        for conn in connections:
            key = (conn.account_id, conn.via, conn.via_entity)
            seen.setdefault(key, conn)
        unique = list(seen.values())[:validated_limit]
        return schemas.ConnectedAccounts(
            account_id=acct_id,
            connections=unique,
            count=len(unique),
            truncated=len(seen) > len(unique),
        )

    # ------------------------------------------------------------------ #
    # find_shared_devices
    # ------------------------------------------------------------------ #
    async def find_shared_devices(
        self, account_id: str, limit: int | None = None
    ) -> schemas.SharedDevices:
        acct_id = validate_external_id(account_id, field="account_id")
        validated_limit = validate_limit(limit)
        if not await _account_exists_in_graph(acct_id):
            raise NotFoundError("account", acct_id)
        rows = await graph_repository.shared_devices(acct_id, validated_limit)
        devices = [
            schemas.SharedDevice(device_id=r["device_id"], other_accounts=r["other_accounts"])
            for r in rows
        ]
        return schemas.SharedDevices(account_id=acct_id, shared_devices=devices, count=len(devices))

    # ------------------------------------------------------------------ #
    # find_shared_ips
    # ------------------------------------------------------------------ #
    async def find_shared_ips(self, account_id: str, limit: int | None = None) -> schemas.SharedIPs:
        acct_id = validate_external_id(account_id, field="account_id")
        validated_limit = validate_limit(limit)
        if not await _account_exists_in_graph(acct_id):
            raise NotFoundError("account", acct_id)
        rows = await graph_repository.shared_ips(acct_id, validated_limit)
        ips = [
            schemas.SharedIP(ip_address=r["ip_address"], other_accounts=r["other_accounts"])
            for r in rows
        ]
        return schemas.SharedIPs(account_id=acct_id, shared_ips=ips, count=len(ips))

    # ------------------------------------------------------------------ #
    # find_transaction_paths
    # ------------------------------------------------------------------ #
    async def find_transaction_paths(
        self,
        source_account_id: str,
        target_account_id: str,
        max_depth: int | None = None,
        limit: int | None = None,
    ) -> schemas.TransactionPaths:
        source_id = validate_external_id(source_account_id, field="source_account_id")
        target_id = validate_external_id(target_account_id, field="target_account_id")
        depth = validate_depth(max_depth)
        validated_limit = validate_limit(limit)
        for acct in (source_id, target_id):
            if not await _account_exists_in_graph(acct):
                raise NotFoundError("account", acct)

        rows = await graph_repository.transaction_paths(
            source_id, target_id, max_edges=depth * _EDGES_PER_HOP, limit=validated_limit
        )
        paths = [
            schemas.GraphPath(
                nodes=[schemas.PathNode(type=n["type"].upper(), id=n["id"]) for n in row["nodes"]],
                relationships=row["relationships"],
                edges=row["edges"],
            )
            for row in rows
        ]
        return schemas.TransactionPaths(
            source_account_id=source_id,
            target_account_id=target_id,
            paths=paths,
            count=len(paths),
        )

    # ------------------------------------------------------------------ #
    # find_fraud_ring (evidence/signal analysis - never a verdict)
    # ------------------------------------------------------------------ #
    async def find_fraud_ring(
        self,
        account_id: str,
        max_depth: int | None = None,
        limit: int | None = None,
    ) -> schemas.FraudSignals:
        acct_id = validate_external_id(account_id, field="account_id")
        depth = validate_depth(max_depth)
        validated_limit = validate_limit(limit)
        if not await _account_exists_in_graph(acct_id):
            raise NotFoundError("account", acct_id)

        signals: list[schemas.FraudSignal] = []

        # Signal 1: shared devices with multiple accounts.
        for row in await graph_repository.shared_devices(acct_id, validated_limit):
            if len(row["other_accounts"]) >= 1:
                signals.append(
                    schemas.FraudSignal(
                        type="SHARED_DEVICE",
                        entity_id=row["device_id"],
                        connected_accounts=row["other_accounts"],
                        description=(
                            f"Device {row['device_id']} is used by this account and "
                            f"{len(row['other_accounts'])} other account(s)"
                        ),
                    )
                )

        # Signal 2: shared IPs with multiple accounts.
        for row in await graph_repository.shared_ips(acct_id, validated_limit):
            if len(row["other_accounts"]) >= 1:
                signals.append(
                    schemas.FraudSignal(
                        type="SHARED_IP",
                        entity_id=row["ip_address"],
                        connected_accounts=row["other_accounts"],
                        description=(
                            f"IP {row['ip_address']} is used by this account and "
                            f"{len(row['other_accounts'])} other account(s)"
                        ),
                    )
                )

        # Signal 3: pass-through structure (funds in from X, out to Y).
        for row in await graph_repository.pass_through_links(acct_id, validated_limit):
            signals.append(
                schemas.FraudSignal(
                    type="PASS_THROUGH",
                    entity_id=f"{row['from_account']}->{row['to_account']}",
                    connected_accounts=[row["from_account"], row["to_account"]],
                    description=(
                        f"Account received {row['in_txn']} from {row['from_account']} "
                        f"and sent {row['out_txn']} to {row['to_account']}"
                    ),
                )
            )

        return schemas.FraudSignals(
            account_id=acct_id,
            max_depth=depth,
            signals=signals[:validated_limit],
            count=len(signals[:validated_limit]),
            note=(
                "Structural signals only - not a fraud determination. "
                "Shared infrastructure and pass-through flows are common in "
                "legitimate relationships; interpretation belongs to the "
                "investigator/agent layer."
            ),
        )
