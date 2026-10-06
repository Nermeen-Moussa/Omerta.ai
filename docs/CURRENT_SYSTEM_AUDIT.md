# Omerta.ai — Current System Audit & Subsystem Inventory

**Document Version**: 1.0.0  
**Audit Date**: October 6, 2026  
**Auditors**: Senior Software Architect, FinTech Backend Engineer, Security Engineer, QA Engineer, Frontend Architect  
**Scope**: Full Stack (FastAPI Backend, React/Vite Frontend, PostgreSQL 17, Neo4j 5.26, LangGraph, MCP Servers, Deterministic Risk Engine)

---

## 1. Executive Subsystem Inventory

### 1.1 Backend Subsystems

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                 FASTAPI API GATEWAY                              │
│  /api/v1/auth   /api/v1/accounts   /api/v1/transfers   /api/v1/tickets   /cases  │
└────────┬───────────────────┬───────────────────┬──────────────────┬──────────────┘
         │                   │                   │                  │
         ▼                   ▼                   ▼                  ▼
┌──────────────────┐┌──────────────────┐┌──────────────────┐┌─────────────────────┐
│ Customer Banking ││ Security/3-Strike││  Support/Ticket  ││ Risk Intelligence   │
│ - Double-entry   ││ - Non-logout hold││ - Lifecycle      ││ - Deterministic     │
│ - Isolation      ││ - 3 wrong pwds   ││ - Restoration    ││   Rules (0-100)     │
│ - Ledger audit   ││ - Auto ticket    ││ - Identity verify││ - Model: mock-v1    │
└────────┬─────────┘└────────┬─────────┘└────────┬─────────┘└────────┬────────────┘
         │                   │                   │                   │
         └───────────────────┼───────────────────┼───────────────────┘
                             ▼                   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            PRIMARY SOURCE OF TRUTH                               │
│                   PostgreSQL 17 (Relational Database & Ledger)                   │
└────────────────────────────────────┬─────────────────────────────────────────────┘
                                     │
                 Projection / Tracing│ (Idempotent Cypher Sync)
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           GRAPH PROJECTION & TOPOLOGY                            │
│                  Neo4j 5.26 (Accounts, Devices, IPs, Transfers)                  │
└────────────────────────────────────┬─────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           MCP TOOL & REASONING LAYER                             │
│       Transaction MCP  │  Graph MCP  │  Risk Signals MCP  │  Knowledge MCP       │
└────────────────────────────────────┬─────────────────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         LANGGRAPH INVESTIGATION PIPELINE                         │
│  initialize -> load_txn -> load_account -> load_graph -> load_risk -> load_rag   │
│  -> analyze_with_agent (Fake/OpenAI) -> assemble_evidence (SHA-256 Grounding)    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Deep-Dive Subsystem Audit

### 2.1 Authentication & RBAC
- **Implementation**: [`infrastructure/security/jwt_auth.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/security/jwt_auth.py), [`apps/api/v1/auth.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/apps/api/v1/auth.py).
- **Login**: `POST /api/v1/auth/login` verifies bcrypt password hash, generates HMAC-SHA256 JWT access token with 8-hour expiry.
- **Logout**: `POST /api/v1/auth/logout` revokes session, records audit event.
- **Sessions**: Session table in PostgreSQL tracks `ip_address_id`, `device_id`, `user_agent`, `created_at`, `expires_at`, `is_active`.
- **Password Reset**: Admin-assisted or support ticket workflow.
- **RBAC**: Enforced via FastAPI dependency `require_roles(...)`.
  - Roles: `ADMINISTRATOR`, `FRAUD_ANALYST`, `SENIOR_INVESTIGATOR`, `AUDITOR`, `CUSTOMER`.
- **Role Enforcement & Isolation**: Customers can only query their own accounts, transfers, devices, and tickets. Staff roles are required for `/api/v1/admin/*`, `/cases`, `/investigations`, and staff operations.

---

