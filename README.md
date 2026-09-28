# Omerta.ai

**Agentic AI financial-crime investigation platform.**

Traditional fraud systems detect suspicious activity. Omerta.ai also autonomously
investigates **why** activity is suspicious: it gathers evidence through MCP tools,
combines it into an auditable investigation case, and recommends actions for
**human compliance review**. The AI never performs irreversible financial or
regulatory actions (account freezing, SAR submission, rule changes).

## Stack

| Concern | Choice |
| --- | --- |
| Language | Python 3.12 |
| Package management | uv |
| API | FastAPI |
| Orchestration | LangGraph |
| Tool interface | MCP (Model Context Protocol) |
| OLTP database | PostgreSQL (SQLAlchemy async + asyncpg) |
| Graph database | Neo4j |
| Validation | Pydantic v2 |
| Tests / lint | pytest, ruff |

## Project structure

```
apps/
    api/            FastAPI application
    investigator/   LangGraph orchestrator (Phase 8) + future agent (Phase 9)
mcp_servers/
    transaction_server/  Read-only transaction MCP server (Phase 5)
    graph_server/        Read-only graph MCP server over Neo4j (Phase 6)
    risk_server/         Read-only risk MCP server, MOCK provider (Phase 7)
domain/             schemas, errors, services (business logic)
infrastructure/     config, database, neo4j, risk (mock provider), adapters
data/seed/          seed data for local development
knowledge/          AML typologies, policies, regulations (RAG corpus, later)
tests/              pytest suite
scripts/            dev smoke tests
```

Separation of responsibilities:

- **Agent** = reasoning (LLM)
- **Orchestrator** = workflow/control (LangGraph state machine)
- **MCP** = tool interface (databases are never exposed directly to the LLM)

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (manages Python 3.12 automatically)
- Docker

## Quickstart

```bash
# 1. Start PostgreSQL and Neo4j
docker compose up -d

# 2. Create the virtual environment, install dependencies, generate uv.lock
uv sync

# 3. Configure the environment
cp .env.example .env   # dev defaults work out of the box

# 4. Run the API
uv run uvicorn apps.api.main:app --reload
```

The API is then available at http://127.0.0.1:8000 with interactive docs at
http://127.0.0.1:8000/docs.

## Database

Schema lives in `infrastructure/database/models.py`; migrations in `migrations/`.
Tables are **never** created outside Alembic migrations.

```bash
# Apply migrations (creates all tables)
uv run alembic upgrade head

# Seed deterministic development data (TXN-001 / ALERT-001 / CASE-001 scenario)
uv run python -m infrastructure.database.seed

# Optional: wipe all rows first, then seed fresh
uv run python -m infrastructure.database.seed --reset
```

The seed is idempotent: every row is upserted on its natural business key
(`external_id` / IP address), so running it repeatedly never duplicates data.

Seeded scenario (facts only - all risk scores are labeled mock values, not ML
predictions):

| Entity | Notes |
| --- | --- |
| `TXN-001` | 8400.00 USD wire, ACC-1001 -> ACC-9001, new device DEV-123, new IP |
| `ALERT-001` | HIGH, risk score 0.87 (seed/mock), status OPEN |
| `CASE-001` | HIGH severity case with 3 traceable POSTGRES evidence rows |
| `TXN-1001..1005` | Baseline + suspicious history (shared device, layering pass-through) |

Live data inspection: `docker exec -it omerta-postgres psql -U omerta -d omerta`.

## Transaction MCP Server (read-only)

The first controlled tool interface for the future Investigator Agent. It
exposes investigation facts over the Model Context Protocol; PostgreSQL stays
the single source of truth and **the server holds no hardcoded data**.

**Architecture** (strict layering, no ORM objects cross layers):

```text
Investigator Agent (future)
       |
Transaction MCP server   mcp_servers/transaction_server/server.py
       |                 tools.py (JSON in/out, structured errors)
       |
Service layer            domain/services/transaction_service.py
       |                 (validation, mapping, NotFoundError)
Repository               infrastructure/database/repository.py
       |
PostgreSQL               infrastructure/database/models.py
```

**The server is strictly read-only.** It exposes no tools that modify
transactions, accounts, risk scores, evidence, or anything else.

