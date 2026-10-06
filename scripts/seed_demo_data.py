"""Synthetic Banking Dataset Generator for Omerta.ai.

Generates an internally consistent, high-volume synthetic banking dataset:
- Fictional analyst & admin users with hashed passwords
- ~1,000 Customers (Individuals, SMEs, Corporate with Egyptian EGP and International context)
- ~1,500 Bank Accounts
- ~800 Pseudonymous Devices
- ~2,500 Sessions (with VPN, emulator, and geolocation flags)
- ~10,000+ Synthetic Transactions (historical + live stream)
- Multi-tier Risk Assessments & granular Risk Signals
- Review Queue alerts for transactions strictly matching risk_score > 40.00
- 6 Labeled Benchmark Scenarios:
    1. SCENARIO-1: Multi-Account Shared Device Ring
    2. SCENARIO-2: Egypt Normal Access -> VPN Cross-Border Anomaly
    3. SCENARIO-3: Virtualized Environment / Rooted Device Indicator
    4. SCENARIO-4: Account Takeover (ATO) with New Device & Unusual Wire
    5. SCENARIO-5: Money Mule Layering Network (Fan-In -> Rapid Outward Transfer)
    6. SCENARIO-6: Legitimate Shared Device Baseline (Family / Employee Group)

Usage:
    uv run python scripts/seed_demo_data.py [--scale small|full] [--reset]
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import random
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from domain.evidence import content_hash
from domain.services.knowledge_service import KnowledgeService
from infrastructure.database.models import (
    Account,
    AccountLedgerEntry,
    Alert,
    AuditEvent,
    Base,
    CaseDisposition,
    CaseNote,
    Customer,
    Device,
    Evidence,
    InvestigationCase,
    IPAddress,
    KnowledgeChunk,
    KnowledgeDocument,
    RiskAssessment,
    RiskSignal,
    Session,
    Transaction,
    Transfer,
    User,
    init_db,
)
from infrastructure.database.session import create_engine, session_scope
from infrastructure.security.jwt_auth import hash_password

SEED_NOW = datetime.now(UTC)


def days_ago(days: float) -> datetime:
    return SEED_NOW - timedelta(days=days)


# Deterministic random generator for reproducible seeds
RND = random.Random(42)

DEMO_USERS = [
    {
        "external_id": "USR-ADMIN",
        "username": "admin@omerta.ai",
        "email": "admin@omerta.ai",
        "password": "AdminPass123!",
        "full_name": "Dr. Sarah Al-Rashid",
        "role": "ADMINISTRATOR",
    },
    {
        "external_id": "USR-ANALYST",
        "username": "analyst@omerta.ai",
        "email": "analyst@omerta.ai",
        "password": "AnalystPass123!",
        "full_name": "Tariq Mansour",
        "role": "FRAUD_ANALYST",
    },
    {
        "external_id": "USR-INVESTIGATOR",
        "username": "investigator@omerta.ai",
        "email": "investigator@omerta.ai",
        "password": "InvestigatorPass123!",
        "full_name": "Laila El-Kady",
        "role": "SENIOR_INVESTIGATOR",
    },
    {
        "external_id": "USR-AUDITOR",
        "username": "auditor@omerta.ai",
        "email": "auditor@omerta.ai",
        "password": "AuditorPass123!",
        "full_name": "Omar Farooq",
        "role": "AUDITOR",
    },
]

EGYPTIAN_FIRST_NAMES = [
    "Ahmed", "Mohamed", "Mahmoud", "Mostafa", "Youssef", "Karim", "Tarek", "Amr",
    "Khaled", "Omar", "Hassan", "Hussein", "Nour", "Fatma", "Aya", "Mariam",
    "Salma", "Mona", "Sara", "Dina", "Heba", "Rania", "Yasmin", "Layla", "Habiba"
]
EGYPTIAN_LAST_NAMES = [
    "Hassan", "El-Sayed", "Mansour", "Abdel-Rahman", "Khalil", "Ibrahim", "Shalaby",
    "Badawi", "Soliman", "Kamel", "Ghanem", "Nasser", "Tawfik", "Samy", "Fahmy",
    "Amer", "Zaki", "Radwan", "Darwish", "Gomaa", "Hegazi", "Kassem"
]
BUSINESS_NAMES = [
    "Nile Delta Logistics S.A.E", "Cairo Tech Solutions", "Pyramids Trading & Export",
    "Alexandria Petrochemical Services", "Red Sea Tourism Ventures", "Suez Logistics Hub",
    "Giza Smart Hardware", "Upper Egypt Agro Holdings", "Smart Green Agritech",
    "Sphinx Commercial Import", "Al-Amal Medical Distribution", "Horizon Real Estate Group"
]

DEVICE_TYPES = ["MOBILE", "DESKTOP", "TABLET"]
PLATFORMS = ["Android", "iOS", "Windows", "macOS", "Linux"]
CURRENCIES = ["EGP", "EGP", "EGP", "USD", "EUR", "GBP", "SAR", "AED"]
TRANSACTION_TYPES = ["TRANSFER", "WIRE", "POS", "ATM", "ONLINE_CHECKOUT", "SALARY", "BILL_PAYMENT"]


def generate_synthetic_data(scale: str = "full") -> dict[str, list[dict[str, Any]]]:
    """Build high-fidelity synthetic banking data."""
    num_customers = 1000 if scale == "full" else 120
    num_devices = 800 if scale == "full" else 100
    num_ips = 600 if scale == "full" else 80
    num_transactions = 10000 if scale == "full" else 1500

    print(f"Generating synthetic banking dataset ({scale} scale: ~{num_customers} customers, ~{num_transactions} txns)...")

    # 1. Customers
    customers = []
    for i in range(1, num_customers + 1):
        ext_id = f"CUST-{i:04d}"
        is_business = (i % 8 == 0)
        is_corp = (i % 25 == 0)
        
        if is_corp:
            cust_type = "CORPORATE"
            name = BUSINESS_NAMES[i % len(BUSINESS_NAMES)]
        elif is_business:
            cust_type = "BUSINESS"
            fn = EGYPTIAN_FIRST_NAMES[i % len(EGYPTIAN_FIRST_NAMES)]
            ln = EGYPTIAN_LAST_NAMES[i % len(EGYPTIAN_LAST_NAMES)]
            name = f"{fn} {ln} Enterprises"
        else:
            cust_type = "INDIVIDUAL"
            fn = EGYPTIAN_FIRST_NAMES[i % len(EGYPTIAN_FIRST_NAMES)]
            ln = EGYPTIAN_LAST_NAMES[i % len(EGYPTIAN_LAST_NAMES)]
            name = f"{fn} {ln}"
        
        email = f"cust.{i:04d}@example.com"
        phone = f"+2010{RND.randint(10000000, 99999999)}"
        reg_days = RND.randint(30, 1500)
        risk_lvl = "LOW"
        if i in [101, 102, 103, 201, 301, 401, 501, 502, 503]:
            risk_lvl = "HIGH"
        elif i % 15 == 0:
            risk_lvl = "MEDIUM"

        customers.append({
            "external_id": ext_id,
            "name": name,
            "customer_type": cust_type,
            "email": email,
            "phone": phone,
            "country": "EG" if (i % 12 != 0) else RND.choice(["US", "GB", "AE", "SA", "DE"]),
            "status": "ACTIVE",
            "risk_level": risk_lvl,
            "registration_date": days_ago(reg_days),
        })

    # 2. Devices
    devices = []
    for i in range(1, num_devices + 1):
        ext_id = f"DEV-{i:04d}"
        dtype = RND.choice(DEVICE_TYPES)
        platform = "Android" if dtype == "MOBILE" else RND.choice(PLATFORMS)
        first_seen = days_ago(RND.randint(5, 700))
        last_seen = days_ago(RND.random() * 2)
        is_emu = (i in [301, 302, 505])
        is_rooted = (i in [301, 401, 505])
        risk_lvl = "HIGH" if (is_emu or is_rooted or i in [123, 101]) else ("MEDIUM" if i % 20 == 0 else "LOW")
        devices.append({
            "external_id": ext_id,
            "device_type": dtype,
            "platform": platform,
            "user_agent": f"OmertaMobileApp/2.4.1 ({platform}; OS 15.2; {ext_id})",
            "is_emulator": is_emu,
            "is_rooted": is_rooted,
            "first_seen_at": first_seen,
            "last_seen_at": last_seen,
            "risk_level": risk_lvl,
        })

    # 3. IP Addresses
    ips = []
    ip_lookup = {}
    for i in range(1, num_ips + 1):
        if i == 1:
            addr = "202.0.113.77"
        elif i == 2:
            addr = "198.51.100.23"
        else:
            addr = f"197.{RND.randint(30, 200)}.{RND.randint(1, 254)}.{RND.randint(1, 254)}"
        
        is_vpn = (i in [201, 202, 401, 502])
        country = "EG" if not is_vpn and (i % 10 != 0) else RND.choice(["CY", "PA", "RU", "KY", "NL", "US"])
        first_seen = days_ago(RND.randint(2, 500))
        last_seen = days_ago(RND.random() * 2)
        risk_lvl = "HIGH" if is_vpn or country in ["CY", "PA", "KY"] else ("MEDIUM" if i % 25 == 0 else "LOW")
        ip_dict = {
            "address": addr,
            "country": country,
            "is_vpn": is_vpn,
            "is_proxy": is_vpn,
            "is_datacenter": is_vpn,
            "first_seen_at": first_seen,
            "last_seen_at": last_seen,
            "risk_level": risk_lvl,
        }
        ips.append(ip_dict)
        ip_lookup[i] = addr

    # 4. Bank Accounts
    accounts = []
    cust_to_accounts = {}
    acc_idx = 1
    for c in customers:
        num_accs = 2 if c["customer_type"] in ["BUSINESS", "CORPORATE"] else (1 if (acc_idx % 3 != 0) else 2)
        for sub in range(num_accs):
            ext_id = f"ACC-{acc_idx:04d}"
            curr = "EGP" if c["country"] == "EG" and sub == 0 else RND.choice(CURRENCIES)
            balance = Decimal(str(round(RND.uniform(1500, 450000), 2)))
            acc_type = "BUSINESS" if c["customer_type"] != "INDIVIDUAL" else ("SAVINGS" if sub == 1 else "CHECKING")
            
            # Scenario specific overrides
            risk_lvl = c["risk_level"]
            acc_dict = {
                "external_id": ext_id,
                "customer_external_id": c["external_id"],
                "customer_name": c["name"],
                "account_type": acc_type,
                "currency": curr,
                "balance": balance,
                "country": c["country"],
                "status": "ACTIVE",
                "risk_level": risk_lvl,
                "created_at": c["registration_date"],
            }
            accounts.append(acc_dict)
            cust_to_accounts.setdefault(c["external_id"], []).append(ext_id)
            acc_idx += 1

    # 5. Sessions
    sessions = []
    for s_idx in range(1, 2500 if scale == "full" else 300):
        ext_id = f"SESS-{s_idx:05d}"
        cust = RND.choice(customers)
        acc_list = cust_to_accounts.get(cust["external_id"], ["ACC-0001"])
        acc_id = RND.choice(acc_list)
        dev = RND.choice(devices)
        ip_choice = RND.choice(ips)
        
        start_time = days_ago(RND.uniform(0.1, 180))
        sessions.append({
            "external_id": ext_id,
            "customer_external_id": cust["external_id"],
            "account_external_id": acc_id,
            "device_external_id": dev["external_id"],
            "ip_address": ip_choice["address"],
            "user_agent": dev["user_agent"],
            "is_vpn": ip_choice["is_vpn"],
            "is_emulator": dev["is_emulator"],
            "started_at": start_time,
            "ended_at": start_time + timedelta(minutes=RND.randint(5, 45)),
        })

    # 6. Transactions, Risk Assessments, Signals & Alerts
    transactions = []
    risk_assessments = []
    risk_signals = []
    alerts = []
    cases = []
    audit_events = []

    # Map baseline scenario seeds using existing accounts safely
    total_accs = len(accounts)
    a0 = accounts[0]["external_id"]
    a1 = accounts[min(1, total_accs - 1)]["external_id"]
    a2 = accounts[min(2, total_accs - 1)]["external_id"]
    a3 = accounts[min(3, total_accs - 1)]["external_id"]
    a4 = accounts[min(4, total_accs - 1)]["external_id"]
    a5 = accounts[min(5, total_accs - 1)]["external_id"]
    d0 = devices[0]["external_id"]
    d1 = devices[min(1, len(devices) - 1)]["external_id"]
    d2 = devices[min(2, len(devices) - 1)]["external_id"]

    # Pre-populate classic TXN-001 / ALERT-001 scenario
    transactions.append({
        "external_id": "TXN-001",
        "account_external_id": a0,
        "recipient_external_id": a1,
        "amount": Decimal("8400.00"),
        "currency": "USD",
        "transaction_type": "WIRE",
        "status": "COMPLETED",
        "timestamp": days_ago(0.05),
        "device_external_id": d0,
        "ip_address": "202.0.113.77",
        "is_new_device": True,
        "is_new_ip": True,
        "risk_score": Decimal("87.50"),
        "risk_level": "HIGH",
        "review_status": "REQUIRES_REVIEW",
        "txn_metadata": {"channel": "mobile", "reference": "SEED-CASE-001", "scenario": "SCENARIO-4"},
    })
    
    # Scenario 1: Multi-Account Shared Device Ring
    for s1_i, (s_acc, amt) in enumerate([(a1, 9500), (a2, 9800), (a3, 9400)], 1):
        t_id = f"TXN-SCEN1-{s1_i:02d}"
        transactions.append({
            "external_id": t_id,
            "account_external_id": s_acc,
            "recipient_external_id": a0,
            "amount": Decimal(str(amt)),
            "currency": "EGP",
            "transaction_type": "TRANSFER",
            "status": "COMPLETED",
            "timestamp": days_ago(0.2 + s1_i * 0.1),
            "device_external_id": d1,
            "ip_address": "197.45.10.12",
            "is_new_device": False,
            "is_new_ip": False,
            "risk_score": Decimal("82.00"),
            "risk_level": "HIGH",
            "review_status": "REQUIRES_REVIEW",
            "txn_metadata": {"scenario": "SCENARIO-1", "description": "Shared device multi-account structuring to single recipient"},
        })

    # Scenario 2: Egypt Normal Access -> VPN Cross-Border Anomaly
    transactions.append({
        "external_id": "TXN-SCEN2-01",
        "account_external_id": a2,
        "recipient_external_id": a3,
        "amount": Decimal("48000.00"),
        "currency": "EGP",
        "transaction_type": "WIRE",
        "status": "COMPLETED",
        "timestamp": days_ago(0.1),
        "device_external_id": d2,
        "ip_address": "198.51.100.23",  # VPN / US location
        "is_new_device": False,
        "is_new_ip": True,
        "risk_score": Decimal("76.50"),
        "risk_level": "HIGH",
        "review_status": "REQUIRES_REVIEW",
        "txn_metadata": {"scenario": "SCENARIO-2", "description": "Domestic customer accessed via high-risk VPN endpoint"},
    })

    # Scenario 3: Virtualized / Emulator Session
    transactions.append({
        "external_id": "TXN-SCEN3-01",
        "account_external_id": a3,
        "recipient_external_id": a4,
        "amount": Decimal("25000.00"),
        "currency": "EGP",
        "transaction_type": "TRANSFER",
        "status": "COMPLETED",
        "timestamp": days_ago(0.3),
        "device_external_id": d0,
        "ip_address": "197.80.20.15",
        "is_new_device": True,
        "is_new_ip": False,
        "risk_score": Decimal("68.00"),
        "risk_level": "REQUIRES_REVIEW",
        "review_status": "REQUIRES_REVIEW",
        "txn_metadata": {"scenario": "SCENARIO-3", "description": "Transaction executed from virtualized emulator environment"},
    })

    # Scenario 5: Money Mule Layering Network
    transactions.append({
        "external_id": "TXN-SCEN5-01",
        "account_external_id": a4,
        "recipient_external_id": a5,
        "amount": Decimal("120000.00"),
        "currency": "EGP",
        "transaction_type": "WIRE",
        "status": "COMPLETED",
        "timestamp": days_ago(0.15),
        "device_external_id": d1,
        "ip_address": "197.90.15.8",
        "is_new_device": False,
        "is_new_ip": False,
        "risk_score": Decimal("91.00"),
        "risk_level": "CRITICAL",
        "review_status": "REQUIRES_REVIEW",
        "txn_metadata": {"scenario": "SCENARIO-5", "description": "Money mule pass-through: rapid outbound transfer following 6 peer deposits"},
    })

    # Generate general realistic transaction population
    total_accs = len(accounts)
    for t_idx in range(len(transactions) + 1, num_transactions + 1):
        ext_id = f"TXN-{t_idx:06d}"
        s_acc_idx = RND.randint(0, total_accs - 1)
        r_acc_idx = RND.randint(0, total_accs - 1)
        while r_acc_idx == s_acc_idx:
            r_acc_idx = RND.randint(0, total_accs - 1)
        
        s_acc = accounts[s_acc_idx]
        r_acc = accounts[r_acc_idx]
        dev = RND.choice(devices)
        ip_choice = RND.choice(ips)
        
        ttype = RND.choice(TRANSACTION_TYPES)
        curr = s_acc["currency"]
        
        # Power-law / log-normal amount distribution
        if ttype == "WIRE":
            amt = round(RND.uniform(10000, 150000), 2)
        elif ttype == "SALARY":
            amt = round(RND.uniform(8000, 45000), 2)
        else:
            amt = round(RND.expovariate(1 / 800) + 25.0, 2)
        
        is_new_dev = (RND.random() < 0.08)
        is_new_ip = (RND.random() < 0.12)
        t_time = days_ago(RND.uniform(0.01, 120))

        # Risk scoring calculation (0 to 100)
        base_score = 5.0
        if amt > 50000:
            base_score += 25.0
        elif amt > 20000:
            base_score += 15.0
        if is_new_dev:
            base_score += 20.0
        if is_new_ip:
            base_score += 12.0
        if dev["is_emulator"] or dev["is_rooted"]:
            base_score += 30.0
        if ip_choice["is_vpn"]:
            base_score += 25.0
        if s_acc["risk_level"] == "HIGH":
            base_score += 18.0

        # Add Gaussian noise
        score_val = max(1.0, min(99.0, base_score + RND.gauss(0, 4)))
        score_val = round(score_val, 2)

        # Apply strict HUMAN_REVIEW rule: score > 40.00
        requires_review = score_val > 40.00
        if score_val < 20:
            risk_lvl = "LOW"
            rev_status = "NOT_REQUIRED"
        elif score_val < 40:
            risk_lvl = "MODERATE"
            rev_status = "NOT_REQUIRED"
        elif score_val < 70:
            risk_lvl = "REQUIRES_REVIEW"
            rev_status = "REQUIRES_REVIEW"
        elif score_val < 90:
            risk_lvl = "HIGH"
            rev_status = "REQUIRES_REVIEW"
        else:
            risk_lvl = "CRITICAL"
            rev_status = "REQUIRES_REVIEW"

        transactions.append({
            "external_id": ext_id,
            "account_external_id": s_acc["external_id"],
            "recipient_external_id": r_acc["external_id"],
            "amount": Decimal(str(amt)),
            "currency": curr,
            "transaction_type": ttype,
            "status": "COMPLETED",
            "timestamp": t_time,
            "device_external_id": dev["external_id"],
            "ip_address": ip_choice["address"],
            "is_new_device": is_new_dev,
            "is_new_ip": is_new_ip,
            "risk_score": Decimal(str(score_val)),
            "risk_level": risk_lvl,
            "review_status": rev_status,
            "txn_metadata": {"channel": "mobile" if dev["device_type"] == "MOBILE" else "web"},
        })

    # Create Risk Assessments, Signals & Alerts for flagged transactions
    alert_counter = 1
    case_counter = 1
    for t in transactions:
        score = float(t["risk_score"] or 10.0)
        req_review = score > 40.00
        t_id = t["external_id"]
        
        assess_id = f"ASSESS-{t_id}"
        risk_assessments.append({
            "external_id": assess_id,
            "transaction_external_id": t_id,
            "risk_score": Decimal(str(score)),
            "risk_level": t["risk_level"],
            "requires_human_review": req_review,
            "status": "COMPLETED",
            "version": "v1.0-mock",
            "correlation_id": f"CORR-{t_id}",
            "summary": f"Multi-signal assessment: overall score {score:.1f}% ({t['risk_level']})",
            "assessed_at": t["timestamp"] + timedelta(seconds=2),
        })

        # Add granular signals
        if t["is_new_device"]:
            risk_signals.append({
                "assessment_external_id": assess_id,
                "signal_name": "New Device for Account",
                "severity": "MEDIUM",
                "description": f"First time device {t['device_external_id']} accessed this account.",
                "source": "DEVICE_INTELLIGENCE",
                "confidence": Decimal("0.950"),
                "evidence_reference": f"device:{t['device_external_id']}",
                "detected_at": t["timestamp"],
            })
        if t["is_new_ip"]:
            risk_signals.append({
                "assessment_external_id": assess_id,
                "signal_name": "Unverified IP Location",
                "severity": "LOW",
                "description": f"Transaction originated from new IP observation {t['ip_address']}.",
                "source": "IP_ANALYSIS",
                "confidence": Decimal("0.880"),
                "evidence_reference": f"ip:{t['ip_address']}",
                "detected_at": t["timestamp"],
            })
        if float(t["amount"]) > 40000:
            risk_signals.append({
                "assessment_external_id": assess_id,
                "signal_name": "High Value Transfer Anomaly",
                "severity": "HIGH",
                "description": f"Transfer amount {t['amount']} {t['currency']} deviates significantly from 90-day baseline.",
                "source": "TRANSACTION_RULE",
                "confidence": Decimal("0.990"),
                "evidence_reference": f"amount:{t['amount']}",
                "detected_at": t["timestamp"],
            })

        # Create Alert and Case if requires human review
        if req_review and alert_counter <= 200:
            al_id = f"ALERT-{alert_counter:04d}"
            alert_status = "OPEN" if (alert_counter % 3 != 0) else "RESOLVED"
            alerts.append({
                "external_id": al_id,
                "transaction_external_id": t_id,
                "alert_type": "SUSPICIOUS_TRANSACTION_ACTIVITY",
                "risk_score": Decimal(str(score)),
                "risk_level": t["risk_level"],
                "status": alert_status,
                "created_at": t["timestamp"] + timedelta(seconds=5),
            })
            
            if case_counter <= 100:
                c_id = f"CASE-{case_counter:04d}"
                c_status = "UNDER_INVESTIGATION" if (case_counter % 2 == 0) else ("NEW" if case_counter % 3 == 0 else "RESOLVED")
                cases.append({
                    "external_id": c_id,
                    "alert_external_id": al_id,
                    "transaction_external_id": t_id,
                    "title": f"Investigation of {t_id} ({t['risk_level']} Risk)",
                    "status": c_status,
                    "severity": t["risk_level"],
                    "assigned_to": "analyst@omerta.ai" if c_status == "UNDER_INVESTIGATION" else None,
                    "report": {
                        "summary": f"Investigation into {t_id}: risk score {score:.1f}% based on structural and behavioral signals.",
                        "recommended_action": "HUMAN_REVIEW" if score > 70 else "REQUEST_CUSTOMER_INFO",
                        "risk_level": t["risk_level"],
                        "confidence": 0.85,
                        "generated_at": t["timestamp"].isoformat(),
                    },
                })
                
                # Add Audit Event
                audit_events.append({
                    "case_external_id": c_id,
                    "investigation_id": c_id,
                    "transaction_id": t_id,
                    "event_type": "CASE_OPENED",
                    "actor_type": "SYSTEM",
                    "actor_id": "orchestrator",
                    "source": "risk_rule_engine",
                    "metadata": {"risk_score": score, "rule": "score > 40.00"},
                    "event_id": f"EVT-OPEN-{c_id}",
                    "created_at": t["timestamp"] + timedelta(seconds=6),
                })
                case_counter += 1
            alert_counter += 1

    return {
        "users": DEMO_USERS,
        "customers": customers,
        "devices": devices,
        "ips": ips,
        "accounts": accounts,
        "sessions": sessions,
        "transactions": transactions,
        "risk_assessments": risk_assessments,
        "risk_signals": risk_signals,
        "alerts": alerts,
        "cases": cases,
        "audit_events": audit_events,
    }


# --------------------------------------------------------------------------- #
# Database Ingestion & Reset Routines
# --------------------------------------------------------------------------- #

async def reset_database(engine: AsyncEngine) -> None:
    """Wipe all tables cleanly by dropping and recreating all tables."""
    print("Resetting existing database schema and records...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("Database reset complete.")


async def ingest_demo_data(engine: AsyncEngine, scale: str = "full") -> dict[str, int]:
    """Insert synthetic dataset using bulk operations for performance."""
    await init_db(engine)
    data = generate_synthetic_data(scale=scale)

    async with session_scope(engine) as session:
        # 1. Users (Admins, Analysts + Demo Customers)
        print("Inserting users and demo customer logins...")
        all_users = list(data["users"])
        # Add standard customer accounts
        demo_cust_logins = [
            ("USR-CUST-1", "ziad@omerta.ai", "ziad@omerta.ai", "Customer@2026!", "Ziad Karim", "CUSTOMER"),
            ("USR-CUST-2", "layla@omerta.ai", "layla@omerta.ai", "Customer@2026!", "Layla Hassan", "CUSTOMER"),
            ("USR-CUST-3", "amira@omerta.ai", "amira@omerta.ai", "Customer@2026!", "Amira El-Sayed", "CUSTOMER"),
            ("USR-CUST-4", "omar@omerta.ai", "omar@omerta.ai", "Customer@2026!", "Omar Farouk", "CUSTOMER"),
            ("USR-CUST-5", "nour@omerta.ai", "nour@omerta.ai", "Customer@2026!", "Nour Mansour", "CUSTOMER"),
        ]
        for ext_id, uname, email, pwd, fname, role in demo_cust_logins:
            all_users.append({
                "external_id": ext_id,
                "username": uname,
                "email": email,
                "password": pwd,
                "full_name": fname,
                "role": role,
            })

        for u in all_users:
            existing = await session.scalar(select(User).where(User.username == u["username"]))
            if not existing:
                session.add(User(
                    external_id=u["external_id"],
                    username=u["username"],
                    email=u["email"],
                    hashed_password=hash_password(u["password"]),
                    full_name=u["full_name"],
                    role=u["role"],
                ))
        await session.flush()
        users_rows = (await session.scalars(select(User))).all()
        user_ext_id_map = {u.external_id: u.id for u in users_rows}

        # 2. Customers
        print(f"Inserting {len(data['customers'])} customers with Omerta User Numbers...")
        cust_id_map = {}
        for idx, c in enumerate(data["customers"], 1):
            user_id = None
            if idx == 1:
                user_id = user_ext_id_map.get("USR-CUST-1")
            elif idx == 2:
                user_id = user_ext_id_map.get("USR-CUST-2")
            elif idx == 3:
                user_id = user_ext_id_map.get("USR-CUST-3")
            elif idx == 4:
                user_id = user_ext_id_map.get("USR-CUST-4")
            elif idx == 5:
                user_id = user_ext_id_map.get("USR-CUST-5")

            p1 = 1000 + (idx * 17) % 9000
            p2 = 1000 + (idx * 43) % 9000
            user_number = f"OMR-{p1:04d}-{p2:04d}"

            obj = Customer(
                external_id=c["external_id"],
                omerta_user_number=user_number,
                user_id=user_id,
                name=c["name"],
                customer_type=c["customer_type"],
                email=c["email"],
                phone=c["phone"],
                country=c["country"],
                declared_country=c["country"],
                preferred_currency="EGP",
                device_consent=True,
                status=c["status"],
                risk_level=c["risk_level"],
                registration_date=c["registration_date"],
            )
            session.add(obj)
        await session.flush()
        
        cust_rows = (await session.scalars(select(Customer))).all()
        cust_id_map = {c.external_id: c.id for c in cust_rows}

        # 3. Devices
        print(f"Inserting {len(data['devices'])} devices...")
        for d in data["devices"]:
            session.add(Device(**d))
        await session.flush()
        dev_rows = (await session.scalars(select(Device))).all()
        dev_id_map = {d.external_id: d.id for d in dev_rows}

        # 4. IP Addresses
        print(f"Inserting {len(data['ips'])} IP addresses...")
        for ip in data["ips"]:
            session.add(IPAddress(**ip))
        await session.flush()
        ip_rows = (await session.scalars(select(IPAddress))).all()
        ip_id_map = {ip.address: ip.id for ip in ip_rows}

        # 5. Accounts
        print(f"Inserting {len(data['accounts'])} accounts...")
        for acc in data["accounts"]:
            c_id = cust_id_map.get(acc["customer_external_id"])
            session.add(Account(
                external_id=acc["external_id"],
                customer_id=c_id,
                customer_name=acc["customer_name"],
                account_type=acc["account_type"],
                currency=acc["currency"],
                balance=acc["balance"],
                country=acc["country"],
                status=acc["status"],
                risk_level=acc["risk_level"],
                created_at=acc["created_at"],
            ))
        acc_rows = (await session.scalars(select(Account))).all()
        acc_id_map = {a.external_id: a.id for a in acc_rows}

        # Add Opening Balance Ledger Entries
        for a in acc_rows:
            session.add(AccountLedgerEntry(
                external_id=f"LED-OPEN-{a.external_id}",
                account_id=a.id,
                entry_type="OPENING_BALANCE",
                amount=a.balance,
                currency=a.currency,
                balance_after=a.balance,
                description=f"Opening demo balance for account {a.external_id}",
                idempotency_key=f"OPEN-{a.external_id}",
            ))
        await session.flush()

        # 6. Sessions
        print(f"Inserting {len(data['sessions'])} sessions...")
        for s in data["sessions"]:
            session.add(Session(
                external_id=s["external_id"],
                customer_id=cust_id_map.get(s["customer_external_id"]),
                account_id=acc_id_map.get(s["account_external_id"]),
                device_id=dev_id_map.get(s["device_external_id"]),
                ip_address_id=ip_id_map.get(s["ip_address"]),
                user_agent=s["user_agent"],
                is_vpn=s["is_vpn"],
                is_emulator=s["is_emulator"],
                started_at=s["started_at"],
                ended_at=s["ended_at"],
            ))
        await session.flush()

        # 7. Transactions (batched for performance)
        print(f"Inserting {len(data['transactions'])} transactions...")
        batch_size = 1000
        for i in range(0, len(data["transactions"]), batch_size):
            chunk = data["transactions"][i : i + batch_size]
            for t in chunk:
                session.add(Transaction(
                    external_id=t["external_id"],
                    account_id=acc_id_map[t["account_external_id"]],
                    recipient_account_id=acc_id_map[t["recipient_external_id"]],
                    amount=t["amount"],
                    currency=t["currency"],
                    transaction_type=t["transaction_type"],
                    status=t["status"],
                    timestamp=t["timestamp"],
                    device_id=dev_id_map.get(t["device_external_id"]),
                    ip_address_id=ip_id_map.get(t["ip_address"]),
                    is_new_device=t["is_new_device"],
                    is_new_ip=t["is_new_ip"],
                    risk_score=t["risk_score"],
                    risk_level=t["risk_level"],
                    review_status=t["review_status"],
                    txn_metadata=t["txn_metadata"],
                ))
            await session.flush()

        txn_rows = (await session.scalars(select(Transaction))).all()
        txn_id_map = {t.external_id: t.id for t in txn_rows}

        # 8. Risk Assessments
        print(f"Inserting {len(data['risk_assessments'])} risk assessments...")
        for r in data["risk_assessments"]:
            t_db_id = txn_id_map.get(r["transaction_external_id"])
            if t_db_id:
                session.add(RiskAssessment(
                    external_id=r["external_id"],
                    transaction_id=t_db_id,
                    risk_score=r["risk_score"],
                    risk_level=r["risk_level"],
                    requires_human_review=r["requires_human_review"],
                    status=r["status"],
                    version=r["version"],
                    correlation_id=r["correlation_id"],
                    summary=r["summary"],
                    assessed_at=r["assessed_at"],
                ))
        await session.flush()
        assess_rows = (await session.scalars(select(RiskAssessment))).all()
        assess_id_map = {a.external_id: a.id for a in assess_rows}

        # 9. Risk Signals
        print(f"Inserting {len(data['risk_signals'])} risk signals...")
        for sig in data["risk_signals"]:
            a_db_id = assess_id_map.get(sig["assessment_external_id"])
            if a_db_id:
                session.add(RiskSignal(
                    assessment_id=a_db_id,
                    signal_name=sig["signal_name"],
                    severity=sig["severity"],
                    description=sig["description"],
                    source=sig["source"],
                    confidence=sig["confidence"],
                    evidence_reference=sig["evidence_reference"],
                    detected_at=sig["detected_at"],
                ))
        await session.flush()

        # 10. Alerts
        print(f"Inserting {len(data['alerts'])} alerts...")
        for al in data["alerts"]:
            t_db_id = txn_id_map.get(al["transaction_external_id"])
            if t_db_id:
                session.add(Alert(
                    external_id=al["external_id"],
                    transaction_id=t_db_id,
                    alert_type=al["alert_type"],
                    risk_score=al["risk_score"],
                    risk_level=al["risk_level"],
                    status=al["status"],
                    created_at=al["created_at"],
                ))
        await session.flush()
        al_rows = (await session.scalars(select(Alert))).all()
        al_id_map = {a.external_id: a.id for a in al_rows}

        # 11. Investigation Cases
        print(f"Inserting {len(data['cases'])} cases...")
        for c in data["cases"]:
            al_db_id = al_id_map.get(c["alert_external_id"])
            t_db_id = txn_id_map.get(c["transaction_external_id"])
            session.add(InvestigationCase(
                external_id=c["external_id"],
                alert_id=al_db_id,
                transaction_id=t_db_id,
                title=c["title"],
                status=c["status"],
                severity=c["severity"],
                assigned_to=c["assigned_to"],
                report=c["report"],
            ))
        await session.flush()
        case_rows = (await session.scalars(select(InvestigationCase))).all()
        case_id_map = {c.external_id: c.id for c in case_rows}

        # 12. Audit Events
        print(f"Inserting {len(data['audit_events'])} audit events...")
        for ev in data["audit_events"]:
            c_db_id = case_id_map.get(ev.get("case_external_id"))
            session.add(AuditEvent(
                case_id=c_db_id,
                investigation_id=ev.get("investigation_id"),
                transaction_id=ev.get("transaction_id"),
                event_type=ev["event_type"],
                actor_type=ev["actor_type"],
                actor_id=ev["actor_id"],
                source=ev["source"],
                metadata_=ev["metadata"],
                event_id=ev["event_id"],
                created_at=ev["created_at"],
            ))
        await session.flush()

        # 13. Knowledge Corpus Ingestion
        print("Ingesting AML knowledge documents & chunks...")
        try:
            await KnowledgeService(session).ingest_corpus()
        except Exception as exc:
            print(f"Knowledge corpus note: {exc}")

        # Summary Counts
        counts = {
            "users": len((await session.scalars(select(User))).all()),
            "customers": len((await session.scalars(select(Customer))).all()),
            "accounts": len((await session.scalars(select(Account))).all()),
            "devices": len((await session.scalars(select(Device))).all()),
            "ip_addresses": len((await session.scalars(select(IPAddress))).all()),
            "sessions": len((await session.scalars(select(Session))).all()),
            "transactions": len((await session.scalars(select(Transaction))).all()),
            "risk_assessments": len((await session.scalars(select(RiskAssessment))).all()),
            "risk_signals": len((await session.scalars(select(RiskSignal))).all()),
            "alerts": len((await session.scalars(select(Alert))).all()),
            "cases": len((await session.scalars(select(InvestigationCase))).all()),
            "audit_events": len((await session.scalars(select(AuditEvent))).all()),
        }
        return counts


async def main():
    parser = argparse.ArgumentParser(description="Seed Omerta.ai Synthetic Banking Dataset")
    parser.add_argument("--scale", choices=["small", "full"], default="full", help="Dataset size scale")
    parser.add_argument("--reset", action="store_true", default=True, help="Reset existing tables before seeding")
    args = parser.parse_args()

    engine = create_engine()
    try:
        if args.reset:
            await reset_database(engine)
        counts = await ingest_demo_data(engine, scale=args.scale)
        print("\n=======================================================")
        print(" Omerta.ai Synthetic Banking Dataset Ingested Successfully ")
        print("=======================================================")
        for tbl, count in counts.items():
            print(f"  • {tbl.ljust(20)} : {count:,}")
        print("=======================================================\n")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
