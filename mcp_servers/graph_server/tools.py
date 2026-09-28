"""Tool functions for the Graph MCP server (read-only).

Same bridge pattern as the transaction server: JSON in, JSON out, domain
errors as structured payloads, unexpected failures logged without secrets.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from domain.errors import DomainError
from domain.services.graph_service import GraphService

logger = logging.getLogger(__name__)


async def _execute(handler: Callable[[], Awaitable[Any]]) -> dict[str, Any]:
    """Run a graph service call and normalize errors to structured payloads."""
    try:
        result = await handler()
        return result.model_dump(mode="json")
    except DomainError as exc:
        logger.info("graph tool domain error: %s", exc.payload)
        return exc.payload
    except Exception:
        logger.exception("graph tool failed")
        return {"error": "INTERNAL_ERROR", "detail": "unexpected server error"}


async def get_account_neighbors(account_id: str, limit: int | None = None) -> dict[str, Any]:
    """Direct graph neighbors of an account."""
    return await _execute(lambda: GraphService().get_account_neighbors(account_id, limit))


async def find_connected_accounts(account_id: str, limit: int | None = None) -> dict[str, Any]:
    """Accounts connected via direct transaction, shared device, or shared IP."""
    return await _execute(lambda: GraphService().find_connected_accounts(account_id, limit))


async def find_shared_devices(account_id: str, limit: int | None = None) -> dict[str, Any]:
    """Devices shared with other accounts (relationship signal)."""
    return await _execute(lambda: GraphService().find_shared_devices(account_id, limit))


async def find_shared_ips(account_id: str, limit: int | None = None) -> dict[str, Any]:
    """IP addresses shared with other accounts (relationship signal)."""
    return await _execute(lambda: GraphService().find_shared_ips(account_id, limit))


async def find_transaction_paths(
    source_account_id: str, target_account_id: str, max_depth: int | None = None
) -> dict[str, None | str | int | list]:
    """Bounded transaction paths between two accounts."""
    return await _execute(
        lambda: GraphService().find_transaction_paths(
            source_account_id, target_account_id, max_depth
        )
    )


async def find_fraud_ring(
    account_id: str, max_depth: int | None = None, limit: int | None = None
) -> dict[str, Any]:
    """Structural signals (shared infra, pass-through) - evidence, not verdicts."""
    return await _execute(lambda: GraphService().find_fraud_ring(account_id, max_depth, limit))


__all__ = [
    "find_connected_accounts",
    "find_fraud_ring",
    "find_shared_devices",
    "find_shared_ips",
    "find_transaction_paths",
    "get_account_neighbors",
]
