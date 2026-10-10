"""Layer 4 - Graph analytics & AML engine.

Flow (from the design notes):  confirmed transaction -> ingest into relationship
graph -> pattern analysis ("smurfing": structured sub-threshold transactions) ->
finding? yes: alert + investigation ticket, no: nothing further.

This module is PURE (no DB / Neo4j imports): it takes a list of confirmed
account-to-account edges and returns findings. PostgreSQL stays the source of
truth for the edges; Neo4j is a derived projection used for investigation views.

Patterns
  STRUCTURING    >=3 transfers from one account, each in the band [50%, 100%) of the
                 reporting threshold, whose total reaches the threshold (window 72h)
  FAN_OUT        one account -> >=5 distinct recipients, total >= threshold
  FAN_IN         >=5 distinct senders -> one account (collector / mule), total >= threshold
  PASS_THROUGH   an account forwards >=80% of what it just received within 6h (layering)
  CYCLE          funds return to the origin through 2-3 hops (A->B->C->A)

Thresholds are DEMO values, not legal advice - set the real regulatory figure.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

DEFAULT_THRESHOLDS: dict[str, float] = {"EGP": 50_000.0, "USD": 1_000.0, "EUR": 1_000.0}
FALLBACK_THRESHOLD = 50_000.0


@dataclass(frozen=True)
class Edge:
    txn_id: str
    src: int  # sender account id
    dst: int  # recipient account id
    amount: float
    currency: str
    ts: datetime


@dataclass
class AmlFinding:
    pattern: str
    score: float
    severity: str  # MEDIUM | HIGH | CRITICAL
    subject_account: int
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"pattern": self.pattern, "score": self.score, "severity": self.severity,
                "subject_account": self.subject_account, "summary": self.summary,
                "evidence": self.evidence}


def _sev(score: float) -> str:
    return "CRITICAL" if score >= 85 else "HIGH" if score >= 70 else "MEDIUM"


def threshold_for(currency: str, thresholds: dict[str, float] | None = None) -> float:
    return (thresholds or DEFAULT_THRESHOLDS).get(currency.upper(), FALLBACK_THRESHOLD)


def _in_window(edges: list[Edge], now: datetime, hours: float) -> list[Edge]:
    lo = now - timedelta(hours=hours)
    return [e for e in edges if lo <= e.ts <= now]


def detect_structuring(edges, focus, now, window_h=72, thresholds=None):
    out = []
    by_cur: dict[str, list[Edge]] = defaultdict(list)
    for e in _in_window(edges, now, window_h):
        if e.src == focus:
            by_cur[e.currency.upper()].append(e)
    for cur, es in by_cur.items():
        t = threshold_for(cur, thresholds)
        band = [e for e in es if 0.5 * t <= e.amount < t]
        total = sum(e.amount for e in band)
        if len(band) >= 3 and total >= t:
            score = min(95.0, 62 + 6 * (len(band) - 3) + 10 * min(total / t - 1, 2))
            out.append(AmlFinding(
                "STRUCTURING", round(score, 1), _sev(score), focus,
                f"{len(band)} sub-threshold transfers ({cur}) totalling {total:,.2f} within {window_h}h "
                f"(reporting threshold {t:,.0f}).",
                {"currency": cur, "count": len(band), "total": round(total, 2), "threshold": t,
                 "txn_ids": [e.txn_id for e in band], "recipients": sorted({e.dst for e in band})}))
    return out


def detect_fan_out(edges, focus, now, window_h=72, thresholds=None, min_counterparties=5):
    out = []
    by_cur: dict[str, list[Edge]] = defaultdict(list)
    for e in _in_window(edges, now, window_h):
        if e.src == focus:
            by_cur[e.currency.upper()].append(e)
    for cur, es in by_cur.items():
        t = threshold_for(cur, thresholds)
        dsts = {e.dst for e in es}
        total = sum(e.amount for e in es)
        if len(dsts) >= min_counterparties and total >= t and all(e.amount < t for e in es):
            score = min(92.0, 66 + 4 * (len(dsts) - min_counterparties))
            out.append(AmlFinding(
                "FAN_OUT", round(score, 1), _sev(score), focus,
                f"Funds dispersed to {len(dsts)} different accounts ({cur} {total:,.2f}) within {window_h}h.",
                {"currency": cur, "recipients": sorted(dsts), "total": round(total, 2)}))
    return out


def detect_fan_in(edges, focus, now, window_h=72, thresholds=None, min_counterparties=5):
    out = []
    by_cur: dict[str, list[Edge]] = defaultdict(list)
    for e in _in_window(edges, now, window_h):
        if e.dst == focus:
            by_cur[e.currency.upper()].append(e)
    for cur, es in by_cur.items():
        t = threshold_for(cur, thresholds)
        srcs = {e.src for e in es}
        total = sum(e.amount for e in es)
        if len(srcs) >= min_counterparties and total >= t:
            score = min(92.0, 66 + 4 * (len(srcs) - min_counterparties))
            out.append(AmlFinding(
                "FAN_IN", round(score, 1), _sev(score), focus,
                f"Account collected funds from {len(srcs)} different senders ({cur} {total:,.2f}) within {window_h}h.",
                {"currency": cur, "senders": sorted(srcs), "total": round(total, 2)}))
    return out


def detect_pass_through(edges, focus, now, window_h=6, thresholds=None, ratio=0.8):
    out = []
    es = _in_window(edges, now, window_h)
    for cur in {e.currency.upper() for e in es}:
        t = threshold_for(cur, thresholds)
        inbound = sum(e.amount for e in es if e.dst == focus and e.currency.upper() == cur)
        outbound = sum(e.amount for e in es if e.src == focus and e.currency.upper() == cur)
        if inbound >= 0.3 * t and outbound >= ratio * inbound:
            out.append(AmlFinding(
                "PASS_THROUGH", 72.0, "HIGH", focus,
                f"Account forwarded {outbound / inbound:.0%} of {cur} {inbound:,.2f} received within {window_h}h.",
                {"currency": cur, "inbound": round(inbound, 2), "outbound": round(outbound, 2)}))
    return out


def detect_cycle(edges, focus, now, window_h=72, max_hops=3):
    """Simple cycle search: focus -> ... -> focus within max_hops (2 or 3)."""
    es = _in_window(edges, now, window_h)
    adj: dict[int, set[int]] = defaultdict(set)
    for e in es:
        adj[e.src].add(e.dst)
    cycles = []
    for a in adj.get(focus, ()):
        if focus in adj.get(a, ()) and a != focus:
            cycles.append([focus, a, focus])
        if max_hops >= 3:
            for b in adj.get(a, ()):
                if b not in (focus, a) and focus in adj.get(b, ()):
                    cycles.append([focus, a, b, focus])
    if not cycles:
        return []
    return [AmlFinding(
        "CYCLE", 80.0, "HIGH", focus,
        f"Funds circulate back to the origin account ({len(cycles)} loop(s) within {window_h}h).",
        {"loops": cycles[:5]})]


def analyze(edges: list[Edge], focus_accounts: list[int], now: datetime,
            window_h: float = 72, thresholds: dict[str, float] | None = None) -> list[AmlFinding]:
    """Run every detector for every focus account; strongest finding first."""
    findings: list[AmlFinding] = []
    for acc in dict.fromkeys(focus_accounts):
        findings += detect_structuring(edges, acc, now, window_h, thresholds)
        findings += detect_fan_out(edges, acc, now, window_h, thresholds)
        findings += detect_fan_in(edges, acc, now, window_h, thresholds)
        findings += detect_pass_through(edges, acc, now, 6, thresholds)
        findings += detect_cycle(edges, acc, now, window_h)
    return sorted(findings, key=lambda f: f.score, reverse=True)
