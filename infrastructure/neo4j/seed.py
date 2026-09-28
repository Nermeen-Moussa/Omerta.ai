"""CLI: project current PostgreSQL data into Neo4j (idempotent).

Run:
    uv run python -m infrastructure.neo4j.seed
"""

import asyncio

from infrastructure.database.session import get_engine
from infrastructure.neo4j import client as graph_client
from infrastructure.neo4j.projection import project_all


async def main() -> None:
    counts = await project_all(get_engine())
    print(f"Graph projection complete (namespace: {graph_client.projection()})")
    print("Nodes:")
    for label, count in sorted(counts["nodes"].items()):
        print(f"  :{label}: {count}")
    print("Relationships:")
    for rel, count in sorted(counts["relationships"].items()):
        print(f"  :{rel}: {count}")
    await graph_client.close_driver()


if __name__ == "__main__":
    asyncio.run(main())