### Tools

| Tool | Input | Output |
| --- | --- | --- |
| `get_transaction` | `transaction_id` | Full transaction: sender, recipient, amount, currency, type, status, timestamp, device, IP, new-device/IP flags, metadata |
| `get_account` | `account_id` | Account facts: name, type, country, created_at, status, risk_level |
| `get_account_transactions` | `account_id`, `limit?` | History where account is sender OR recipient, newest first, `truncated` flag |
| `get_recipient_history` | `recipient_account_id`, `limit?` | History where account is the recipient (mule/layering patterns) |
| `get_device_history` | `device_id`, `limit?` | Transactions from a device (shared-device detection) |
| `get_ip_history` | `ip_address`, `limit?` | Transactions from an IP (shared infrastructure) |

All list tools default to `limit=20`, hard-capped at `100`, deterministic
newest-first ordering.

### Example tool call and result

```jsonc
// get_transaction {"transaction_id": "TXN-001"}
{
  "transaction_id": "TXN-001",
  "sender":   {"external_id": "ACC-1001", "customer_name": "John Anderson", "country": "US", "risk_level": "HIGH"},
  "recipient": {"external_id": "ACC-9001", "customer_name": "Elena Petrova", "country": "CY", "risk_level": "HIGH"},
  "amount": "8400.00",
  "currency": "USD",
  "transaction_type": "WIRE",
  "status": "COMPLETED",
  "device": {"external_id": "DEV-123", "device_type": "MOBILE", "risk_level": "HIGH"},
  "ip": {"address": "202.0.113.77", "country": "US", "risk_level": "MEDIUM"},
  "is_new_device": true,
  "is_new_ip": true,
  "data_source": "POSTGRES"
}

// get_transaction {"transaction_id": "TXN-999"}  (structured, predictable errors)
{"error": "NOT_FOUND", "resource": "transaction", "id": "TXN-999"}

// invalid input
{"error": "VALIDATION_ERROR", "field": "limit", "detail": "limit must be >= 1"}
```

### Running the server locally

```bash
# stdio transport (as an MCP host would launch it)
uv run python -m mcp_servers.transaction_server.server

# end-to-end smoke test over real stdio: spawns the server as a subprocess
# and calls all six tools against the seeded database
uv run python scripts/smoke_transaction_mcp.py
```

The Python API is transport-ready for the Investigator Agent: connect with
`Client(StdioServerParameters(...))` over stdio or `Client(server)` in-memory.

### MCP tests

```bash
uv run pytest tests/test_transaction_mcp.py tests/test_transaction_service.py
```

They run against the isolated `omerta_test` database (the conftest re-points
the application engine at it, so even protocol-level calls never touch dev
or production data) and cover: all six tools, deterministic ordering, limits,
not-found payloads, validation errors, JSON serializability, and the full
MCP protocol path.

## Neo4j Graph Layer + Graph MCP Server (read-only)

Relationship intelligence for investigations. **PostgreSQL remains the source
of truth**; Neo4j is a derived, disposable *graph projection* consumed only by
the tools below (no MCP tool writes to PostgreSQL or the graph).

```text
PostgreSQL (facts, source of truth)
    |  graph projection (idempotent MERGE)
    v
Neo4j (relationship projection)
    |  Cypher (graph repository)
    v
Graph Service (validation, evidence assembly)
    |  MCP
    v
Graph MCP Server -> Future Investigator Agent
```

### Graph schema

All nodes carry a `projection` namespace property (dev/test isolation) plus a
stable business key from PostgreSQL:

```text
(:Account {projection, external_id, customer_name, country, risk_level})
(:Transaction {projection, external_id, amount, currency, transaction_type, status, timestamp})
(:Device {projection, external_id, device_type, risk_level})
(:IP {projection, address, country, risk_level})

(:Account)-[:SENT]->(:Transaction)
(:Transaction)-[:RECEIVED_BY]->(:Account)
(:Transaction)-[:USED_DEVICE]->(:Device)
(:Transaction)-[:USED_IP]->(:IP)
```

Uniqueness constraints (Neo4j 5 syntax, community-edition compatible) exist on
`(projection, external_id)` for Account/Transaction/Device and
`(projection, address)` for IP.

