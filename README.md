# 🛡️ Omerta.ai — Next-Gen AI Agentic Financial Crime & Banking Platform

<div align="center">

![Omerta.ai Banner](https://img.shields.io/badge/Omerta.ai-Autonomous_AML_&_Fraud_Defense-0A192F?style=for-the-badge&logo=shield&logoColor=29C5D9)

**Enterprise-Grade Autonomous Financial Crime Investigation, Real-Time Fraud Prevention, Multi-Agent Forensics, and Secure Core Banking Platform.**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18.3-61DAFB?style=flat-square&logo=react&logoColor=black)](https://reactjs.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17_Alpine-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Neo4j 5](https://img.shields.io/badge/Neo4j-5.26_Graph-008CC1?style=flat-square&logo=neo4j&logoColor=white)](https://neo4j.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-FF6F00?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Protocol_Ready-8A2BE2?style=flat-square)](https://modelcontextprotocol.io)
[![SMTP](https://img.shields.io/badge/SMTP-Live_STARTTLS-EA4335?style=flat-square&logo=gmail&logoColor=white)](https://gmail.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

[Architecture](#-system-architecture) • [Features](#-core-capabilities--innovations) • [Credentials](#-master-credentials--accounts-reference-sheet) • [Quickstart](#-installation--quickstart-guide) • [API Reference](#-api-endpoints-reference) • [Testing](#-test-suite--verification)

</div>

---

## 🌟 Executive Summary

Traditional fraud detection platforms rely on static rule engines that flag suspicious activity but burden human analysts with manual evidence collection and disjointed triage.

**Omerta.ai** bridges modern fintech core banking with autonomous agentic artificial intelligence. It functions as both a **secure double-entry core banking system** and an **autonomous financial crime investigation platform**:
- 🔍 **Autonomously investigates *why* transactions are risky** by orchestrating specialized MCP tools across relational databases, graph databases, risk heuristics, and RAG knowledge bases.
- 🤖 **Multi-Agent Forensic Consensus**: Deploys specialized forensic sub-agents (Identity, Telemetry, Velocity, Compliance) to generate auditable SAR dossiers and evidence-backed investigative reports.
- 🛡️ **Real-Time Active Defense**: Enforces location velocity checks, live VPN/proxy detection, single-active-session constraints, and progressive 3-strikes password lockouts.
- ⚖️ **Human-in-the-Loop Safeguards**: AI agents recommend and generate evidence; irreversible regulatory actions (account freezing, SAR filings, risk resolution) strictly require authorized human review.

---

## 🏗️ System Architecture

```mermaid
flowchart TB
    subgraph ClientLayer [" Client Applications & Telemetry "]
        ReactSPA[" Modern React 18 SPA (Vite + Tailwind) "]
        CustomerPortal[" 👤 Customer Portal (Transfers & Security) "]
        AdminHub[" 🛡️ Command Center & Forensic Hub "]
        TelemetryStream[" 📡 Device, IP & Geolocation Telemetry "]
    end

    subgraph APIGateway [" FastAPI API Gateway (Port 8000) "]
        AuthService[" 🔐 JWT Auth & Session Enforcement "]
        RateLimiter[" ⚡ Security Middleware & Rate Limiting "]
        BankingRouter[" 💳 Banking & Double-Entry Transfers "]
        AdminRouter[" ⚙️ Staff Management & Problem Customer Hub "]
        InvestigatorRouter[" 🧠 Case Management & AI Forensics "]
    end

    subgraph MultiAgentEngine [" LangGraph Multi-Agent Forensic Engine "]
        Orchestrator[" 🤖 Lead Forensic Orchestrator "]
        IdentityAgent[" 🪪 Identity & KYC Agent "]
        TelemetryAgent[" 🌐 Telemetry & VPN Velocity Agent "]
        VelocityAgent[" 📈 Transaction Pattern & Velocity Agent "]
        ComplianceAgent[" 📜 AML Regulatory & Typology Agent "]
    end

    subgraph MCPServers [" Model Context Protocol (MCP) Tool Servers "]
        TxnMCP[" 📊 Transaction MCP Server "]
        GraphMCP[" 🕸️ Neo4j Graph MCP Server "]
        RiskMCP[" 🎯 Risk Engine MCP Server "]
        KnowledgeMCP[" 📚 AML Typology RAG MCP Server "]
    end

    subgraph PersistenceLayer [" Dual Enterprise Persistence Engine "]
        PostgresDB[(" 🐘 PostgreSQL 16 (Port 15432)\n• OLTP Ledger (SELECT FOR UPDATE)\n• Customers, Accounts & Users\n• Evidence Store & Audit Trails ")]
        Neo4jGraph[(" 🌐 Neo4j Graph 5.26 (Port 17687)\n• Entity Relationship Graph\n• Mule Networks & Layering Rings\n• Shared Device & IP Clusters ")]
    end

    subgraph ExternalServices [" External Communication Services "]
        GmailSMTP[" 📧 Gmail SMTP Relay (STARTTLS :587)\n• Password Reset Links\n• Security Lockout Notices "]
        LLMProvider[" 🧠 Groq / OpenAI LLM APIs "]
    end

    ReactSPA --> APIGateway
    CustomerPortal --> APIGateway
    AdminHub --> APIGateway
    TelemetryStream --> APIGateway

    APIGateway --> MultiAgentEngine
    APIGateway --> PersistenceLayer
    APIGateway --> ExternalServices

    MultiAgentEngine --> MCPServers
    MultiAgentEngine --> LLMProvider

    MCPServers --> PostgresDB
    MCPServers --> Neo4jGraph
```

---

## 🚀 Core Capabilities & Innovations

### 🏦 1. Double-Entry Core Banking Platform
- **Immutable Financial Ledger:** High-precision monetary storage (integer cents) across multiple currencies (**EGP, USD, EUR, GBP**) using strictly balanced double-entry accounting (`account_ledger_entries`).
- **Concurrency & Race Condition Protection:** Atomic debit/credit execution with pessimistic row-level locking (`SELECT ... FOR UPDATE`), preventing double-spend and balance overdrafts.
- **National Flag Picker & Multi-Currency Transfers:** Integrated international country code flags with automatic recipient lookup and real-time fee calculation.

```mermaid
sequenceDiagram
    autonumber
    actor Customer as 👤 Customer
    participant Frontend as 💻 React Web App
    participant API as 🛡️ FastAPI Gateway
    participant DB as 🐘 PostgreSQL (15432)
    participant Risk as 🎯 Risk Engine

    Customer->>Frontend: Enter transfer details & password
    Frontend->>API: POST /api/v1/customer/transfer
    API->>DB: Verify password & check failed counter (< 3)
    API->>Risk: Evaluate transaction risk & velocity
    alt Risk is Acceptable & Password Valid
        API->>DB: SELECT ... FOR UPDATE (Lock sender & recipient rows)
        API->>DB: Insert double-entry ledger entries & update balances
        API-->>Frontend: HTTP 200 (Transfer Complete)
    else Invalid Password (Attempt 1 or 2)
        API->>DB: Increment failed_transfer_attempts counter
        API-->>Frontend: HTTP 401 (Attempt X of 3 - Warning modal, keep session)
    else Invalid Password (Attempt 3)
        API->>DB: Set is_active=False, status=SUSPENDED, risk=CRITICAL
        API->>DB: Terminate all active sessions
        API-->>Frontend: HTTP 403 (Account Locked Out)
    end
```

---

### 🛡️ 2. Real-Time Security & Active Defense

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                    OMERTA.AI ACTIVE DEFENSE SUITE                       │
  ├───────────────────────┬─────────────────────────┬───────────────────────┤
  │  📍 Geolocation &     │  🌐 VPN & Proxy         │  🔐 Progressive       │
  │     Velocity Engine   │     Live Interception   │     3-Strikes Lockout │
  ├───────────────────────┼─────────────────────────┼───────────────────────┤
  │ Calculates physical   │ Detects commercial VPNs │ Attempts 1 & 2: Alert │
  │ distance & speed      │ and datacenter proxies. │ without logging out.  │
  │ (Haversine formula).  │ Blocks transfers with   │ Attempt 3: Immediate  │
  │ > 800 km/h triggers   │ an interactive warning. │ account suspension &  │
  │ CRITICAL risk flag.   │ Admin VPN = Auto-Lock.  │ admin intervention.   │
  └───────────────────────┴─────────────────────────┴───────────────────────┘
```

- **Impossible Travel Velocity:** Computes real-world geographic velocity between consecutive logins/transfers. If an account moves between distant cities (e.g. Cairo to Port Said) in minutes, the transaction is immediately elevated to **CRITICAL** risk.
- **VPN / Proxy Interception:** Detects known VPN exit nodes and hosting provider ASNs:
  - **Customers:** Prompts a dedicated security modal requiring VPN disconnection before funds can move.
  - **Administrators:** Automatically locks out admin accounts on VPN detection (`ADMIN_VPN_SECURITY_LOCK`) to prevent administrative session hijacking. Unlocking is automated upon reconnecting via a verified residential/office IP.
- **Single-Active-Session Enforcement:** When a user logs in from a new browser or device, prior sessions are gracefully terminated and notified in real-time.

---

### ✨ 3. Multi-Agent AI Forensic Investigation

When a transaction triggers an alert or an account enters high risk, the **LangGraph Agentic Orchestrator** summons a consensus panel of specialized AI agents:

```mermaid
flowchart LR
    subgraph Trigger [" Risk Event Trigger "]
        Alert[" 🚨 Alert / Suspicious Transfer "]
    end

    subgraph ConsensusPanel [" Multi-Agent Forensic Consensus Panel "]
        IA[" 🪪 Identity Agent\n• KYC History\n• Device Consistency "]
        TA[" 🌐 Telemetry Agent\n• IP Geolocation\n• VPN / ASN Intel "]
        VA[" 📈 Velocity Agent\n• Burst Frequency\n• Layering Patterns "]
        CA[" 📜 Compliance Agent\n• AML Typologies\n• SAR Thresholds "]
    end

    subgraph Synthesis [" Evidence Synthesis "]
        LeadAgent[" 🤖 Lead Forensic Orchestrator "]
        Dossier[" 📋 Evidence-Backed Audit Report\n• SHA-256 Hashed Evidence\n• Traceable Citations\n• Recommended Action "]
    end

    Alert --> ConsensusPanel
    IA --> LeadAgent
    TA --> LeadAgent
    VA --> LeadAgent
    CA --> LeadAgent
    LeadAgent --> Dossier
```

- **100% Grounded in Evidence:** Every finding in the generated investigation report cites verified database evidence items (`evidence_ids`). Unsupported assertions fail schema validation.
- **Anti-Hallucination & Prompt-Injection Guardrails:** Tool outputs and user inputs are strictly separated from system instructions. The agent cannot be coerced into changing transaction states.

---

### ✉️ 4. Live Transactional SMTP Email Relay

Omerta.ai features a production-grade SMTP dispatch engine built with Python's asynchronous executor and `smtplib` STARTTLS:
- **Verified Sender:** Transmits directly from `abdomostafa13571234@gmail.com` via `smtp.gmail.com:587`.
- **Responsive Security Templates:** Dispatches branded, high-contrast HTML emails with 15-minute cryptographically signed JWT reset tokens.
- **Admin Notice Dispatch:** Allows administrators to dispatch custom compliance notices directly to customers from the Problem Customer Center.

---

## 🔑 Master Credentials & Accounts Reference Sheet

Use these pre-seeded accounts to test all platform roles and permission boundaries:

| Role | Persona Name | Login Email / Username | Password | Account / Identifier | Initial Balance | Purpose & Permissions |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`ADMINISTRATOR`** | **Dr. Sarah Al-Rashid** | `admin@omerta.ai` / `admin` | `AdminPass123!` | System Super Admin | Platform Oversight | Root Super Admin (Immutable, User & Staff Management, Risk Tuning) |
| **`FRAUD_ANALYST`** | **Tariq Mansour** | `analyst@omerta.ai` / `analyst` | `AnalystPass123!` | Operations Sub-Admin | Case Operations | Case Review, Evidence Inspection, Risk Monitoring |
| **`INVESTIGATOR`** | **Laila El-Kady** | `investigator@omerta.ai` / `investigator` | `InvestigatorPass123!` | Senior Investigator | SAR Dispositions | SAR Filing, Multi-Agent Forensics, Case Resolution |
| **`COMPLIANCE_AUDITOR`** | **Omar Farooq** | `auditor@omerta.ai` / `auditor` | `AuditorPass123!` | Regulatory Sub-Admin | Audit & Telemetry | Read-Only Audit Trails, Compliance Verification |
| **`CUSTOMER`** | **Ziad Karim** | `ziad@omerta.ai` / `ziad_k` | `Customer@2026!` | `OMR-1092-4821` | `50,000.00 EGP` | P2P Transfers, Beneficiary Management, Device Security |
| **`CUSTOMER`** | **Layla Hassan** | `layla@omerta.ai` / `layla_h` | `Customer@2026!` | `OMR-3847-1920` | `25,000.00 EGP` | Multi-Currency Accounts, Transfer Recipient |
| **`CUSTOMER`** | **Amira El-Sayed** | `amira@omerta.ai` / `amira_e` | `Customer@2026!` | `OMR-7193-8402` | `100,000.00 EGP` | High-Net-Worth Profile, Velocity Scenarios |

---

## 🗄️ Database Architecture & Connection Details

The platform operates on a production-grade dual database architecture:

```
  ┌──────────────────────────────────────────────┐    ┌──────────────────────────────────────────────┐
  │         🐘 PostgreSQL 16 (Port 15432)        │    │          🌐 Neo4j Graph (Port 17687)         │
  ├──────────────────────────────────────────────┤    ├──────────────────────────────────────────────┤
  │ • Users, Roles & Session Authentication      │    │ • Customer, Account, Device & IP Nodes       │
  │ • Customers, Checking & Savings Accounts     │    │ • [:TRANSFERRED_TO] Transaction Edges        │
  │ • Double-Entry Immutable Ledger Entries      │    │ • [:USED_DEVICE] & [:USED_IP] Edges          │
  │ • SHA-256 Hashed Evidence & Investigation    │    │ • Mule Network Detection & Pass-Through Rings│
  │ • Append-Only Compliance Audit Events        │    │ • Graph Visualization & Cypher Query Engine  │
  └──────────────────────────────────────────────┘    └──────────────────────────────────────────────┘
```

### 1. Primary OLTP & Ledger Store (PostgreSQL 16)
- **Host & Port:** `localhost:15432` (Docker service `omerta-postgres`)
- **Database:** `omerta` | **User:** `omerta` | **Password:** `omerta_dev_password`
- **Async Connection String:** `postgresql+asyncpg://omerta:omerta_dev_password@localhost:15432/omerta`
- **ORM / Driver:** SQLAlchemy 2.0 Async Session + `asyncpg`

### 2. Financial Crime Knowledge Graph (Neo4j 5.26)
- **Host & Bolt Port:** `localhost:17687` | **HTTP Web UI:** `http://localhost:17474`
- **User:** `neo4j` | **Password:** `omerta_dev_password`

---

## 💻 Interactive Application Tour

### 👤 Customer Banking Portal
- **Dashboard Overview:** Real-time balances, recent transaction feed, quick-transfer actions, and active device health.
- **Send Money:** Dynamic national flag selection, recipient account validation, instant fee preview, and password authorization with 3-strikes visual countdown.
- **Security & Devices:** Live list of registered devices, active session eviction, login geography history, and VPN alert status.

### 🛡️ Operations & Forensic Hub
- **Command Dashboard:** Global telemetry metrics, real-time transaction throughput, active case pipeline, and risk severity distribution.
- **Problem Customer Center:** Dedicated triage view for accounts under review (e.g. 3 failed password attempts, impossible travel). Features:
  - 📞 **Click-to-Call Modal:** Direct telephone communication with verified customer contact info.
  - ✉️ **Send Notice:** Custom email dispatch via live SMTP relay.
  - ✨ **Agentic AI Forensic Report:** Instantly runs multi-agent forensic consensus and displays interactive evidence timeline.
  - 🔓 **One-Click Risk Resolution:** Restores `user.is_active = True`, resets failed attempts, and reactivates account.
- **Network Graph Explorer:** Interactive Neo4j visualization showing money flows, shared devices, and cyclic layering rings.
- **Audit Logs:** Immutable chronological log of every system authentication, transfer, and administrative action.

---

## 🛠️ Installation & Quickstart Guide

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (Fast Python 3.12 package manager)
- [Node.js 18+](https://nodejs.org) and `npm`
- [Docker & Docker Compose](https://www.docker.com/)

---

### 1. Clone & Configure Environment

```bash
# Clone the repository
git clone https://github.com/abo7adeed/Omerta.ai.git
cd Omerta.ai

# Copy the environment file
cp .env.example .env
```

Ensure your `.env` contains your desired settings:
```ini
# PostgreSQL (Port 15432 to avoid local 5432 collisions)
DATABASE_URL=postgresql+asyncpg://omerta:omerta_dev_password@localhost:15432/omerta

# Neo4j Graph Database
NEO4J_URI=bolt://localhost:17687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=omerta_dev_password

# SMTP Live Email Dispatch
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=abdomostafa13571234@gmail.com
SMTP_PASSWORD=your-gmail-app-password
SMTP_SENDER_EMAIL=abdomostafa13571234@gmail.com

# LLM Provider (Groq / OpenAI)
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b
LLM_API_KEY=your-groq-api-key
```

---

### 2. Launch Databases with Docker

```bash
# Start PostgreSQL 17 and Neo4j 5.26 containers
docker compose up -d postgres neo4j
```

---

### 3. Initialize Backend & Seed Database

```bash
# 1. Sync dependencies with uv
uv sync

# 2. Run database migrations
uv run alembic upgrade head

# 3. Seed deterministic development scenarios and staff accounts
uv run python -m infrastructure.database.seed

# 4. Project facts into Neo4j graph database
uv run python -m infrastructure.neo4j.seed
```

---

### 4. Start the Application

#### Terminal 1 — FastAPI Backend (Port 8000)
```bash
uv run uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

#### Terminal 2 — React Frontend (Port 5173)
```bash
cd frontend
npm install
npm run dev
```
- Web Application: `http://localhost:5173`

---

## 📡 API Endpoints Reference

### 🔐 Authentication & Session Endpoints
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/login` | Authenticate with username/password, check active sessions & VPN |
| `POST` | `/api/v1/auth/logout` | Terminate session and remove device token |
| `GET` | `/api/v1/auth/me` | Fetch active profile, role, permissions, and customer data |
| `POST` | `/api/v1/auth/forgot-password` | Dispatch live password reset email with JWT authorization token |
| `POST` | `/api/v1/auth/reset-password` | Verify token and update user password |

### 💳 Customer Banking Endpoints
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/customer/dashboard` | Retrieve accounts, total balance, recent transactions & notifications |
| `POST` | `/api/v1/customer/transfer` | Execute password-protected transfer with 3-strikes lockout logic |
| `GET` | `/api/v1/customer/transactions` | Paginated transaction history with search & filter |
| `GET` | `/api/v1/customer/security` | Active sessions, registered devices, and security event log |

### 🛡️ Administrative & Risk Endpoints
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/admin/problem-customers` | List all locked-out, high-risk, or suspended customer accounts |
| `POST` | `/api/v1/admin/problem-customers/{id}/resolve` | 1-Click resolve risk, reset failed counters, and reactivate user |
| `POST` | `/api/v1/admin/problem-customers/{id}/notify` | Send custom email/SMS notice via live SMTP |
| `GET` | `/api/v1/admin/problem-customers/{id}/agentic-summary` | Generate real-time multi-agent consensus report |
| `GET` | `/api/v1/admin/staff` | List staff accounts (Admins, Analysts, Investigators, Auditors) |
| `POST` | `/api/v1/admin/staff` | Provision new staff member with role-based access control |

---

## 🧪 Test Suite & Verification

The platform is guarded by a comprehensive, fully automated test suite running against an isolated `omerta_test` database:

```bash
# Run the complete test suite
uv run pytest

# Run specific domain & security integration suites
uv run pytest tests/test_stage2_banking_and_admin.py tests/test_auth_session_reset_and_rbac.py
```

### Coverage Highlights:
- ✅ **100% Pass Rate across 26+ Banking & Auth Integration Scenarios**
- ✅ Password 3-Strikes lockout, warning modals, and session eviction
- ✅ Multi-currency double-entry ledger atomicity and row locking
- ✅ Admin VPN auto-lockout and Root Super Admin protection
- ✅ SHA-256 evidence integrity hashing and forensic reconstruction
- ✅ Live SMTP STARTTLS email formatting and JWT token verification

---

## 📂 Repository Layout

```text
Omerta.ai/
├── apps/
│   ├── api/                     # FastAPI application & v1 route handlers
│   │   ├── v1/                  # Auth, Customer, Admin, Cases, Risk, Network APIs
│   │   └── main.py              # Application entrypoint & security middleware
│   └── investigator/            # LangGraph multi-agent forensic state machine
├── domain/                      # Core business logic, schemas, and services
│   ├── services/                # Banking, Transfer, Email, Risk, Velocity services
│   ├── evidence.py              # SHA-256 evidence model & hashing algorithms
│   └── report.py                # Typed investigation report schema
├── frontend/                    # React 18 + TypeScript + Vite + Tailwind UI
│   ├── src/                     # Contexts, Pages, Components & Telemetry
│   └── package.json             # Frontend dependencies
├── infrastructure/              # Database, Neo4j, LLM & Security adapters
│   ├── database/                # SQLAlchemy models, sessions, repositories & seed
│   ├── neo4j/                   # Neo4j graph client, repository & projections
│   └── security/                # JWT tokens, password hashing & rate limiting
├── mcp_servers/                 # Model Context Protocol servers
│   ├── transaction_server/      # Read-only transaction MCP interface
│   ├── graph_server/            # Neo4j relationship intelligence MCP
│   ├── risk_server/             # Real-time risk heuristics MCP
│   └── knowledge_server/        # AML typologies & regulations RAG MCP
├── migrations/                  # Alembic database migration scripts
├── tests/                       # Pytest test suites (unit, e2e, security, agentic)
├── docker-compose.yml           # Multi-container orchestration (Postgres, Neo4j)
├── pyproject.toml               # Project metadata & Python dependencies
└── README.md                    # Project documentation
```

---

<div align="center">

**Built with precision for next-generation financial intelligence and autonomous crime prevention.**

*Omerta.ai &copy; 2026. All rights reserved.*

</div>
