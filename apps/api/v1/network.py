"""Network Graph Relationship Router for Omerta.ai."""

from typing import Any
from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from domain.services.network_graph_service import NetworkGraphService
from infrastructure.database.session import get_engine

router = APIRouter(prefix="/network", tags=["Network Analysis"])


@router.get("/graph")
async def get_network_graph(
    focus_entity_id: str | None = Query(default=None),
    entity_type: str = Query(default="account"),
    max_nodes: int = Query(default=40, ge=10, le=100),
) -> dict[str, Any]:
    """Retrieve node-link graph payload (Accounts, Devices, IPs, Transfers)."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        return await NetworkGraphService(session).get_network_graph(
            focus_entity_id=focus_entity_id,
            entity_type=entity_type,
            max_nodes=max_nodes,
        )
