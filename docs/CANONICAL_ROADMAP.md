# Omerta.ai — Canonical Roadmap & Phase Status

**Document Version**: 1.0.0  
**Audit Baseline**: Post-Audit Stabilized Codebase (October 6, 2026)

---

## 1. Roadmap Overview Matrix

| Phase | Subsystem | Status | Test Suite | Next Action |
|---|---|---|---|---|
| **Phase 0** | Infrastructure & Database Foundation | **COMPLETE** | Alembic migrations, session tests | Maintained |
| **Phase 1** | Core Banking & Double-Entry Ledger | **COMPLETE** | `test_banking_foundation_e2e.py` | Maintained |
| **Phase 2** | 3-Strike Security & Support Restoration | **COMPLETE** | `test_transfer_security_and_support.py` | Maintained |
| **Phase 3** | Deterministic Risk Intelligence (0-100) | **COMPLETE** | `test_risk_service.py` | Maintained |
| **Phase 4** | Neo4j Graph Intelligence & Fund Tracing | **COMPLETE** | `test_network_graph_and_fund_tracing.py` | Maintained |
| **Phase 5** | MCP Tool Layer (4 Read-Only Servers) | **COMPLETE** | `test_graph_mcp.py`, capability tests | Maintained |
| **Phase 6** | LangGraph Deterministic Orchestration | **COMPLETE** | `test_investigator_graph.py` | Maintained |
| **Phase 7** | Regulatory Knowledge Retrieval (TF-IDF) | **COMPLETE** | `test_knowledge_service.py` | Maintained |
| **Phase 8** | LLM Agent & Evidence Grounding | **COMPLETE** | `test_agent_and_persistence.py` | Maintained |
| **Phase 9** | Case & Evidence Persistence (SHA-256) | **COMPLETE** | `test_api_cases.py`, `test_api_investigations.py` | Maintained |
| **Phase 10**| **Multi-Agent Forensic Specialists** | **PLANNED** | Ready for specification | **NEXT STAGE TARGET** |
| **Phase 11**| Live ML Risk & Production Hardening | **PLANNED** | Future phase | Post Phase 10 |

---

## 2. Phase-by-Phase Verification Details

### Phase 0 — Foundation & Infrastructure
- **Status**: `COMPLETE`
- **Implemented Components**:
  - PostgreSQL 17-alpine on port 15432 with async connection pooling.
  - Neo4j 5.26 on port 17687 with APOC support.
  - Docker Compose orchestration with healthchecks.
  - Alembic asynchronous migration pipeline (versions `0001` through `0006`).
- **Test Status**: Cleanly executes migrations and test database creation.

---

### Phase 1 — Core Banking & Ledger Invariants
- **Status**: `COMPLETE`
- **Implemented Components**:
  - Double-entry accounting model (`AccountLedgerEntry` debits and credits).
  - Row-level locking `SELECT ... FOR UPDATE` on sender accounts.
  - Atomicity guarantee: rollback on insufficient funds or status errors.
  - Currency matching validation (EGP/USD).
- **Test Status**: `tests/test_banking_foundation_e2e.py` passes 100%.

---

### Phase 2 — Security & Support System
- **Status**: `COMPLETE`
- **Implemented Components**:
  - Non-logout 3-strike transfer password lockout.
  - Automatic support ticket creation on 3rd failed attempt.
  - Separation of Concerns: Ticket Resolution $\neq$ Transfer Restoration.
  - Multi-tier staff restoration endpoint forcing transfer password reset.
- **Test Status**: `tests/test_transfer_security_and_support.py` passes 100%.

---

### Phase 3 — Deterministic Risk Engine
- **Status**: `COMPLETE`
- **Implemented Components**:
  - Scoring contract: 0.00 to 100.00 (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
  - Signal computation: `NEW_DEVICE`, `VPN_INDICATOR`, `IMPOSSIBLE_TRAVEL`, `SHARED_DEVICE`, `SHARED_IP`.
  - Provenance tagging: `source="MOCK"`, `model_version="mock-risk-v1"`.
- **Test Status**: Risk assessment unit and integration tests pass cleanly.

---

### Phase 4 — Graph Intelligence & Neo4j Projection
- **Status**: `COMPLETE`
- **Implemented Components**:
  - Idempotent Cypher projection of accounts, devices, IPs, and transactions.
  - Multi-hop transaction pathfinding up to depth 3.
  - Shared device / shared IP co-location cluster detection.
- **Test Status**: `tests/test_network_graph_and_fund_tracing.py` passes 100%.

---

### Phase 5 — Model Context Protocol (MCP) Tool Layer
- **Status**: `COMPLETE`
- **Implemented Components**:
  - 4 Read-Only MCP Servers: `TransactionServer`, `GraphServer`, `RiskServer`, `KnowledgeServer`.
  - Invariant: Zero write or execution capabilities in MCP tools.
- **Test Status**: MCP capability wrappers verified with JSON serialization safety.

---

### Phase 6 — LangGraph Deterministic Orchestration
- **Status**: `COMPLETE`
- **Implemented Components**:
  - State machine routing: `init -> load_txn -> load_account -> load_graph -> load_risk -> load_rag -> agent -> assemble_evidence`.
  - Error short-circuiting: Graceful routing to `END` on invalid transaction IDs.
- **Test Status**: `tests/test_investigator_graph.py` passes 14/14 tests.

---

### Phase 7 — Regulatory Knowledge Retrieval (RAG)
- **Status**: `COMPLETE`
- **Implemented Components**:
  - In-memory TF-IDF and keyword matching over `KnowledgeDocument` and `KnowledgeChunk` tables.
  - Seeded guidance: FinCEN Red Flags, FATF Typologies, Omerta AML Policy.
- **Test Status**: Verified supporting context retrieval.

---

### Phase 8 — LLM Agent & Grounding
- **Status**: `COMPLETE`
- **Implemented Components**:
  - `FakeLLMProvider` for deterministic offline testing and CI.
  - `OpenAIProvider` for live inference with external endpoints.
  - Validation pass ensuring findings cite only real evidence IDs.
  - Self-repair and deterministic rule-based fallback.
- **Test Status**: `tests/test_agent_and_persistence.py` passes 100%.

---

### Phase 9 — Investigation Case & Evidence Persistence
- **Status**: `COMPLETE`
- **Implemented Components**:
  - `InvestigationCase` relational records linked to alerts.
  - Immutable `Evidence` rows with SHA-256 content hashes.
  - Append-only `AuditEvent` log stream.
  - HTTP REST endpoints for `/investigations`, `/cases`, and `/investigations/{id}/evidence`.
- **Test Status**: `tests/test_api_cases.py` and `tests/test_api_investigations.py` pass 100%.

---

### Phase 10 — Multi-Agent Forensic Specialists (Target for Next Phase)
- **Status**: `PLANNED`
- **Scope**:
  - Decompose single monolithic agent into cooperating specialist sub-agents:
    1. **Structuring & Smurfing Specialist** (Temporal bursts, sub-threshold transfers).
    2. **Mule Network Specialist** (Graph cycles, rapid in-out flow).
    3. **Cyber & Device Specialist** (VPN hops, multi-account device co-location).
    4. **Lead Synthesizer Agent** (Aggregates specialist verdicts into canonical SAR recommendation).
  - Multi-agent state orchestration in LangGraph.

---

### Phase 11 — Production Hardening & Advanced ML
- **Status**: `PLANNED`
- **Scope**:
  - Train LightGBM / XGBoost fraud models to replace deterministic mock provider.
  - Embeddings with pgvector for regulatory semantic search.
  - Async event streaming and WebSocket alert dispatch.
