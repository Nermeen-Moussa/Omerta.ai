"""Phase 11 live validation: deterministic investigations x2 with persist + reconstruction.

Runs against the dev database (omerta) after ``alembic upgrade head``:

    uv run python scripts/phase11_live_validation.py

For TXN-001, TXN-1006 and TXN-1001 it verifies:
    * investigation completes with a valid report and evidence set
    * persistence is idempotent when repeated with identical content
    * reconstruction succeeds (fail-closed checks pass)
    * every finding evidence reference resolves to persisted evidence
"""

import asyncio
import sys
from collections import Counter
from typing import Any

from apps.investigator.graph import run_investigation_async
from domain.services.audit_service import get_investigation_audit
from infrastructure.database.persistence import persist_investigation
from infrastructure.database.session import create_engine


def _persist_kwargs(state: dict[str, Any]) -> dict[str, Any]:
    return dict(
        investigation_id=state["investigation_id"],
        transaction_id=state["transaction_id"],
        alert_id=state.get("alert_id"),
        report=state["report"],
        evidence=state["evidence"],
        audit_events=state.get("audit_events", []),
    )


def _refs_valid(findings: list[dict[str, Any]], evidence_ids: set[str]) -> tuple[bool, int]:
    refs = [rid for finding in findings for rid in finding.get("evidence_ids", [])]
    return all(rid in evidence_ids for rid in refs), len(refs)


async def _validate(engine, txn_id: str) -> None:
    state = await run_investigation_async(txn_id)
    inv = state["investigation_id"]
    result = await persist_investigation(engine, **_persist_kwargs(state))
    audit = await get_investigation_audit(engine, inv)

    # Idempotent repeat persistence with identical content.
    again = await persist_investigation(engine, **_persist_kwargs(state))
    idempotent = (
        again["case_id"] == result["case_id"]
        and again["evidence_rows"] == result["evidence_rows"]
        and again["audit_events"] == result["audit_events"]
    )

    evidence_ids = {e["evidence_id"] for e in audit["evidence"]}
    refs_ok, ref_count = _refs_valid(audit["findings"], evidence_ids)
    tiers = Counter(e["tier"] for e in audit["evidence"])
    actors = Counter(e["actor_type"] for e in audit["audit_events"])

    print(f"[{txn_id}] {inv}")
    print(
        f"  persisted: case={result['case_id']} status={result['case_status']} "
        f"evidence={result['evidence_rows']} events={result['audit_events']}"
    )
    print(
        f"  reconstructed: evidence={len(audit['evidence'])} "
        f"events={len(audit['audit_events'])} findings={len(audit['findings'])}"
    )
    print(f"  tiers: {dict(sorted(tiers.items()))}")
    print(f"  actors: {dict(sorted(actors.items()))}")
    print(f"  finding refs valid: {refs_ok} (refs={ref_count})")
    print(f"  idempotent: {idempotent}")

    if not refs_ok or not idempotent or not evidence_ids:
        raise RuntimeError(f"Phase 11 live validation failed for {txn_id}")


async def main() -> int:
    engine = create_engine()
    try:
        for txn in ("TXN-001", "TXN-1006", "TXN-1001"):
            for run in (1, 2):
                print(f"=== {txn} run {run} ===")
                await _validate(engine, txn)
    finally:
        await engine.dispose()
    print("ALL LIVE VALIDATIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
