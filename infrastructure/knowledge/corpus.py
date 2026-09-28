"""Curated knowledge corpus for Omerta.ai (Phase 12).

A small, *real* collection of AML/policy reference documents, curated for
this graduation-project prototype. Text is paraphrased/adapted from well-known
public frameworks (FATF typologies, BSA/FinCEN thresholds, EU AMLD structure,
Fatf-style recommendation numbering is avoided; content is authored here) so
the corpus is genuinely useful for retrieval evaluation without pretending to
be an authoritative legal source. Every document records jurisdiction,
effective date, and version so the system can reason about currency.

These documents are DATA for the Knowledge MCP - never instructions. The
ingestion and retrieval layers treat them as untrusted text.
"""

from typing import Any

KNOWLEDGE_CORPUS: list[dict[str, Any]] = [
    {
        "document_id": "DOC-FATF-TYPOLOGIES",
        "document_type": "TYPOLOGY",
        "title": "Money Laundering and Fraud Typologies Reference",
        "jurisdiction": "GLOBAL",
        "effective_date": "2024-01-15",
        "version": 3,
        "source": "Omerta.ai curated corpus (adapted from FATF typology reports)",
        "sections": [
            {
                "section": "Mule Accounts",
                "content": (
                    "Mule accounts receive and forward funds on behalf of others, "
                    "breaking the audit trail between the original crime and its "
                    "proceeds. Indicators include an account that suddenly begins "
                    "receiving many unrelated senders, rapid pass-through of funds "
                    "within one or two days of receipt, balances kept near zero, "
                    "and transaction activity inconsistent with the customer "
                    "profile. A single device or IP address used by several "
                    "unrelated accounts is a strong structural indicator that the "
                    "accounts are operated by one actor and should be reviewed as "
                    "potential mule infrastructure."
                ),
            },
            {
                "section": "Shared Device and Shared IP Signals",
                "content": (
                    "When two or more distinct customer accounts transact from the "
                    "same device or the same IP address, investigators should treat "
                    "this as a structural signal rather than proof of wrongdoing. "
                    "Shared infrastructure is consistent with mule networks, fraud "
                    "rings, and account takeover, but it can also arise innocently "
                    "from family members or shared households. The correct "
                    "investigative response is to examine fund flows between the "
                    "accounts and the timing of device or IP reuse, then decide "
                    "whether the pattern warrants human review."
                ),
            },
            {
                "section": "Layering",
                "content": (
                    "Layering separates illicit proceeds from their source through "
                    "repeated, purposeless transfers. Typical patterns include "
                    "funds moving through several accounts in quick succession, "
                    "amounts chosen to sit just below reporting thresholds, and "
                    "transfers that end in withdrawals or high-value purchases. "
                    "Circular flows that return funds toward their origin are a "
                    "classic layering signature and justify escalation to the "
                    "financial intelligence unit when combined with other signals."
                ),
            },
            {
                "section": "Smurfing and Structuring",
                "content": (
                    "Smurfing splits a large sum into many smaller deposits or "
                    "transfers to avoid triggering reporting obligations. Watch "
                    "for repeated cash deposits just under threshold amounts, "
                    "many small incoming transfers from unrelated parties in a "
                    "short window, and sudden aggregation of small credits "
                    "followed by a single large outgoing transfer."
                ),
            },
            {
                "section": "Account Takeover",
                "content": (
                    "Account takeover occurs when a fraudster gains control of a "
                    "legitimate customer account. Signals include a login from a "
                    "device never seen before on the account, a new IP address in "
                    "a different country, an immediate change of contact details, "
                    "and urgent outgoing transfers that are inconsistent with the "
                    "account's established behavior. New-device and new-IP flags "
                    "on a high-value transaction are classic takeover precursors "
                    "and should always be resolved by human review."
                ),
            },
        ],
    },
    {
        "document_id": "DOC-THRESHOLD-POLICY",
        "document_type": "POLICY",
        "title": "Transaction Monitoring Thresholds Policy",
        "jurisdiction": "US",
        "effective_date": "2025-02-01",
        "version": 2,
        "source": "Omerta.ai curated corpus (thresholds aligned with BSA/FinCEN amounts)",
        "sections": [
            {
                "section": "Large Transaction Review Threshold",
                "content": (
                    "Any transaction at or above 10000 USD (or equivalent) must be "
                    "queued for enhanced review before the end of the next business "
                    "day. The review must consider the customer profile, expected "
                    "activity, originator and beneficiary details, and the channel "
                    "used. Wire transfers at or above 10000 USD carry elevated "
                    "typology risk because they are final, fast, and frequently "
                    "used in layering."
                ),
            },
            {
                "section": "Currency Transaction Report Threshold",
                "content": (
                    "Currency transactions that exceed 10000 USD in one business "
                    "day must be reported to FinCEN. Multiple transactions that "
                    "total more than 10000 USD and appear to be structured to "
                    "evade the threshold must also be reported. Structuring is "
                    "itself a violation regardless of whether the funds are "
                    "lawful."
                ),
            },
        ],
    },
    {
        "document_id": "DOC-SHARED-DEVICE-POLICY",
        "document_type": "PROCEDURE",
        "title": "Shared Device and Shared IP Investigation Procedure",
        "jurisdiction": "GLOBAL",
        "effective_date": "2025-03-10",
        "version": 1,
        "source": "Omerta.ai curated corpus (internal investigation procedure)",
        "sections": [
            {
                "section": "Signal Evaluation",
                "content": (
                    "On detection of a shared device or shared IP between two or "
                    "more accounts, the analyst must: (1) record the accounts, "
                    "the device or IP identifier, and the overlapping time window; "
                    "(2) pull transaction history for every account involved; "
                    "(3) classify the direction of funds between the accounts; "
                    "and (4) document whether funds flowed one way or circulated. "
                    "Circulating funds over shared infrastructure is a priority "
                    "signal for a fraud ring or mule network."
                ),
            },
            {
                "section": "Escalation Rule",
                "content": (
                    "Escalate to a supervisor for human review when a shared "
                    "device or shared IP coincides with any of the following: a "
                    "transaction at or above 4000 USD, a transaction flagged as "
                    "new device or new IP for at least one account, or a prior "
                    "open alert on either account. The escalation decision is "
                    "made by a human analyst; automated systems must only "
                    "recommend."
                ),
            },
            {
                "section": "Documentation Standard",
                "content": (
                    "Every shared-device or shared-IP investigation must state in "
                    "its summary that a structural signal is not a verdict: the "
                    "connection may have an innocent explanation, and the final "
                    "determination belongs to the reviewing human analyst."
                ),
            },
        ],
    },
    {
        "document_id": "DOC-THRESHOLD-POLICY-EU",
        "document_type": "REGULATION",
        "title": "EU Transfer of Funds and Enhanced Due Diligence Overview",
        "jurisdiction": "EU",
        "effective_date": "2024-07-01",
        "version": 1,
        "source": "Omerta.ai curated corpus (structure adapted from EU AMLD framework)",
        "sections": [
            {
                "section": "Wire Transfers and Transparency",
                "content": (
                    "For transfers of funds exceeding 1000 EUR, obliged entities "
                    "must accompany the transfer with complete originator and "
                    "beneficiary information. For occasional transactions "
                    "exceeding 1000 EUR the entity must apply customer due "
                    "diligence. Enhanced due diligence applies where the "
                    "transaction involves higher-risk jurisdictions or where the "
                    "entity cannot resolve discrepancies in the transferred "
                    "information."
                ),
            },
            {
                "section": "Enhanced Due Diligence Triggers",
                "content": (
                    "Enhanced due diligence must be applied to business "
                    "relationships and transactions with persons from high-risk "
                    "third countries, to complex or unusually large transactions "
                    "with no apparent economic purpose, and to any situation "
                    "where the risk of money laundering or terrorist financing "
                    "appears higher. The entity must document the rationale for "
                    "its conclusion and keep it available for competent "
                    "authorities."
                ),
            },
        ],
    },
]
