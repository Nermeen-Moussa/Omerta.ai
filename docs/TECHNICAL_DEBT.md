# Omerta.ai — Technical Debt & Architectural Backlog

**Document Version**: 1.0.0  
**Audit Baseline**: Post-Audit Review (October 6, 2026)

---

## Priority Classification

| Priority | Category | Description |
|---|---|---|
| **P0** | Security / Data Integrity | Immediate risk to ledger balance, customer isolation, or evidence tampering. |
| **P1** | Functional Bugs | Defect in core banking, support, or investigation execution. |
| **P2** | Architecture | Structural debt, tight coupling, or suboptimal resource management. |
| **P3** | UI/UX | Frontend polish, responsiveness, or visual clarity improvements. |
| **P4** | Documentation | Stale comments, outdated diagrams, or inaccurate descriptions. |
| **P5** | Nice-to-have | Enhancements, non-critical optimizations, developer quality of life. |

---

## 1. P0 — Security / Data Integrity

### DEBT-P0-01: Cross-Loop asyncpg Driver Lifecycle
- **Problem**: When running multiple asynchronous tasks or sub-processes without explicit context-local engine binding, asyncpg connection objects can be garbage-collected across loop boundaries, emitting `SAWarning` or connection teardown errors.
- **Impact**: Potential resource leakage or connection pool exhaustion under sustained concurrency.
- **Location**: [`infrastructure/database/session.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/database/session.py), [`apps/investigator/capabilities.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/apps/investigator/capabilities.py).
- **Resolution**: Implemented explicit `session.rollback()` in all capability wrapper `finally:` blocks. Engine pool defaults to `NullPool` in tests.
- **Status**: **RESOLVED** in this audit.

---

## 2. P1 — Functional Bugs

### DEBT-P1-01: Investigation Case Alert Linkage Requirement
- **Problem**: The relational schema requires `alert_id` on `investigation_cases` (not nullable). Persisting an investigation run on a transaction that did not trigger an alert caused unhandled `ValueError`.
- **Impact**: Investigations on normal transactions could not be durably recorded without explicitly providing or generating an associated review alert.
- **Location**: [`infrastructure/database/persistence.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/database/persistence.py).
- **Recommended Fix**: For manual/analyst-triggered investigations on non-alerted transactions, auto-generate an ad-hoc `MANUAL_INVESTIGATION` alert row so the foreign key constraint is satisfied.
- **Priority**: **P1**

---

## 3. P2 — Architecture

### DEBT-P2-01: Single Monolithic Agent Node in LangGraph
- **Problem**: The current LangGraph investigator uses a single monolithic agent node (`analyze_with_agent`) to evaluate structuring, mule accounts, device anomalies, and sanctions simultaneously.
- **Impact**: Large prompt token footprint, potential cognitive overload on complex multi-typology fraud rings, and difficult modular testing.
- **Location**: [`apps/investigator/graph.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/apps/investigator/graph.py), [`apps/investigator/agent.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/apps/investigator/agent.py).
- **Recommended Fix**: Decompose into specialist sub-agents (Structuring Specialist, Mule Specialist, Cyber Specialist, Lead Synthesizer) in Phase 10.
- **Priority**: **P2**

### DEBT-P2-02: Synchronous Graph Resync in Development
- **Problem**: Neo4j projection is currently executed synchronously or in batch (`project_all`). Under high transaction volume, live changes in PostgreSQL should stream to Neo4j via transactional outbox or async workers.
- **Impact**: Neo4j may be briefly stale until the next sync cycle.
- **Location**: [`infrastructure/neo4j/projection.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/neo4j/projection.py).
- **Recommended Fix**: Implement transactional outbox pattern or post-commit database event hooks in Phase 11.
- **Priority**: **P2**

---

## 4. P3 — UI / UX

### DEBT-P3-01: Large Frontend Bundle Chunk Size
- **Problem**: `dist/assets/index-9YUKVI63.js` is ~1.2 MB uncompressed (~303 kB gzipped) due to bundled charting and graph libraries (`recharts`, `lucide-react`, `d3-interpolate`).
- **Impact**: Initial page load time on slow mobile networks.
- **Location**: `frontend/vite.config.ts`, `frontend/src/App.tsx`.
- **Recommended Fix**: Implement `React.lazy()` and dynamic `import()` for Admin Network Graph and Investigation Dossier pages.
- **Priority**: **P3**

---

## 5. P4 — Documentation

### DEBT-P4-01: Reconcile Stale "Vector DB / ML" References
- **Problem**: Early legacy drafts occasionally used marketing terms like "Vector Embeddings" or "Neural ML Engine" for components that are actually deterministic TF-IDF and heuristic rules.
- **Impact**: Confusion for developers and audit discrepancies.
- **Location**: Repository root documentation and docstrings.
- **Resolution**: Reconciled and corrected in `SYSTEM_SUMMARY.md`, `CURRENT_SYSTEM_AUDIT.md`, and `CANONICAL_ARCHITECTURE.md`.
- **Status**: **RESOLVED** in this audit.

---

## 6. P5 — Nice-to-Have

### DEBT-P5-01: Synthetic Scenario Selector in Frontend
- **Problem**: Triggering specific fraud topologies (smurfing bursts, mule chains) in manual testing requires executing specific transaction sequences.
- **Impact**: Minor friction during live demonstrations.
- **Location**: `frontend/src/pages/admin/RiskMonitoring.tsx`.
- **Recommended Fix**: Add a developer "Scenario Trigger" dropdown in the Admin console for instant demonstration playback.
- **Priority**: **P5**
