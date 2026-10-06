"""Engineering evaluation of the Investigator Agent across seeded scenarios.

Runs the complete pipeline (orchestration -> agent -> report) for selected
scenarios and prints a compact report:

    scenario | provider | model | status | findings | grounding | action | agent_ms

Grounding = every finding references evidence ids that exist in the snapshot
(0 violations). This is an engineering evaluation, NOT a scientific benchmark;
it makes no statistical claims.

Usage:

    # Deterministic baseline (no network, no API key) - the default:
    uv run python scripts/evaluate_investigator.py

    # Against a real configured provider (uses LLM_PROVIDER/LLM_MODEL/...):
    LLM_PROVIDER=openai LLM_MODEL=gpt-4o-mini LLM_API_KEY=... \
        uv run python scripts/evaluate_investigator.py --live

Exits non-zero if any scenario fails or produces ungrounded findings.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import Any

SCENARIOS: list[str] = ["TXN-001", "TXN-1006", "TXN-1001"]

EXPECTED_ACTION: dict[str, set[str]] = {
    "TXN-001": {"HUMAN_REVIEW", "ESCALATE_TO_FIU"},
    "TXN-1006": {"HUMAN_REVIEW", "ESCALATE_TO_FIU"},
    "TXN-1001": {"HUMAN_REVIEW", "MONITOR", "REQUEST_CUSTOMER_INFO", "CLOSE_NO_ACTION"},
}


def evaluate(final: dict[str, Any], scenario: str) -> dict[str, Any]:
    """Extract observable evaluation properties from one finished run."""
    report = final.get("report") or {}
    evidence_ids = {item["evidence_id"] for item in final.get("evidence", [])}
    violations: list[str] = []
    for index, finding in enumerate(report.get("findings", [])):
        unknown = sorted(set(finding.get("evidence_ids", [])) - evidence_ids)
        if unknown:
            violations.append(f"finding#{index}: unknown evidence {unknown}")

    action = report.get("recommended_action", "")
    action_ok = action in EXPECTED_ACTION.get(scenario, set())
    timings = final.get("node_timings_ms") or {}

    return {
        "scenario": scenario,
        "provider": (report.get("provenance") or {}).get("llm_provider", "?"),
        "model": (report.get("provenance") or {}).get("llm_model", "?"),
        "status": final.get("status"),
        "findings": len(report.get("findings", [])),
        "grounding_violations": violations,
        "action": action,
        "action_expected": action_ok,
        "risk_level": report.get("risk_level"),
        "agent_ms": round(timings.get("analyze_with_agent", 0.0), 1),
        "total_ms": round(sum(timings.values()), 1),
    }


async def _run_scenario(transaction_id: str) -> dict[str, Any]:
    from apps.investigator.graph import run_investigation_async
    from infrastructure.database.session import create_engine, use_engine

    started = time.perf_counter()
    # Private NullPool engine for this loop: asyncpg connections are loop-bound,
    # so each scenario owns its connections and nothing survives the loop.
    engine = create_engine(use_null_pool=True)
    try:
        with use_engine(engine):
            final = await run_investigation_async(transaction_id)
    finally:
        await engine.dispose()
    result = evaluate(final, transaction_id)
    result["wall_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="use the configured real provider (requires LLM_* env vars); "
        "default is the deterministic fake provider",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args(argv)

    if args.live:
        from infrastructure.config import get_settings

        settings = get_settings()
        if (settings.llm_provider or "fake") == "fake":
            print("error: --live requested but LLM_PROVIDER is not configured", file=sys.stderr)
            return 2

    rows = [asyncio.run(_run_scenario(s)) for s in SCENARIOS]

    failures: list[str] = []
    for row in rows:
        if row["status"] != "COMPLETED":
            failures.append(f"{row['scenario']}: status={row['status']}")
        if row["grounding_violations"]:
            failures.append(f"{row['scenario']}: ungrounded findings")
        if not row["action_expected"]:
            failures.append(f"{row['scenario']}: unexpected action {row['action']}")

    if args.json:
        print(json.dumps({"results": rows, "failures": failures}, indent=2))
    else:
        header = (
            f"{'scenario':<10} {'provider':<10} {'model':<16} {'status':<10} "
            f"{'find':<5} {'ground':<7} {'action':<20} {'agent_ms':<9} {'total_ms':<9}"
        )
        print(header)
        print("-" * len(header))
        for row in rows:
            grounding = "OK" if not row["grounding_violations"] else "VIOLATION"
            print(
                f"{row['scenario']:<10} {row['provider']:<10} {row['model']:<16} "
                f"{row['status']:<10} {row['findings']:<5} {grounding:<7} "
                f"{row['action']:<20} {row['agent_ms']:<9} {row['total_ms']:<9}"
            )
        if failures:
            print("\nFAILURES:")
            for failure in failures:
                print(f"  - {failure}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
