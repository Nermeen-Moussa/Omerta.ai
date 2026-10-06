# Omerta.ai — Audit Handoff & Next Stage Prompt

**Document Version**: 1.0.0  
**Date**: October 6, 2026  
**Auditors**: Senior Software Architect, FinTech Backend Engineer, Security Engineer, QA Engineer, Frontend Architect

---

## 1. Executive Summary

Omerta.ai has undergone a comprehensive full-stack audit, stabilization, test suite verification, and documentation reconciliation. The core banking ledger, three-strike security hold, support ticket lifecycle, graph projections, MCP tools, deterministic risk engine, and LangGraph investigation pipeline are stable, verified, and passing 100% of tests.

---

## 2. Status Matrix (17 Subsystems)

1. **Overall Status**: **STABLE & VERIFIED**. Foundation is hardened and ready for the next multi-agent AI phase.
2. **Backend Status**: **HEALTHY**. FastAPI routes (17 modules) operational with strict RBAC and customer isolation.
3. **Frontend Status**: **COMPILED & VERIFIED**. React 19 + TypeScript + Vite builds with zero errors; routes communicate with real backend APIs.
4. **Database Status**: **HEALTHY**. PostgreSQL 17 operational with ACID double-entry ledger, row-level concurrency locks (`FOR UPDATE`), and idempotent seeds.
5. **Security Status**: **HARDENED**. 3-strike non-logout transfer hold verified; customer data isolation enforced; parameterization prevents SQL/Cypher injection.
6. **Risk Engine Status**: **DETERMINISTIC (0-100)**. Explicitly verified and labeled as rule/heuristic engine (`source="MOCK"`, `model_version="mock-risk-v1"`).
7. **Neo4j Status**: **HEALTHY**. Version 5.26 with idempotent Cypher projection (`'dev'`/`'test'` namespaces), multi-hop traversal, and shared infrastructure detection.
8. **MCP Status**: **ACTIVE (100% READ-ONLY)**. 4 servers (Transaction, Graph, Risk, Knowledge) providing structured facts without write permissions.
9. **LangGraph Status**: **ACTIVE & DETERMINISTIC**. 8-node StateGraph compiling and executing with strict SHA-256 evidence grounding and error routing.
10. **LLM Status**: **ABSTRACTION VERIFIED**. `FakeLLMProvider` verified for deterministic test/CI runs; `OpenAIProvider` ready for live external inference.
11. **RAG Status**: **VERIFIED AS IN-MEMORY TF-IDF**. In-memory text matching over structured regulatory document tables; correctly documented without inflated vector claims.
12. **Tests**: **PASSING**. 100% pass across core test suites (`test_banking_foundation_e2e.py`, `test_transfer_security_and_support.py`, `test_investigator_graph.py`, `test_agent_and_persistence.py`, `test_network_graph_and_fund_tracing.py`, `test_api_cases.py`, `test_api_investigations.py`).
13. **Build**: **PASSING**. `npm --prefix frontend run build` compiles with 0 TypeScript/Vite errors.
14. **Bugs Fixed**:
    - Resolved cross-loop asyncpg connection leakage in capability wrappers via explicit rollback before close.
    - Fixed user seed uniqueness collision across username, email, and external ID.
    - Converted test suite fixtures to native async iterators with proper teardown.
    - Reconciled test assertions with updated Egyptian Pounds demo seed data and alert foreign key schema invariants.
15. **Remaining Problems**: Minor P1/P2 items documented in `TECHNICAL_DEBT.md` (e.g. ad-hoc alert generation for manual investigations).
16. **Documentation Changed**:
    - Created `docs/CURRENT_SYSTEM_AUDIT.md`
    - Created `docs/CANONICAL_ARCHITECTURE.md`
    - Created `docs/CANONICAL_ROADMAP.md`
    - Created `docs/TECHNICAL_DEBT.md`
    - Created `docs/AUDIT_HANDOFF.md`
    - Updated `SYSTEM_SUMMARY.md` and `README.md`
17. **Recommended Next Phase**: **PHASE 10: Multi-Agent Forensic Specialists & Dossier Synthesizer**.

---

## 3. Ready-to-Copy Prompt for the Next Stage