### Projecting PostgreSQL into Neo4j

```bash
# 1. Seed PostgreSQL facts
docker compose up -d postgres neo4j
uv run alembic upgrade head
uv run python -m infrastructure.database.seed

# 2. Project into Neo4j (idempotent - safe to re-run)
uv run python -m infrastructure.neo4j.seed
```

Every node/relationship write is a MERGE on stable keys, so running the
projection twice never duplicates anything; it reports per-label counts.

### Graph MCP tools (all read-only)

| Tool | Input | Returns |
| --- | --- | --- |
| `get_account_neighbors` | `account_id`, `limit?` | Connected entities (ACCOUNT/TRANSACTION/DEVICE/IP) with relationship and direction |
| `find_connected_accounts` | `account_id`, `limit?` | Accounts connected via `DIRECT_TRANSACTION`, `SHARED_DEVICE`, or `SHARED_IP` (each with the entity responsible) |
| `find_shared_devices` | `account_id`, `limit?` | Devices shared with other accounts (relationship signal, **not** a fraud label) |
| `find_shared_ips` | `account_id`, `limit?` | IPs shared with other accounts (relationship signal) |
| `find_transaction_paths` | `source_account_id`, `target_account_id`, `max_depth?` | Bounded paths (nodes + relationships + edge count), shortest first |
| `find_fraud_ring` | `account_id`, `max_depth?`, `limit?` | Structural signals: `SHARED_DEVICE`, `SHARED_IP`, `PASS_THROUGH` clusters with explicit **non-verdict** note |

Safety: result limits (default 20, cap 100), traversal depth 1–5 (hard cap),
parameterized Cypher, structured `NOT_FOUND`/`VALIDATION_ERROR` payloads, no
credentials/queries/stack traces in tool output. The graph provides evidence;
interpretation belongs to the future agent/investigator layers.

Example:

```jsonc
// find_shared_devices {"account_id": "ACC-1001"}
{
  "account_id": "ACC-1001",
  "shared_devices": [{"device_id": "DEV-123", "other_accounts": ["ACC-3001"]}],
  "count": 1
}
```

### Running & testing the graph server

```bash
uv run python -m mcp_servers.graph_server.server      # stdio transport
uv run python scripts/smoke_graph_mcp.py              # real stdio smoke test
uv run pytest tests/test_graph_projection.py tests/test_graph_service.py tests/test_graph_mcp.py
```

Graph tests are marked `@pytest.mark.graph` and run in the dedicated `test`
projection namespace: test data coexists with dev data in one Neo4j instance
(community-edition-safe), queries are namespace-scoped, and cleanup deletes
only `projection: 'test'` nodes - never a developer's unrelated graph data.

`GET /health/neo4j` verifies actual Neo4j connectivity (503 if unreachable).

## Risk MCP Server (read-only, MOCK provider)

Risk MCP provides a **stable interface for transaction risk information**.
Phase 7 uses deterministic **mock/seeded risk data**; the real ML Risk Engine
will replace the mock provider in a later phase without changing the MCP tool
names, schemas, agent, or orchestrator.

> **This is NOT a trained ML fraud model.** No LightGBM/XGBoost/SHAP exists in
> this phase. Every risk output declares `source = "MOCK"` and
> `model_version = "mock-risk-v1"`.

```text
Risk MCP tool
    |
Risk Service            domain/services/risk_service.py
    |                    (validation + feature extraction from PG facts)
RiskProvider            infrastructure/risk/mock_provider.py
    |                    (MockRiskProvider now; MLModelRiskProvider later)
PostgreSQL facts        transactions, accounts, alerts (source of truth)
```

### Tools (all read-only)

| Tool | Input | Returns |
| --- | --- | --- |
| `get_risk_score` | `transaction_id` | `risk_score` (0..1), `risk_level` (LOW/MEDIUM/HIGH), `source=MOCK`, `model_version=mock-risk-v1`, `contributions`, `seeded_alert` (if a stored alert exists), `generated_at` |
| `get_risk_features` | `transaction_id` | Features derived strictly from PostgreSQL facts: amount, currency, new-device/new-IP flags, 7-day velocity, account/recipient age, risk levels, prior alert count |
| `get_feature_importance` | `transaction_id` | Deterministic mock contributions sorted descending — **not SHAP, not a trained model** |
| `get_previous_risk_events` | `account_id` | Stored (seeded) alert facts only; empty structured result when none exist — nothing fabricated |

