"""Transaction Management Application Service.

Provides comprehensive transaction query, filtering, CSV export, and deep detail views:
- Server-side search & filtering (date range, amount range, currency, type, risk level, review status)
- Sorting & pagination
- Transaction detail page with 6 complete sections:
    A. Transaction Overview
    B. Risk Assessment (Score 0-100%, Review trigger badge)
    C. Risk Signals list
    D. Transaction Timeline
    E. Related Entities (Customer, Accounts, Device, Session, IP)
    F. Investigation Report (Structured AI/Mock report)
"""

from datetime import datetime
from decimal import Decimal
import io
import csv
from typing import Any

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import (
    Account,
    Alert,
    Customer,
    Device,
    InvestigationCase,
    IPAddress,
    RiskAssessment,
    RiskSignal,
    Session,
    Transaction,
)


class BankingTransactionService:
    """Service layer for banking transactions and detail reconstructions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_transactions(
        self,
        *,
        search: str | None = None,
        currency: str | None = None,
        transaction_type: str | None = None,
        risk_level: str | None = None,
        review_status: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        sort_by: str = "timestamp",
        sort_desc: bool = True,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        """Server-side filtered, searched, and paginated transaction list."""
        query = select(Transaction).options(
            selectinload(Transaction.account),
            selectinload(Transaction.recipient_account),
            selectinload(Transaction.device),
            selectinload(Transaction.ip_address),
        )

        conditions = []
        if search:
            search_clean = f"%{search.strip()}%"
            conditions.append(
                or_(
                    Transaction.external_id.ilike(search_clean),
                    Transaction.account.has(Account.external_id.ilike(search_clean)),
                    Transaction.account.has(Account.customer_name.ilike(search_clean)),
                    Transaction.recipient_account.has(Account.external_id.ilike(search_clean)),
                )
            )

        if currency:
            conditions.append(Transaction.currency == currency.upper())
        if transaction_type:
            conditions.append(Transaction.transaction_type == transaction_type.upper())
        if risk_level:
            conditions.append(Transaction.risk_level == risk_level.upper())
        if review_status:
            conditions.append(Transaction.review_status == review_status.upper())
        if min_amount is not None:
            conditions.append(Transaction.amount >= Decimal(str(min_amount)))
        if max_amount is not None:
            conditions.append(Transaction.amount <= Decimal(str(max_amount)))
        if start_date:
            conditions.append(Transaction.timestamp >= start_date)
        if end_date:
            conditions.append(Transaction.timestamp <= end_date)

        if conditions:
            query = query.where(and_(*conditions))

        # Count total
        count_q = select(func.count(Transaction.id))
        if conditions:
            count_q = count_q.where(and_(*conditions))
        total = await self.session.scalar(count_q) or 0

        # Sorting
        sort_column = getattr(Transaction, sort_by, Transaction.timestamp)
        query = query.order_by(desc(sort_column) if sort_desc else sort_column)

        # Pagination
        offset = (max(1, page) - 1) * page_size
        query = query.offset(offset).limit(page_size)

        rows = (await self.session.scalars(query)).all()

        items = []
        for t in rows:
            items.append({
                "id": t.id,
                "external_id": t.external_id,
                "account_id": t.account_id,
                "source_account": t.account.external_id if t.account else "N/A",
                "customer_name": t.account.customer_name if t.account else "N/A",
                "recipient_account": t.recipient_account.external_id if t.recipient_account else "N/A",
                "amount": float(t.amount),
                "currency": t.currency,
                "transaction_type": t.transaction_type,
                "status": t.status,
                "timestamp": t.timestamp.isoformat(),
                "device": t.device.external_id if t.device else "N/A",
                "ip_country": t.ip_address.country if t.ip_address else "EG",
                "ip_address": t.ip_address.address if t.ip_address else None,
                "is_new_device": t.is_new_device,
                "is_new_ip": t.is_new_ip,
                "risk_score": float(t.risk_score) if t.risk_score is not None else 0.0,
                "risk_level": t.risk_level,
                "review_status": t.review_status,
            })

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        }

    async def get_transaction_detail(self, identifier: str) -> dict[str, Any] | None:
        """Load deep 6-section transaction detail view."""
        query = select(Transaction).options(
            selectinload(Transaction.account).selectinload(Account.customer),
            selectinload(Transaction.recipient_account),
            selectinload(Transaction.device),
            selectinload(Transaction.ip_address),
            selectinload(Transaction.risk_assessments).selectinload(RiskAssessment.signals),
            selectinload(Transaction.alerts).selectinload(Alert.cases),
        )

        if identifier.isdigit():
            query = query.where(or_(Transaction.id == int(identifier), Transaction.external_id == identifier))
        else:
            query = query.where(Transaction.external_id == identifier)

        txn = await self.session.scalar(query)
        if not txn:
            return None

        # 1. Overview
        customer = txn.account.customer if txn.account else None
        overview = {
            "id": txn.id,
            "external_id": txn.external_id,
            "amount": float(txn.amount),
            "currency": txn.currency,
            "transaction_type": txn.transaction_type,
            "status": txn.status,
            "timestamp": txn.timestamp.isoformat(),
            "source_account": {
                "id": txn.account.id if txn.account else None,
                "external_id": txn.account.external_id if txn.account else "N/A",
                "customer_name": txn.account.customer_name if txn.account else "N/A",
                "account_type": txn.account.account_type if txn.account else "N/A",
                "balance": float(txn.account.balance) if txn.account else 0.0,
            },
            "recipient_account": {
                "id": txn.recipient_account.id if txn.recipient_account else None,
                "external_id": txn.recipient_account.external_id if txn.recipient_account else "N/A",
                "customer_name": txn.recipient_account.customer_name if txn.recipient_account else "N/A",
                "account_type": txn.recipient_account.account_type if txn.recipient_account else "N/A",
            },
            "customer": {
                "id": customer.id if customer else None,
                "external_id": customer.external_id if customer else "N/A",
                "name": customer.name if customer else (txn.account.customer_name if txn.account else "N/A"),
                "customer_type": customer.customer_type if customer else "INDIVIDUAL",
                "country": customer.country if customer else "EG",
                "risk_level": customer.risk_level if customer else "LOW",
            } if (customer or txn.account) else None,
            "device": {
                "id": txn.device.id if txn.device else None,
                "external_id": txn.device.external_id if txn.device else "N/A",
                "device_type": txn.device.device_type if txn.device else "N/A",
                "platform": txn.device.platform if txn.device else "N/A",
                "is_emulator": txn.device.is_emulator if txn.device else False,
                "is_rooted": txn.device.is_rooted if txn.device else False,
            } if txn.device else None,
            "ip_address": {
                "id": txn.ip_address.id if txn.ip_address else None,
                "address": txn.ip_address.address if txn.ip_address else "N/A",
                "country": txn.ip_address.country if txn.ip_address else "EG",
                "is_vpn": txn.ip_address.is_vpn if txn.ip_address else False,
            } if txn.ip_address else None,
            "is_new_device": txn.is_new_device,
            "is_new_ip": txn.is_new_ip,
            "txn_metadata": txn.txn_metadata or {},
        }

        # 2. Risk Assessment & Signals
        latest_assessment = txn.risk_assessments[-1] if txn.risk_assessments else None
        assessment_data = None
        signals_data = []
        if latest_assessment:
            assessment_data = {
                "id": latest_assessment.id,
                "external_id": latest_assessment.external_id,
                "risk_score": float(latest_assessment.risk_score),
                "risk_level": latest_assessment.risk_level,
                "requires_human_review": latest_assessment.requires_human_review,
                "status": latest_assessment.status,
                "version": latest_assessment.version,
                "correlation_id": latest_assessment.correlation_id,
                "summary": latest_assessment.summary,
                "assessed_at": latest_assessment.assessed_at.isoformat(),
            }
            signals_data = [
                {
                    "id": sig.id,
                    "signal_name": sig.signal_name,
                    "severity": sig.severity,
                    "description": sig.description,
                    "source": sig.source,
                    "confidence": float(sig.confidence),
                    "evidence_reference": sig.evidence_reference,
                    "detected_at": sig.detected_at.isoformat(),
                }
                for sig in latest_assessment.signals
            ]
        else:
            score = float(txn.risk_score) if txn.risk_score is not None else 10.0
            assessment_data = {
                "external_id": f"ASSESS-{txn.external_id}",
                "risk_score": score,
                "risk_level": txn.risk_level,
                "requires_human_review": score > 40.0,
                "status": "COMPLETED",
                "version": "v1.0-mock",
                "correlation_id": f"CORR-{txn.external_id}",
                "summary": f"Assessment for {txn.external_id}: risk score {score:.1f}% ({txn.risk_level})",
                "assessed_at": txn.timestamp.isoformat(),
            }

        # 3. Transaction Timeline
        timeline = [
            {"event": "TRANSACTION_INITIATED", "timestamp": txn.timestamp.isoformat(), "description": "Transaction received and validated."},
            {"event": "RISK_ASSESSMENT_COMPLETED", "timestamp": (txn.timestamp).isoformat(), "description": f"Score computed: {assessment_data['risk_score']:.1f}% ({assessment_data['risk_level']})."},
        ]
        if assessment_data.get("requires_human_review"):
            timeline.append({
                "event": "HUMAN_REVIEW_TRIGGERED",
                "timestamp": txn.timestamp.isoformat(),
                "description": f"Risk score ({assessment_data['risk_score']}%) exceeds 40% threshold. Sent to review queue.",
            })

        # 4. Related Cases & Alerts
        related_cases = []
        for al in txn.alerts:
            for c in al.cases:
                related_cases.append({
                    "id": c.id,
                    "external_id": c.external_id,
                    "title": c.title,
                    "status": c.status,
                    "severity": c.severity,
                    "assigned_to": c.assigned_to,
                })

        # 5. Mock Investigation Report
        investigation_report = {
            "title": f"Investigation Dossier: {txn.external_id}",
            "executive_summary": (
                f"Autonomous assessment flagged transaction {txn.external_id} with an estimated "
                f"risk score of {assessment_data['risk_score']:.1f}% ({assessment_data['risk_level']}). "
                f"Key factors include {'new device' if txn.is_new_device else 'standard device'}, "
                f"{'unverified IP' if txn.is_new_ip else 'known IP'}, and amount {float(txn.amount):,.2f} {txn.currency}."
            ),
            "risk_factors": [
                s["signal_name"] for s in signals_data
            ] or ["Standard Activity Verification"],
            "recommended_action": "HUMAN_REVIEW" if assessment_data["requires_human_review"] else "ROUTINE_MONITORING",
            "confidence": 0.88,
            "version": "agent-v1.0-preview",
            "provenance": {
                "evaluator": "Omerta Multi-Tier Risk Engine",
                "review_rule": "risk_score > 40.00",
                "timestamp": txn.timestamp.isoformat(),
            },
        }

        return {
            "overview": overview,
            "assessment": assessment_data,
            "signals": signals_data,
            "timeline": timeline,
            "related_cases": related_cases,
            "report": investigation_report,
        }

    async def export_transactions_csv(
        self,
        *,
        search: str | None = None,
        currency: str | None = None,
        risk_level: str | None = None,
        review_status: str | None = None,
        limit: int = 1000,
    ) -> str:
        """Export filtered transactions to CSV string."""
        data = await self.list_transactions(
            search=search,
            currency=currency,
            risk_level=risk_level,
            review_status=review_status,
            page=1,
            page_size=limit,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Transaction ID", "Timestamp", "Source Account", "Customer", "Recipient Account",
            "Amount", "Currency", "Type", "Status", "Risk Score", "Risk Level", "Review Status",
            "Device", "IP Country"
        ])

        for t in data["items"]:
            writer.writerow([
                t["external_id"],
                t["timestamp"],
                t["source_account"],
                t["customer_name"],
                t["recipient_account"],
                t["amount"],
                t["currency"],
                t["transaction_type"],
                t["status"],
                t["risk_score"],
                t["risk_level"],
                t["review_status"],
                t["device"],
                t["ip_country"],
            ])

        return output.getvalue()