### 2.2 Customer Banking & Core Ledger
- **Implementation**: [`domain/services/account_service.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/domain/services/account_service.py), [`domain/services/transfer_service.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/domain/services/transfer_service.py), [`infrastructure/database/models.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/database/models.py).
- **Customer Registration**: Creates `User` and linked `Customer` profile with unique Omerta User Number (e.g. `OMR-1092-4821`).
- **Account Ownership**: Each account belongs to a verified `customer_id`.
- **Double-Entry Invariant**: Every transfer creates exactly two balanced `AccountLedgerEntry` rows in an atomic PostgreSQL transaction:
  $$\text{Debit}(\text{Sender}) = \text{Credit}(\text{Recipient})$$
  $$\sum \text{Debits} = \sum \text{Credits}$$
- **Concurrency & Atomicity**: Sender account is locked using `SELECT ... FOR UPDATE` before balance check and debit to prevent overdraft or double-spend race conditions.
- **Currency Handling**: Transfers enforce single-currency matching (`EGP == EGP`, `USD == USD`). Multi-currency transfers without FX conversion are rejected with HTTP 400.

---

### 2.3 Three-Strike Security Workflow
- **Implementation**: [`domain/services/transfer_service.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/domain/services/transfer_service.py), [`domain/services/customer_service.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/domain/services/customer_service.py).
- **Mechanism**:
  - Strike 1: Wrong transfer password $\rightarrow$ HTTP 401, strike count = 1, warning displayed, login session preserved.
  - Strike 2: Wrong transfer password $\rightarrow$ HTTP 401, strike count = 2, warning displayed, login session preserved.
  - Strike 3: Wrong transfer password $\rightarrow$ HTTP 403 `TRANSFER_LOCKED`, customer `transfer_status` set to `BLOCKED`, auto-creates support ticket (`category="TRANSFER_SECURITY"`), creates audit event, **login session remains active**.
- **Customer Capabilities while Blocked**:
  - Can browse dashboard, view accounts, review ledger, read/send support messages.
  - CANNOT send transfers or authorize outgoing funds.
- **Transfer Password Reset**: Customer cannot self-unblock without completing staff identity verification and ticket restoration.

---

### 2.4 Support, Tickets & Restoration Workflow
- **Implementation**: [`domain/services/ticket_service.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/domain/services/ticket_service.py), [`apps/api/v1/tickets.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/apps/api/v1/tickets.py).
- **Ticket Lifecycle**: `OPEN` $\rightarrow$ `IN_REVIEW` $\rightarrow$ `PENDING_CUSTOMER` $\rightarrow$ `RESOLVED` / `CLOSED`.
- **Critical Policy — Separation of Concerns**:
  $$\text{Ticket Resolution} \neq \text{Transfer Restoration}$$
  Resolving or closing a support ticket DOES NOT unblock customer transfers.
- **Restoration Workflow**:
  1. Customer identity verified by staff.
  2. Staff executes `POST /api/v1/tickets/{id}/restore-transfer`.
  3. Creates durable `TransferRestoration` row with authorized staff user ID, tier, and rationale.
  4. Sets customer `transfer_status = "ACTIVE"`, resets `failed_transfer_password_attempts = 0`.
  5. Forces customer to set a new transfer password.
  6. Emits immutable `AUDIT_EVENT` (`TRANSFER_RESTORED`).

---

### 2.5 Risk Engine & Deterministic Scoring Contract
- **Implementation**: [`domain/services/risk_service.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/domain/services/risk_service.py), [`infrastructure/risk/mock_provider.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/risk/mock_provider.py).
- **Nature of System**: Strictly **Deterministic Rules & Heuristics** with explicit provenance `source="MOCK"`, `model_version="mock-risk-v1"`. It is NOT an ML/neural model.
- **Canonical Risk Contract**:
  - $0.00 - 39.99$: `LOW` / Normal flow.
  - $40.00 - 69.99$: `MEDIUM` / Review required (generates review alert).
  - $70.00 - 89.99$: `HIGH` / High priority review.
  - $90.00 - 100.00$: `CRITICAL` / Urgent AML/Fraud review.
- **Evaluated Signals**:
  - `NEW_DEVICE`: Unrecognized device fingerprint (+15 pts).
  - `VPN_INDICATOR`: Known VPN/Proxy ASN indicator (+25 pts).
  - `IMPOSSIBLE_TRAVEL`: Geo-velocity mismatch > 800 km/h (+35 pts).
  - `SHARED_DEVICE`: Device associated with $\ge 2$ distinct customer accounts (+30 pts for 2, +50 pts for $\ge 3$).
  - `SHARED_IP`: IP associated with $\ge 3$ distinct customer accounts (+20 pts).
  - `STRUCTURING_BURST`: $\ge 3$ outbound transfers within 10 minutes totaling near reporting thresholds (+40 pts).

---

### 2.6 Network & Graph Intelligence (PostgreSQL $\rightarrow$ Neo4j)
- **Implementation**: [`infrastructure/neo4j/client.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/neo4j/client.py), [`infrastructure/neo4j/projection.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/neo4j/projection.py), [`domain/services/graph_service.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/domain/services/graph_service.py).
- **Source of Truth**: PostgreSQL is the immutable source of financial truth. Neo4j is an index/projection for structural graph traversals.
- **Graph Nodes**: `(:Account)`, `(:Customer)`, `(:Device)`, `(:IPAddress)`.
- **Graph Edges**: `[:TRANSFERRED_TO]`, `[:ACCESSED_FROM]`, `[:OPERATES_ON]`, `[:ORIGINATED_AT]`.
- **Idempotent Projection**: `project_all(engine)` re-syncs state using Cypher `MERGE` statements tagged with `projection` namespace (`'dev'` or `'test'`).
- **Graph Queries**:
  - `get_account_neighbors(account_id, limit)`
  - `find_connected_accounts(account_id, limit)`
  - `find_shared_devices(account_id, limit)`
  - `find_shared_ips(account_id, limit)`
  - `find_transaction_paths(source_id, target_id, max_depth)`
  - `find_fraud_ring(account_id, max_depth, limit)`