Errors follow the shared structured contract (`NOT_FOUND` / `VALIDATION_ERROR`).

### How mock risk is derived

Features are **extracted from existing database facts** (no invented data):
amount/currency and new-device/new-IP flags come from the transaction row,
velocity = originator's transaction count in the 7 days up to the transaction,
account/recipient ages = days between account creation and the transaction,
`previous_suspicious_activity` = any stored alert on the originator's
transactions. The mock provider then adds fixed, documented weights
(`infrastructure/risk/mock_provider.py`) and clamps the sum to 0..1.

Thresholds (single source of truth in code, mirrored here):
`score >= 0.70 -> HIGH`, `>= 0.40 -> MEDIUM`, else `LOW`.

### ALERT-001 is preserved

The seeded alert (`risk_score = 0.87, HIGH`) remains an untouched database
fact. `get_risk_score` reports it under `seeded_alert` with an explicit note
that it is independent of the mock provider — the mock score (deterministically
0.9 for TXN-001) is never silently equated with the stored alert.

### Running & testing

```bash
uv run python -m mcp_servers.risk_server.server     # stdio transport
uv run python scripts/smoke_risk_mcp.py             # real stdio smoke test
uv run pytest tests/test_risk_service.py tests/test_risk_mcp.py
```

`GET /health/risk` reports `{"provider": "mock", ...}` — it deliberately does
not claim an ML model is healthy, because none exists.

## LangGraph Investigation Orchestrator (Phase 8, deterministic)

Phase 8 coordinates the three capability layers into a single investigation
snapshot that the future Investigator Agent (Phase 9) will reason over.

> **Phase 8 provides deterministic investigation orchestration. It does not
> perform LLM reasoning, real ML inference, RAG retrieval, or final
> investigation decisions.**

```text
Investigation Request (transaction_id)
    |
LangGraph Orchestrator (this phase)
    |--- Transaction capability -> what happened?   (Phase 5)
    |--- Graph capability      -> who is connected? (Phase 6)
    |--- Risk capability       -> how risky is it?  (Phase 7)
    |
Investigation State (typed, serializable snapshot)
    |
Evidence Assembly (provenance-preserving items)
    |
COMPLETED  (Phase 9 will add: Agent reasoning + findings)
```

### Investigation state

`apps/investigator/state.py` defines a typed Pydantic state — a **serializable
snapshot**, never a container for sessions/engines/drivers/secrets. Statuses:
`PENDING -> RUNNING -> COMPLETED | FAILED`. Collected evidence items carry
`category` (TRANSACTION/ACCOUNT/HISTORY/DEVICE/IP/GRAPH/RISK), `source`
(capability), `reference` (business key), and `data` — answering "where did
this come from?" for every item. Graph items remain *structural signals*;
risk items retain `source=MOCK`; database rows remain facts.

### Workflow and nodes

```text
START -> initialize_investigation -> load_transaction -> load_account_context
      -> load_graph_context -> load_risk_context -> assemble_evidence -> END
```

- `load_transaction` fails the investigation (FAILED + structured NOT_FOUND)
  when the transaction does not exist — the workflow never pretends success.
- Context nodes collect data through **capability wrappers**
  (`apps/investigator/capabilities.py`) that call the *existing* domain
  services (no duplicated SQL/Cypher, no second repository layer, no MCP
  subprocesses).
- Non-critical failures (e.g. one graph section unavailable) become structured
  warnings; critical failures become errors + FAILED status. Errors are never
  silently swallowed and never leak SQL/credentials/stack traces.
- `assemble_evidence` marks COMPLETED only when `errors` is empty.

### Running an investigation

```bash
# Minimal test endpoint (Phase 8 convenience, no case persistence)
curl -X POST http://127.0.0.1:8000/investigations/run \
  -H "Content-Type: application/json" -d '{"transaction_id": "TXN-001"}'
```