```markdown
# Antigravity Phase 10 Prompt — Omerta.ai Multi-Agent Forensic Specialists & Dossier Synthesizer

Act as a **Principal AI Architect, FinTech Security Engineer, and Lead LangGraph Developer**.

We have completed the full system audit and stabilization of Omerta.ai. All core banking, ledger invariants, 3-strike security holds, Neo4j projections, MCP servers, and persistence layers are 100% verified and tested.

Your task in this phase is to implement **PHASE 10: Multi-Agent Forensic Specialists & Dossier Synthesizer**.

---

### 1. Architectural Baseline & Existing Components to Reuse

You are building directly on top of the verified Omerta.ai codebase:
- **State Machine**: `apps/investigator/graph.py` and `apps/investigator/nodes.py`
- **State Schema**: `apps/investigator/state.py` (`InvestigationState`, `EvidenceItem`, `AuditEventItem`)
- **Capabilities / MCP Wrappers**: `apps/investigator/capabilities.py` (`TransactionCapability`, `GraphCapability`, `RiskCapability`, `KnowledgeCapability`)
- **LLM Abstraction**: `infrastructure/llm/factory.py`, `FakeLLMProvider`, `OpenAIProvider`
- **Persistence**: `infrastructure/database/persistence.py` (`persist_investigation`)
- **Domain Reports**: `domain/report.py` (`InvestigationReport`, `Typology`, `RecommendedAction`)

---

### 2. Objectives & Scope of Phase 10

Decompose the existing monolithic agent (`analyze_with_agent`) into a coordinated multi-specialist LangGraph sub-graph:

1. **Structuring & Smurfing Specialist Agent**:
   - Analyzes temporal bursts, amounts just below reporting thresholds ($10,000 USD / equivalent EGP), rapid multi-account fan-in/fan-out.
   - Outputs: Structuring confidence, specific evidence references, typology tags (`STRUCTURING`).

2. **Mule Network & Graph Specialist Agent**:
   - Analyzes graph paths, circular flow of funds, high out-degree pass-through accounts, and community clusters from Neo4j facts.
   - Outputs: Mule network confidence, path citations, typology tags (`MULE_ACCOUNT`, `LAYERING`).

3. **Cyber & Device Specialist Agent**:
   - Analyzes VPN/proxy indicators, multi-account device co-location, impossible travel velocity.
   - Outputs: Cyber risk confidence, device/IP citations, typology tags (`ACCOUNT_TAKEOVER`, `SYNTHETIC_IDENTITY`).

4. **Lead Dossier Synthesizer Agent**:
   - Collects specialist findings, eliminates redundant signals, resolves conflicting recommendations, and synthesizes the canonical `InvestigationReport`.
   - Generates executive narrative, evidence-grounded findings matrix, and actionable recommendation (`HUMAN_REVIEW`, `MONITOR`, `CLOSE_NO_ACTION`, `BLOCK`).

---

### 3. Strict Invariants & Constraints

- **Evidence Grounding**: Every specialist finding and the final synthesized report MUST only cite valid `evidence_id`s collected in the investigation state. Hallucinated IDs must fail validation and trigger self-repair.
- **Read-Only Invariant**: Specialist agents MUST NOT execute financial transactions, modify customer status, or perform irreversible mutations. They recommend actions.
- **Provider Agnostic**: Multi-agent graph must run deterministically offline with `FakeLLMProvider` in tests and seamlessly support `OpenAIProvider` / live endpoints.
- **Zero Regression**: All existing tests in `tests/test_banking_foundation_e2e.py`, `tests/test_transfer_security_and_support.py`, `tests/test_investigator_graph.py`, and `tests/test_agent_and_persistence.py` MUST remain passing.

---

### 4. Implementation Steps

1. Define specialist agent state schemas and prompt contracts in `apps/investigator/specialists/`.
2. Implement the specialist reasoning nodes and synthesizer node.
3. Update `apps/investigator/graph.py` StateGraph to fan-out to specialists and fan-in to the synthesizer.
4. Add unit and integration tests in `tests/test_multi_agent_specialists.py`.
5. Verify end-to-end execution from `/investigations/run` API through to persistence and frontend display.
```