---

### 2.7 Model Context Protocol (MCP) Tool Layer
- **Implementation**: `mcp_servers/`
  1. `mcp_servers/transaction_server.py`: Tools for querying transactions, accounts, recipient history, device history, IP history.
  2. `mcp_servers/graph_server.py`: Tools for graph neighborhood, connected accounts, shared infrastructure, fund paths.
  3. `mcp_servers/risk_server.py`: Tools for deterministic risk scores, feature breakdown, rule activations.
  4. `mcp_servers/knowledge_server.py`: Tools for regulatory typology search and AML guidelines.
- **Safety Invariant**: All MCP tools are **100% read-only**. No MCP tool can transfer funds, freeze accounts, modify passwords, or file regulatory SARs.

---

### 2.8 LangGraph Investigation Pipeline
- **Implementation**: [`apps/investigator/graph.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/apps/investigator/graph.py), [`apps/investigator/nodes.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/apps/investigator/nodes.py), [`apps/investigator/agent.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/apps/investigator/agent.py).
- **Execution Graph**:
  ```
  START -> initialize_investigation -> load_transaction (checks existence)
        -> load_account_context -> load_graph_context -> load_risk_context
        -> load_knowledge_context -> analyze_with_agent -> assemble_evidence -> END
  ```
- **Error Routing**: If transaction not found or fatal error occurs, routes directly to `END` with `status="FAILED"`.
- **Evidence Grounding**: Every node produces `EvidenceItem` with category, description, and source data. `assemble_evidence` computes deterministic SHA-256 content hashes.
- **Agent Reasoning**: Evaluates evidence against AML typologies (`STRUCTURING`, `MULE_ACCOUNT`, `ACCOUNT_TAKEOVER`, `RAPID_MOVEMENT`). Recommends actions (`HUMAN_REVIEW`, `MONITOR`, `CLOSE_NO_ACTION`, `BLOCK`).

---

### 2.9 LLM Provider & Fallback Layer
- **Implementation**: [`infrastructure/llm/factory.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/llm/factory.py), [`infrastructure/llm/fake_provider.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/llm/fake_provider.py), [`infrastructure/llm/openai_provider.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/infrastructure/llm/openai_provider.py).
- **Provider Abstraction**:
  - `FakeLLMProvider`: Deterministic offline provider for unit tests and local runs with zero API keys required.
  - `OpenAIProvider`: Live LLM provider compatible with OpenAI, Groq, or local vLLM/Ollama endpoints.