Or programmatically via `run_investigation("TXN-001")` /
`run_investigation_async(...)`. For TXN-001 the final state contains the real
seeded transaction, full account context, all six graph sections, all four
risk sections (provenance preserved: `source=MOCK`, `model_version=mock-risk-v1`,
`seeded_alert=0.87` distinct from mock `0.9`), and ~16 evidence items with
unique IDs.

### Limitations

No LLM, no ML, no RAG, no case persistence, no conditional exploration beyond
the early-failure stop, evidence is in-memory (full audit system is Phase 11).

## Investigator Agent (Phase 9, evidence-backed reasoning)

Phase 9 adds the reasoning step to the orchestrator: after evidence assembly,
the `analyze_with_agent` node asks an LLM to produce a **structured
investigation report**, validated against typed schemas with **referential
integrity enforced** — every finding must cite evidence IDs that actually exist
in the snapshot, otherwise validation fails.

### LLM provider layer (provider-agnostic)

```text
apps/investigator/agent.py        prompt builder + JSON parse + schema validation
infrastructure/llm/base.py        LLMProvider protocol (the stable seam)
infrastructure/llm/fake_provider.py  deterministic FakeInvestigatorProvider (no network)
infrastructure/llm/openai_provider.py  OpenAI-compatible chat client over httpx
infrastructure/llm/factory.py     LLM_PROVIDER -> provider instance
```

Providers are configured via environment variables (no hard-coded vendors):

```text
LLM_PROVIDER=fake      # fake (default, deterministic) | openai | groq | ollama | ...
LLM_MODEL=             # e.g. gpt-4o-mini (ignored by the fake provider)
LLM_API_KEY=           # never committed
LLM_BASE_URL=          # optional: Groq/Ollama/vLLM-compatible endpoints
```

The OpenAI-compatible provider works with any chat-completions endpoint
(OpenAI, Groq, Ollama, vLLM) via `LLM_BASE_URL`. The agent layer never changes
when the provider changes.

### Report schema and safety

The report (`domain/report.py`) is fully typed: `risk_level`, `typologies`,
`findings` (each with `evidence_ids`), `risk_factors`, `recommended_action`,
`confidence`, and an explicit `limitations` note. Guardrails:

- **No unsupported findings** — findings referencing unknown evidence IDs are
  rejected by validation (Pydantic validation-context integrity check).
- **No verdicts** — `recommended_action` is limited to review-oriented enum
  values (e.g. `HUMAN_REVIEW`); the agent cannot freeze accounts or submit SARs.
- **Provenance preserved** — mock risk (`source=MOCK`) and structural graph
  signals remain labeled as such inside the report context.
- **Prompt-injection-resistant parsing** — the agent parses JSON from the LLM
  response and validates it; free-text narratives cannot bypass the schema.

### Investigation run persistence

`infrastructure/database/persistence.py` upserts one `InvestigationCase` per
`investigation_id` (idempotent — re-running the same investigation updates the
same case) plus one `Evidence` row per evidence item, inside a single
transaction. The case links to the transaction and, when available, the alert.
Cases are created with status `OPEN`; only a human reviewer moves them forward
(Phase 13 adds the review API).

Run an investigation end-to-end:

```bash
uv run python -c "import asyncio; from apps.investigator.graph import run_investigation; print(run_investigation('TXN-001')['report'])"
```

Or through the API (persist to a case):

```bash
curl -X POST http://localhost:8000/investigations/run \
  -H "Content-Type: application/json" \
  -d '{"transaction_id": "TXN-001", "persist": true}'
```

> The Investigator Agent recommends; it does not decide. Every finding is
> traceable to evidence, and high-impact actions remain behind human approval.

## Pipeline hardening & evaluation (Phase 10)

Phase 10 makes the complete investigation pipeline reliable, measurable, and
safe — no new intelligence, no RAG, no ML.

### Lifecycle & safety

- Explicit lifecycle `PENDING → RUNNING → COMPLETED | FAILED`; a `FAILED` run
  can never become `COMPLETED` without a new run (enforced in
  `assemble_evidence` and tested).
- **Failure matrix**: transaction-not-found → `FAILED` + structured
  `NOT_FOUND`; graph/risk/agent/persistence failures degrade to structured
  `DEPENDENCY_ERROR` warnings (or run failure where critical) — never an
  exception leak, never a fabricated score or report, never a silent
  zero-fill.
