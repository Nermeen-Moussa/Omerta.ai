"""Capability wrappers: the boundary between LangGraph nodes and services.

Nodes never touch sessions, repositories, or MCP internals - they call these
capabilities, which open short-lived sessions, invoke the *existing* domain
services, and return JSON-safe dicts. No business logic is duplicated here.
"""

import json
import logging
from typing import Any

from infrastructure.database.session import get_engine
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _to_payload(result: BaseModel) -> dict[str, Any]:
    """Convert a domain schema to a JSON-safe dict (fail loudly on bugs)."""
    return json.loads(result.model_dump_json())


class TransactionCapability:
    """Read-only transaction facts via the Phase 5 service."""

    async def get_transaction(self, transaction_id: str) -> dict[str, Any] | None:
        from domain.errors import NotFoundError
        from domain.services.transaction_service import TransactionService

        session = AsyncSession(get_engine(), expire_on_commit=False)
        try:
            return _to_payload(await TransactionService(session).get_transaction(transaction_id))
        except NotFoundError:
            return None
        finally:
            await session.rollback()
            await session.close()

    async def get_account(self, account_id: str) -> dict[str, Any] | None:
        from domain.errors import NotFoundError
        from domain.services.transaction_service import TransactionService

        session = AsyncSession(get_engine(), expire_on_commit=False)
        try:
            return _to_payload(await TransactionService(session).get_account(account_id))
        except NotFoundError:
            return None
        finally:
            await session.rollback()
            await session.close()

    async def get_account_transactions(self, account_id: str, limit: int) -> dict[str, Any] | None:
        from domain.services.transaction_service import TransactionService

        session = AsyncSession(get_engine(), expire_on_commit=False)
        try:
            return _to_payload(
                await TransactionService(session).get_account_transactions(account_id, limit)
            )
        except Exception:
            logger.exception("capability failed: get_account_transactions")
            return None
        finally:
            await session.rollback()
            await session.close()

    async def get_recipient_history(self, account_id: str, limit: int) -> dict[str, Any] | None:
        from domain.services.transaction_service import TransactionService

        session = AsyncSession(get_engine(), expire_on_commit=False)
        try:
            return _to_payload(
                await TransactionService(session).get_recipient_history(account_id, limit)
            )
        except Exception:
            logger.exception("capability failed: get_recipient_history")
            return None
        finally:
            await session.rollback()
            await session.close()

    async def get_device_history(self, device_id: str, limit: int) -> dict[str, Any] | None:
        from domain.services.transaction_service import TransactionService

        session = AsyncSession(get_engine(), expire_on_commit=False)
        try:
            return _to_payload(
                await TransactionService(session).get_device_history(device_id, limit)
            )
        except Exception:
            logger.exception("capability failed: get_device_history")
            return None
        finally:
            await session.rollback()
            await session.close()

    async def get_ip_history(self, ip_address: str, limit: int) -> dict[str, Any] | None:
        from domain.services.transaction_service import TransactionService

        session = AsyncSession(get_engine(), expire_on_commit=False)
        try:
            return _to_payload(await TransactionService(session).get_ip_history(ip_address, limit))
        except Exception:
            logger.exception("capability failed: get_ip_history")
            return None
        finally:
            await session.rollback()
            await session.close()


class GraphCapability:
    """Read-only structural signals via the Phase 6 graph service."""

    async def _invoke(self, method: str, *args: Any) -> BaseModel:
        """Perform the graph service call (override point for tests)."""
        from domain.services.graph_service import GraphService

        return await getattr(GraphService(), method)(*args)

    async def _call(self, method: str, *args: Any) -> dict[str, Any] | None:
        """GraphService is session-free (Neo4j), so no session is needed.

        Every failure degrades to ``None`` + a logged structured error -
        including payload-conversion bugs, never a raised exception.
        """
        try:
            result = await self._invoke(method, *args)
            return _to_payload(result)
        except Exception:
            logger.exception("capability failed: graph %s", method)
            return None

    async def get_account_neighbors(self, account_id: str, limit: int) -> dict[str, Any] | None:
        return await self._call("get_account_neighbors", account_id, limit)

    async def find_connected_accounts(self, account_id: str, limit: int) -> dict[str, Any] | None:
        return await self._call("find_connected_accounts", account_id, limit)

    async def find_shared_devices(self, account_id: str, limit: int) -> dict[str, Any] | None:
        return await self._call("find_shared_devices", account_id, limit)

    async def find_shared_ips(self, account_id: str, limit: int) -> dict[str, Any] | None:
        return await self._call("find_shared_ips", account_id, limit)

    async def find_transaction_paths(
        self, source_account_id: str, target_account_id: str, max_depth: int
    ) -> dict[str, Any] | None:
        return await self._call(
            "find_transaction_paths", source_account_id, target_account_id, max_depth
        )

    async def find_fraud_ring(
        self, account_id: str, max_depth: int, limit: int
    ) -> dict[str, Any] | None:
        return await self._call("find_fraud_ring", account_id, max_depth, limit)


class KnowledgeCapability:
    """Read-only knowledge retrieval via the Phase 12 service (RAG).

    Returns ranked stored policy/typology sections with full provenance.
    Every failure degrades to ``None`` - knowledge retrieval is supporting
    context, never a hard dependency of an investigation.
    """

    async def _invoke(self, method: str, *args: Any) -> BaseModel:
        """Perform the knowledge service call (override point for tests)."""
        from domain.services.knowledge_service import KnowledgeService

        session = AsyncSession(get_engine(), expire_on_commit=False)
        try:
            return await getattr(KnowledgeService(session), method)(*args)
        finally:
            await session.rollback()
            await session.close()

    async def _call(self, method: str, *args: Any) -> dict[str, Any] | None:
        try:
            result = await self._invoke(method, *args)
            return _to_payload(result)
        except Exception:
            logger.exception("capability failed: knowledge %s", method)
            return None

    async def search_knowledge(self, query: str, top_k: int) -> dict[str, Any] | None:
        return await self._call("search", query, top_k)


class RiskCapability:
    """Read-only risk signals via the Phase 7 service (MOCK provenance)."""

    async def _invoke(self, method: str, *args: Any) -> BaseModel:
        """Perform the risk service call (override point for tests)."""
        from domain.services.risk_service import RiskService

        session = AsyncSession(get_engine(), expire_on_commit=False)
        try:
            return await getattr(RiskService(session), method)(*args)
        finally:
            await session.rollback()
            await session.close()

    async def _call(self, method: str, *args: Any) -> dict[str, Any] | None:
        """Every failure degrades to ``None``; no exception ever escapes."""
        try:
            result = await self._invoke(method, *args)
            return _to_payload(result)
        except Exception:
            logger.exception("capability failed: risk %s", method)
            return None

    async def get_risk_score(self, transaction_id: str) -> dict[str, Any] | None:
        return await self._call("get_risk_score", transaction_id)

    async def get_risk_features(self, transaction_id: str) -> dict[str, Any] | None:
        return await self._call("get_risk_features", transaction_id)

    async def get_feature_importance(self, transaction_id: str) -> dict[str, Any] | None:
        return await self._call("get_feature_importance", transaction_id)

    async def get_previous_risk_events(self, account_id: str) -> dict[str, Any] | None:
        return await self._call("get_previous_risk_events", account_id)
