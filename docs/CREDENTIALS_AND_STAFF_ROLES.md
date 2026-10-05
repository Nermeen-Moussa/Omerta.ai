# Omerta.ai — Credentials, Roles & Privileges Sheet

This document contains the complete offline credentials reference sheet for **Omerta.ai**.
All test demo chips and exposed credentials have been completely removed from the public UI to ensure an enterprise-grade banking experience.

---

## 🛡️ Administrative & Operations Staff Accounts

| Full Name | Role | Email / Username | Password | Assigned Operational Privileges |
| :--- | :--- | :--- | :--- | :--- |
| **Dr. Sarah Al-Rashid** | `ADMINISTRATOR` | `admin@omerta.ai` / `admin` | `AdminPass123!` | **Full Platform Authority**<br>• Create Sub-Admins & Operational Staff<br>• User Management (Suspend/Activate)<br>• Review Flagged Transactions<br>• Ledger-backed Balance Adjustments<br>• Audit Logs & Telemetry<br>• Export Compliance Reports<br>• Risk Engine Threshold Tuning |
| **Tariq Mansour** | `FRAUD_ANALYST` | `analyst@omerta.ai` / `analyst` | `AnalystPass123!` | • Review Flagged Transactions (`risk_score > 40.00`)<br>• Inspect Customer Risk Summaries<br>• Escalate/Resolve Investigation Cases |
| **Laila El-Kady** | `INVESTIGATOR` | `investigator@omerta.ai` / `investigator` | `InvestigatorPass123!` | • Case Dispositions & SAR Filing<br>• Review Evidence & Entity Relationships<br>• Escalate to Financial Intelligence Unit |
| **Omar Farooq** | `COMPLIANCE_AUDITOR` | `auditor@omerta.ai` / `auditor` | `AuditorPass123!` | • Read-only Audit Logs Inspection<br>• Telemetry & Compliance Data Export<br>• Verification Status Review |

---

## 👤 Pre-Configured Customer Banking Accounts

| Customer Name | Declared Country | Phone Number | Omerta User Number | Login Email / Username | Password | Initial Balance |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Ziad Karim** | 🇪🇬 Egypt (`+20`) | `+20 10 1111 2222` | `OMR-1092-4821` | `ziad@omerta.ai` / `ziad_k` | `Customer@2026!` | `50,000.00 EGP` |
| **Layla Hassan** | 🇪🇬 Egypt (`+20`) | `+20 10 2222 3333` | `OMR-3847-1920` | `layla@omerta.ai` / `layla_h` | `Customer@2026!` | `25,000.00 EGP` |
| **Amira El-Sayed** | 🇪🇬 Egypt (`+20`) | `+20 10 3333 4444` | `OMR-7193-8402` | `amira@omerta.ai` / `amira_e` | `Customer@2026!` | `100,000.00 EGP` |

---

## ⚙️ Sub-Admin & Staff Provisioning Feature

Administrators can provision and manage sub-admins directly from the **Admin Control Center**:
1. Log in as `admin@omerta.ai`.
2. Navigate to **User Management** (`/customers`).
3. Click the **"Sub-Admins & Staff"** tab.
4. Click **"Create Sub-Admin / Staff"** to configure:
   - Full Name, Email, Username, Password
   - Assigned Role (`ADMINISTRATOR`, `FRAUD_ANALYST`, `INVESTIGATOR`, `COMPLIANCE_AUDITOR`)
   - Granular Privileges:
     - 👥 **User Management**: Suspend or activate customer accounts
     - ⚠️ **Review Flagged Transactions**: Triage suspicious peer-to-peer transfers
     - ⚖️ **Balance Adjustments**: Adjust account balances with ledger justification
     - 📋 **Audit & Telemetry**: Inspect system events and login activities
     - 📄 **Compliance Reports**: Generate and export regulatory filings