- **No silent fallbacks**: unavailable sections stay `None` with a warning;
  the agent can never produce a report without valid evidence references.
- **Report guard (defense-in-depth)**: `assemble_evidence` re-validates the
  agent report (schema, enums, confidence bounds, transaction-id match,
  evidence-referential integrity, evidence-id uniqueness) before anything can
  be marked COMPLETED or persisted.

### Idempotency, concurrency & isolation

- Same `investigation_id` → idempotent case/evidence upsert; a genuinely new
  run → a distinct historical case. Repeated runs, repeated persistence, and
  repeated graph reads are verified safe.
- Concurrent investigations (e.g. `TXN-001` + `TXN-1006` in one event loop)
  are isolated: the Neo4j driver binds **context-locally** (contextvar
  `use_driver`), and DB engines support the same pattern (`use_engine`), so
  concurrent runs never race on driver/engine state or leak state between
  runs.
- Persistence is atomic: an evidence-row failure rolls back the case row —
  no half-persisted investigations.

### Observability

- Every node records its duration in `node_timings_ms`
  (`initialize_investigation`, `load_transaction`, `load_account_context`,
  `load_graph_context`, `load_risk_context`, `analyze_with_agent`,
  `assemble_evidence`) — simple structured latency, no tracing platform.
- Lifecycle logs: `investigation_started`, `transaction_loaded`,
  `account_loaded`, `graph_loaded`, `risk_loaded`, `agent_started`,
  `agent_completed`, `evidence_validated`, `investigation_completed`,
  `investigation_failed` — ids and durations only, never payloads or secrets.

### Security tests

- Secret-leakage tests: no `DATABASE_URL`, passwords, `bolt://`, API keys, or
  authorization headers in results, failure payloads, or logs.
- **Prompt-injection**: evidence containing "Ignore previous instructions…"
  is embedded as JSON *data* and cannot steer the report; recommendations
  remain bounded review-oriented enums.
- Evidence injection: fabricated evidence ids in agent output are rejected
  (fail-closed); malformed LLM output never reaches persistence.

### Evaluation

Deterministic scenarios (`tests/test_investigator_evaluation.py`) assert
**observable properties** — not exact LLM wording — using the no-network fake
provider (the suite never needs API keys):

| Scenario | Transaction | Expected observable behavior |
| --- | --- | --- |
| High-risk | `TXN-001` | COMPLETED; facts surfaced (8400 USD, ACC-1001); review-oriented action; all findings evidence-grounded |
| Shared device | `TXN-1006` | COMPLETED; `DEV-123` discoverable as shared-device graph signal; no fraud verdict |
| Clean baseline | `TXN-1001` | COMPLETED; valid grounded report even with no suspicious signals |

For optional engineering evaluation against a real provider:

```bash
# Deterministic baseline (default; no network):
uv run python scripts/evaluate_investigator.py

# With a configured provider (LLM_PROVIDER/LLM_MODEL/LLM_API_KEY):
uv run python scripts/evaluate_investigator.py --live
```

The script reports per-scenario provider/model/status/finding count/evidence
grounding/recommendation/latency and exits non-zero on ungrounded findings.
It is an engineering check, not a statistical benchmark.

### API & data hardening

- `POST /investigations/run`: input validation (blank ids → 422), structured
  error payloads, explicit `persist` opt-in, persistence failures surface as
  structured HTTP 503 — never stack traces or secrets.
- Seed data includes `ALERT-002` for `TXN-1006` (mock 0.74, clearly labeled)
  so both primary scenarios are alert-linked and persistable; the ALERT-001
  (0.87) vs mock-score (0.9) distinction is regression-guarded by dedicated
  tests.

## RAG + Knowledge MCP (Phase 12)

The knowledge layer stores curated AML reference data — policies, regulations,
typologies, procedures — as *data* and answers controlled queries over it.
Everything is deterministic: no LLM, no external embedding service, no network.

### Architecture

