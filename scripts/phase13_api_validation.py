"""Phase 13 live validation: run + persist + read back all three scenarios via the API.

Uses one event loop with httpx ASGITransport so the async engine, its
connection pool, and every request share the same loop (mirrors production,
where uvicorn serves on a single loop).

    uv run python scripts/phase13_api_validation.py
"""

import asyncio
import sys

import httpx
from apps.api.main import app

SCENARIOS = ("TXN-001", "TXN-1006", "TXN-1001")


async def main() -> int:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        assert health.status_code == 200, health.text
        print("health:", health.json())

        before = (await client.get("/investigations")).json()["total"]
        print("cases before:", before)

        for txn in SCENARIOS:
            run = await client.post(
                "/investigations/run", json={"transaction_id": txn, "persist": True}
            )
            assert run.status_code == 200, run.text
            body = run.json()
            assert body["status"] == "COMPLETED"
            case_id = body["persistence"]["case_id"]

            detail = await client.get(f"/investigations/{case_id}")
            assert detail.status_code == 200, detail.text
            d = detail.json()

            evidence = await client.get(f"/investigations/{case_id}/evidence")
            assert evidence.status_code == 200
            knowledge = await client.get(
                f"/investigations/{case_id}/evidence", params={"tier": "KNOWLEDGE"}
            )
            assert knowledge.status_code == 200
            audit = await client.get(f"/investigations/{case_id}/audit")
            assert audit.status_code == 200
            report = await client.get(f"/investigations/{case_id}/report")
            assert report.status_code == 200
            rep = report.json()

            print(
                f"{txn}: case={case_id} evidence={len(d['evidence'])} "
                f"knowledge={knowledge.json()['total']} events={len(audit.json())} "
                f"action={rep['recommended_action']} OK"
            )

        after = (await client.get("/investigations")).json()["total"]
        print("cases after:", after, "(+", after - before, ")")
    print("API SCENARIO VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
