"""Offline scenario runner for Layer 3 (ML scoring) and Layer 4 (AML graph patterns).

No database, no servers needed:
    uv run python scripts/demo_layer3_layer4.py

Layer 3 uses the real FraudGuard models when they load (source=FRAUDGUARD) and
falls back to rules-only otherwise (source=RULES_ONLY) - check the 'source' column.
"""

from datetime import UTC, datetime, timedelta

from domain.services import layer3_engine as l3
from domain.services import layer4_aml as l4

C = l3.TransferRiskContext
HIST = dict(hist_count=40, hist_avg=300.0, hist_max=900.0, hist_std=150.0)

L3_SCENARIOS = [
    ("1  Routine payment, known device, known recipient", C(amount=250, **HIST), "LOW / ALLOW"),
    ("2  Bigger than usual, known recipient", C(amount=1500, **HIST), "LOW-MEDIUM"),
    ("3  Scam-like: 1st transfer to a new beneficiary, 10x usual",
     C(amount=3000, is_new_beneficiary=True, recipient_account_age_days=20, **HIST), "MEDIUM / STEP_UP"),
    ("4  Account takeover: new device + VPN + new country + big",
     C(amount=9500, is_new_device=True, is_vpn=True, is_new_country=True,
       min_since_device_registered=8, is_new_beneficiary=True, **HIST), "HIGH / BLOCK"),
    ("5  Impossible travel, small amount", C(amount=100, impossible_travel=True, **HIST), "HIGH / BLOCK"),
    ("6  Burst: 6 transfers in 5 minutes", C(amount=400, txn_count_5min=6, txn_count_1hour=9, **HIST), "MEDIUM+"),
    ("7  Night-time + new beneficiary + flagged recipient",
     C(amount=3000, is_unusual_hour=True, is_new_beneficiary=True, recipient_flagged=True,
       recipient_account_age_days=3, **HIST), "MEDIUM-HIGH"),
    ("8  Familiar session but 3 prior alerts (friendly fraud)",
     C(amount=700, previous_alert_count=3, **HIST), "any / FIRST_PARTY"),
]

NOW = datetime.now(UTC)


def _e(i, src, dst, amt, h, cur="EGP"):
    return l4.Edge(f"T{i}", src, dst, amt, cur, NOW - timedelta(hours=h))


L4_SCENARIOS = [
    ("A  Normal activity", [_e(1, 1, 2, 300, 5), _e(2, 1, 3, 800, 30)], 1, "no finding"),
    ("B  Smurfing: 3 x ~47k EGP in 30h (threshold 50k)",
     [_e(1, 1, 2, 47000, 30), _e(2, 1, 2, 48000, 12), _e(3, 1, 2, 46500, 1)], 1, "STRUCTURING"),
    ("C  Fan-out: 6 recipients x 12k", [_e(i, 1, 10 + i, 12000, i + 1) for i in range(6)], 1, "FAN_OUT"),
    ("D  Fan-in mule: 6 senders -> 1", [_e(i, 20 + i, 1, 11000, i + 1) for i in range(6)], 1, "FAN_IN"),
    ("E  Pass-through: in 30k, out 28k within 3h", [_e(1, 5, 1, 30000, 3), _e(2, 1, 6, 28000, 2)], 1, "PASS_THROUGH"),
    ("F  Round trip A->B->C->A", [_e(1, 1, 2, 1000, 5), _e(2, 2, 3, 990, 4), _e(3, 3, 1, 980, 3)], 1, "CYCLE"),
]


def main() -> None:
    print("\n=== LAYER 3: ML scoring -> typology -> tier -> action ===")
    print(f"{'scenario':<62}{'score':>6}  {'tier':<7}{'action':<15}{'typology':<28}{'source':<11}expect")
    for name, ctx, expect in L3_SCENARIOS:
        d = l3.assess(ctx)
        print(f"{name:<62}{d.score:>6.1f}  {d.tier:<7}{d.action:<15}{d.typology:<28}{d.source:<11}{expect}")
    print("\n=== LAYER 4: graph / AML patterns ===")
    for name, edges, focus, expect in L4_SCENARIOS:
        found = l4.analyze(edges, [focus], NOW)
        got = ", ".join(f"{f.pattern}({f.score:.0f})" for f in found) or "no finding"
        print(f"{name:<55} -> {got:<30} expect: {expect}")
    print()


if __name__ == "__main__":
    main()