```text
Curated corpus (infrastructure/knowledge/corpus.py)
    → deterministic ingestion (idempotent upsert, one chunk per section)
    → knowledge_documents + knowledge_chunks (PostgreSQL, migration c8d3e6a71b45)
    → TF-IDF retrieval (infrastructure/knowledge/embeddings.py, dependency-free)
    → KnowledgeService (domain/services/knowledge_service.py)
    → Knowledge MCP (mcp_servers/knowledge_server: search_knowledge,
      get_document, get_document_section)
    → KnowledgeCapability → load_knowledge_context node in the LangGraph run
```

### Provenance & safety

- Every retrieved chunk carries `document_id`, `document_title`,
  `document_type`, `section`, `jurisdiction`, `effective_date`, `version`,
  `content`, and a retrieval `score` — an agent citation that does not resolve
  to these fields is invalid.
- Document content is treated strictly as **data, never instructions** (schema
  note + agent prompt rule 5); the agent must cite document + section and is
  forbidden from inventing or altering regulation citations.
- Empty retrieval is a valid, explicit outcome — results are never padded with
  irrelevant material, and scores are never fabricated for non-matches.
- Old vs current policy versions stay distinct, versioned facts.

### Tests

`test_knowledge_embeddings.py` (12), `test_knowledge_mcp.py` (9),
`test_knowledge_service.py` (8), `test_knowledge_security.py` (6),
`test_knowledge_agent.py` (5), `test_knowledge_persistence.py` (4),
`test_knowledge_evaluation.py` (5) — 49 tests covering deterministic ranking,
provenance resolution, hostile-document injection (treated as inert data),
retrieval degradation, idempotent ingestion, KNOWLEDGE-tier persistence,
reconstruction, and scenario-based RAG evaluation for TXN-001 / TXN-1006 /
TXN-1001.

Smoke test: `uv run python scripts/smoke_knowledge_mcp.py` (4th MCP server).

## Full Evidence & Audit System (Phase 11)

Evidence is a durable, immutable, traceable audit artifact: every item answers
where it came from, which investigation/transaction produced it, when, by which
capability, and whether its content changed since creation.

### Evidence model, categories & provenance

- Typed categories (extensible enum): `TRANSACTION`, `ACCOUNT`, `HISTORY`,
  `DEVICE`, `IP`, `GRAPH`, `RISK`, `AGENT_FINDING`, `KNOWLEDGE` (reserved for a
  future Knowledge MCP — no RAG in this phase).
- Audit tiers are preserved explicitly: `FACT` (transaction/account/history/
  device/ip), `STRUCTURAL_SIGNAL` (graph), `MODEL_OUTPUT` (risk),
  `AGENT_FINDING`, `KNOWLEDGE` (reserved). Seeded alert facts stay distinct
  from mock outputs (ALERT-001 = 0.87 is never merged with the mock 0.9 score).
- Provenance columns on `evidence`: `evidence_id`, `investigation_id`,
  `transaction_id`, `tier`, `producer`, `producer_version`, plus
  `source_reference`; unique `(case_id, evidence_id)` alongside the existing
  `(case_id, source, source_reference)` constraint.

### Integrity hashing & immutability

- `domain/evidence.py` computes a deterministic SHA-256 `content_hash` over
  canonical JSON (`sort_keys=True`) of semantic fields only — timestamps and
  DB-generated ids are excluded, so hashes survive JSONB round-trips.
- Persistence is append-only: re-persisting identical content is idempotent,
  while changed content raises `IntegrityError` instead of silently
  overwriting. Reconstruction recomputes hashes and fails closed on mismatch.

### Audit events

- Durable business events (new `audit_events` table), deliberately separate
  from operational logs: `INVESTIGATION_STARTED/COMPLETED/FAILED`,
  context `*_LOADED`, `AGENT_STARTED/COMPLETED`, `REPORT_CREATED/VALIDATED`,
  `PERSISTENCE_STARTED/COMPLETED`, `EVIDENCE_VALIDATED`.
- Each event stores `event_id`, investigation/transaction ids, `event_type`,
  `actor_type` (SYSTEM/AGENT/HUMAN), `source`, metadata and timestamp; unique
  `(investigation_id, event_id)` keeps re-persistence idempotent.

### Finding → evidence traceability & reconstruction

- Every finding carries `evidence_ids`; assembly resolves them against the
  evidence collected in the same run and fails the investigation on
  unresolvable references — unsupported assertions cannot reach a report.