- **Validation & Self-Repair**: Agent output is strictly validated against Pydantic schema. If an LLM hallucinates an invalid evidence ID, self-repair pass runs. If repair fails, deterministic rule-based fallback executes safely.
- **Credential Safety**: No API keys, passwords, or JWT secrets are ever logged or serialized into evidence.

---

### 2.10 Knowledge & Regulatory Corpus (RAG Reality Check)
- **Implementation**: [`domain/services/knowledge_service.py`](file:///home/abdo/Desktop/Final%20Project%20Nti/Omerta.ai/domain/services/knowledge_service.py), `infrastructure/database/models.py` (`KnowledgeDocument`, `KnowledgeChunk`).
- **Truth Invariant**: This subsystem is an **In-Memory TF-IDF + Keyword / Metadata Search** over structured PostgreSQL rows.
- **Documentation Correction**: We do NOT falsely claim this is a "vector database" or "ChromaDB/Pinecone". It is a reliable, deterministic text retrieval engine for regulatory guidance (FinCEN, FATF, EML, Omerta AML Manual).

---

## 3. Frontend Audit Matrix

| Route | Role | Backend API | Real Data? | Mock Data? | Complete? | Issues / Status |
|---|---|---|---|---|---|---|
| `/login` | Public | `POST /api/v1/auth/login` | Real API | None | Yes | Fully functional, stores JWT, redirects by role. |
| `/register` | Public | `POST /api/v1/auth/register` | Real API | None | Yes | Creates user and customer records with auto-generated Omerta ID. |
| `/customer/dashboard` | Customer | `GET /api/v1/accounts/me`, `/api/v1/transfers/me` | Real API | None | Yes | Displays real balances, recent activity, transfer status. |
| `/customer/accounts` | Customer | `GET /api/v1/accounts/me` | Real API | None | Yes | Displays accounts, balances, IBANs, currencies. |
| `/customer/transactions` | Customer | `GET /api/v1/transfers/me` | Real API | None | Yes | Displays customer ledger history with status badges. |
| `/customer/transfer` | Customer | `POST /api/v1/transfers/send` | Real API | None | Yes | Form enforces transfer password, live recipient validation, 3-strike hold banner. |
| `/customer/security` | Customer | `GET /api/v1/customers/me/security` | Real API | None | Yes | Shows transfer lock status, password reset action, active devices. |
| `/customer/support` | Customer | `GET /api/v1/tickets/me`, `POST /api/v1/tickets` | Real API | None | Yes | Lists customer tickets, creates new ticket, real-time message thread. |
| `/customer/profile` | Customer | `GET /api/v1/customers/me` | Real API | None | Yes | Displays KYC verified status, national ID, phone, email. |
| `/admin/dashboard` | Staff | `GET /api/v1/admin/stats` | Real API | None | Yes | Aggregates active users, total volume, pending alerts, locked accounts. |
| `/admin/customers` | Staff | `GET /api/v1/admin/customers` | Real API | None | Yes | Customer management table with search, filter, and lock status. |
| `/admin/accounts` | Staff | `GET /api/v1/admin/accounts` | Real API | None | Yes | System-wide accounts, balance overview, currency breakdown. |
| `/admin/transactions` | Staff | `GET /api/v1/admin/transactions` | Real API | None | Yes | Global transaction monitoring table with risk scores. |
| `/admin/risk-monitoring` | Staff | `GET /api/v1/admin/risk-alerts` | Real API | None | Yes | Live risk alert triage queue with score thresholds. |
| `/admin/support` | Staff | `GET /api/v1/admin/tickets` | Real API | None | Yes | Admin support queue, ticket assignment, reply, and transfer restoration. |
| `/admin/devices` | Staff | `GET /api/v1/admin/devices` | Real API | None | Yes | Device intelligence, multi-account co-location badges, IP tracking. |
| `/admin/network` | Staff | `GET /api/v1/admin/network-graph` | Real API | None | Yes | Interactive 2D network visualization of fund flows and shared devices. |
| `/admin/investigations` | Staff | `GET /investigations`, `POST /investigations/run` | Real API | None | Yes | Investigation queue, triggering runs, viewing evidence. |
| `/admin/investigations/:id`| Staff | `GET /investigations/{id}` | Real API | None | Yes | Complete investigation dossier with findings, evidence, audit trail. |
| `/admin/audit-logs` | Staff | `GET /api/v1/admin/audit-events` | Real API | None | Yes | Immutable security audit event log with actor metadata. |
| `/admin/settings` | Staff | `GET /api/v1/admin/settings` | Real API | None | Yes | System configuration, threshold adjustments, provider health. |

---

## 4. Backend API Endpoints Audit

```
-------------------------------------------------------------------------------------------------------------------------
METHOD  PATH                                  ROLE         AUTH  OWNER CHECK  DATABASE EFFECT     TEST COVERAGE
-------------------------------------------------------------------------------------------------------------------------
POST    /api/v1/auth/login                    Public       No    N/A          Creates Session     test_auth.py
POST    /api/v1/auth/register                 Public       No    N/A          Inserts User/Cust   test_auth.py
POST    /api/v1/auth/logout                   Authenticated Yes  N/A          Deactivates Session test_auth.py
GET     /api/v1/accounts/me                   Customer     Yes   Customer ID  Read-only           test_banking.py
GET     /api/v1/transfers/me                  Customer     Yes   Customer ID  Read-only           test_banking.py
POST    /api/v1/transfers/send                Customer     Yes   Account ID   Double-entry Ledger test_transfers.py
GET     /api/v1/customers/me/security         Customer     Yes   Customer ID  Read-only           test_security.py
GET     /api/v1/tickets/me                    Customer     Yes   Customer ID  Read-only           test_tickets.py
POST    /api/v1/tickets                       Customer     Yes   Customer ID  Inserts Ticket      test_tickets.py
POST    /api/v1/tickets/{id}/messages         Authenticated Yes  Ticket Owner Inserts Msg/Audit   test_tickets.py
POST    /api/v1/tickets/{id}/restore-transfer Staff Only   Yes   Admin Role   Updates TransferSt  test_tickets.py
GET     /api/v1/admin/stats                   Staff Only   Yes   Admin Role   Read-only           test_admin.py
GET     /api/v1/admin/customers               Staff Only   Yes   Admin Role   Read-only           test_admin.py
GET     /api/v1/admin/devices                 Staff Only   Yes   Admin Role   Read-only           test_admin.py
GET     /api/v1/admin/network-graph           Staff Only   Yes   Admin Role   Read-only / Neo4j   test_admin.py
POST    /investigations/run                   Staff Only   Yes   Admin Role   Runs LangGraph      test_investigations.py
GET     /investigations                       Staff Only   Yes   Admin Role   Read-only           test_cases.py
GET     /investigations/{id}                  Staff Only   Yes   Admin Role   Read-only           test_cases.py
GET     /investigations/{id}/report           Staff Only   Yes   Admin Role   Read-only           test_cases.py
GET     /investigations/{id}/evidence         Staff Only   Yes   Admin Role   Read-only           test_cases.py
GET     /investigations/{id}/audit            Staff Only   Yes   Admin Role   Read-only           test_cases.py
-------------------------------------------------------------------------------------------------------------------------
```

---

## 5. Security & Isolation Verification

1. **Customer Isolation**:
   - Customers querying `/api/v1/accounts/{id}` where account does not belong to them receive `HTTP 404 NOT_FOUND` or `HTTP 403 FORBIDDEN`.
   - Customer token used against `/api/v1/admin/*` or `/investigations` receives `HTTP 403 FORBIDDEN`.
2. **SQL Injection**: All database queries use SQLAlchemy 2.0 async parameterized queries (`select(...)`, `where(...)`). No string interpolation in SQL.
3. **Cypher Injection**: Graph queries in `domain/services/graph_service.py` and `infrastructure/neo4j/` use Cypher parameter maps (`$account_id`, `$projection`).
4. **Evidence Immutability**: Persistence layer validates SHA-256 content hashes. Any attempt to modify an existing evidence row's content results in `IntegrityError`.
