"""LangGraph investigation workflow (Phase 8, deterministic).

START -> initialize_investigation -> load_transaction -> load_account_context
       -> load_graph_context -> load_risk_context -> load_knowledge_context
       -> assemble_evidence -> END

The workflow stops early only when the investigation has failed (e.g. the
transaction does not exist). Orchestration is deterministic; the agent node
(Phase 9) reasons over the snapshot and the knowledge node (Phase 12)
retrieves stored policy/typology context via the Knowledge MCP service.
"""

import asyncio
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from apps.investigator import nodes
from apps.investigator.state import InvestigationState, InvestigationStatus

logger = logging.getLogger(__name__)


def _stop_on_failure(state: InvestigationState) -> str:
    """Route to END when the investigation has failed (structured error)."""
    if state.status == InvestigationStatus.FAILED or state.errors:
        return END
    return "continue"


def build_investigation_graph() -> Any:
    """Compile the deterministic investigation StateGraph."""
    graph = StateGraph(InvestigationState)
    graph.add_node("initialize_investigation", nodes.initialize_investigation)
    graph.add_node("load_transaction", nodes.load_transaction)
    graph.add_node("load_account_context", nodes.load_account_context)
    graph.add_node("load_graph_context", nodes.load_graph_context)
    graph.add_node("load_risk_context", nodes.load_risk_context)
    graph.add_node("load_knowledge_context", nodes.load_knowledge_context)
    graph.add_node("analyze_with_agent", nodes.analyze_with_agent)
    graph.add_node("assemble_evidence", nodes.assemble_evidence)

    graph.add_edge(START, "initialize_investigation")
    graph.add_edge("initialize_investigation", "load_transaction")
    graph.add_conditional_edges(
        "load_transaction",
        _stop_on_failure,
        {
            END: END,
            "continue": "load_account_context",
        },
    )
    graph.add_edge("load_account_context", "load_graph_context")
    graph.add_edge("load_graph_context", "load_risk_context")
    graph.add_edge("load_risk_context", "load_knowledge_context")
    graph.add_edge("load_knowledge_context", "analyze_with_agent")
    graph.add_edge("analyze_with_agent", "assemble_evidence")
    graph.add_edge("assemble_evidence", END)
    return graph.compile()


def _normalize(final: Any) -> dict[str, Any]:
    """Normalize LangGraph's result into a JSON-safe state dict.

    Depending on state-field types, ``invoke`` may return a dict with nested
    model instances; validating back into ``InvestigationState`` and dumping
    guarantees a fully serializable snapshot.
    """
    return InvestigationState.model_validate(final).model_dump(mode="json")


def run_investigation(transaction_id: str, alert_id: str | None = None) -> dict[str, Any]:
    """Run one investigation synchronously; returns the final state dict."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run_on_private_loop(transaction_id, alert_id))
    # Already inside a loop (e.g. FastAPI): reuse the caller's loop; the
    # request's own lifetime bounds the cached Neo4j driver there.
    app = build_investigation_graph()
    initial = InvestigationState(transaction_id=transaction_id, alert_id=alert_id)
    final = _normalize(app.invoke(initial))
    logger.info(
        "investigation_finished",
        extra={
            "transaction_id": transaction_id,
            "investigation_id": final["investigation_id"],
            "status": final["status"],
        },
    )
    return final


async def _run_on_private_loop(transaction_id: str, alert_id: str | None) -> dict[str, Any]:
    """Drive one investigation with a self-contained Neo4j driver lifecycle.

    The asyncio Neo4j driver is event-loop-bound; this runner creates a driver
    and binds it **context-locally** (contextvar, not process-global) so
    concurrent investigations never race on driver creation/teardown, then
    closes it when the run finishes.
    """
    from infrastructure.config import get_settings
    from infrastructure.neo4j import client as graph_client

    from neo4j import AsyncGraphDatabase

    settings = get_settings()
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    try:
        with graph_client.use_driver(driver):
            app = build_investigation_graph()
            initial = InvestigationState(transaction_id=transaction_id, alert_id=alert_id)
            return _normalize(await app.ainvoke(initial))
    finally:
        await driver.close()


async def run_investigation_async(
    transaction_id: str, alert_id: str | None = None
) -> dict[str, Any]:
    """Async variant for FastAPI endpoints."""
    return await _run_on_private_loop(transaction_id, alert_id)