- `domain/services/audit_service.py::get_investigation_audit` reconstructs a
  persisted investigation (report, findings, evidence, audit trail) and fails
  closed on schema/transaction mismatch, hash mismatch, cross-investigation or
  duplicate evidence references. Internal/domain-level only — the public case
  API is Phase 13.
- Migration `b41c7e5d9f02` adds the evidence provenance/hash columns,
  `investigation_cases.report` and `audit_events`; legacy rows are backfilled
  (`LEGACY-<id>` evidence ids, Python-side hash backfill) so the upgrade is
  reproducible and downgrade-verified.
- Live end-to-end validation (dev DB): `uv run python scripts/phase11_live_validation.py`.

## Services & ports

| Service | Port | Credentials (local dev only) |
| --- | --- | --- |
| PostgreSQL 17 | **15432** (host) → 5432 | `omerta` / `omerta_dev_password`, db `omerta` |
| Neo4j 5 | **17474** (HTTP), **17687** (Bolt) | `neo4j` / `omerta_dev_password` |

PostgreSQL is published on host port **15432** so it cannot clash with a
native PostgreSQL installation on 5432 (or other services on nearby ports).
Neo4j uses **17474/17687** because Windows can reserve shifting Hyper-V port
ranges (observed 7681–7780) that would otherwise block bolt port 7687 after a
reboot; override with `NEO4J_URI` if needed.

## Tests & linting

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests run against an isolated `omerta_test` database (auto-created and migrated
on the same Dockerized PostgreSQL). The dev database and any external database
are never touched. Test isolation uses reset+seed plus per-test rollback.

## Configuration

All configuration comes from environment variables — see `.env.example`.
No secrets are committed; `.env` is git-ignored.

## Deployment (Phase 18)

### Clean environment, exact commands

```bash
# 1. Services (PostgreSQL 15432, Neo4j 17474/17687; or add the backend service)
docker compose up -d postgres neo4j

# 2. Database schema + deterministic seed (facts + knowledge corpus)
uv run alembic upgrade head
uv run python -m infrastructure.database.seed

# 3. Neo4j graph projection (idempotent)
uv run python -m infrastructure.neo4j.seed --project-only   # if provided
# or: uv run python -c "import asyncio; from infrastructure.database.session import create_engine; from infrastructure.neo4j.projection import project_all; asyncio.run(project_all(create_engine()))"

# 4. (Optional) train the ML risk model, then set RISK_PROVIDER=ml
uv run python scripts/train_risk_model.py

# 5. Start the backend + dashboard
uv run uvicorn apps.api.main:app --port 8000
# Dashboard: http://127.0.0.1:8000/   API docs: http://127.0.0.1:8000/docs
```

With Docker Compose, `docker compose up -d --build backend` starts the API on
port 8000 with container-internal `DATABASE_URL`/`NEO4J_URI` already set.

### Health checks

`/health` (liveness), `/health/db`, `/health/neo4j`, `/health/risk`,
`/health/knowledge` (corpus stats), `/health/llm` (provider configuration,
never keys). Readiness endpoints return 503 when a dependency is unreachable;
none expose secrets or internals.

### Security configuration

Auth is off by default (dev). To enable: set `API_KEY_ANALYST` and/or
`API_KEY_ADMIN` (requests then require `X-API-Key`); optionally set
`RATE_LIMIT_PER_MINUTE` (+ `RATE_LIMIT_BURST`) for 429 throttling. `.env` is
git-ignored; `.env.example` carries placeholders only.

## Roadmap

The implementation follows small, testable vertical slices. Complete so far:
Phases 1, 4–13 as listed above, plus Phase 14 (real ML risk engine -
LightGBM over an honestly-labeled synthetic dataset, `RISK_PROVIDER=ml`),
Phase 15 (advanced agent: indirect-injection defense, scenario evaluation),
Phase 16 (frontend investigation dashboard - static SPA on the Case API),
Phase 17 (security hardening: opt-in API-key auth with roles, rate limiting,
input hardening, tamper evidence), and Phase 18 (deployment, health checks,
Docker backend, documentation). Remaining: none - see the final report.
