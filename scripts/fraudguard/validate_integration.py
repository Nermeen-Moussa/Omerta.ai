"""Replay YOUR labelled CSV data through the integrated FraudGuard scorer.

    uv run python scripts/fraudguard/validate_integration.py --data-dir /path/to/csvs [--sample 5000]

The folder must hold the 7 CSVs (customers, devices, customer_devices, merchants,
transactions, account_events, ground_truth_labels). Prints how the 0-30 / 31-70 /
71-100 tiers line up with the ground-truth fraud labels. If the XGBoost model cannot
be loaded it says so and falls back to rules-only so you still get a result.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from feature_engineering import FEATURE_COLUMNS, build_features  # noqa: E402

from infrastructure.risk.fraudguard.rule_engine import score_row  # noqa: E402
from infrastructure.risk.fraudguard.scorer import FraudGuardScorer, FraudGuardUnavailable  # noqa: E402


def tier(s: float) -> str:
    return "LOW (0-30)" if s <= 30 else "MEDIUM (31-70)" if s <= 70 else "HIGH (71-100)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--sample", type=int, default=5000, help="rows to score (0 = all)")
    a = ap.parse_args()

    print("building features ...")
    df = build_features(a.data_dir)
    if a.sample and len(df) > a.sample:
        fraud = df[df.is_fraud == 1]
        keep = min(len(fraud), a.sample // 5)  # keep fraud visible in a small sample
        df = pd.concat([fraud.sample(keep, random_state=1),
                        df[df.is_fraud == 0].sample(a.sample - keep, random_state=1)])
    print(f"scoring {len(df):,} rows (fraud rate {df.is_fraud.mean():.1%})")

    source = "FRAUDGUARD (rules+XGBoost+IsolationForest)"
    try:
        out = FraudGuardScorer().score_many(df)
        df["final_score"] = out["final_score"]
    except FraudGuardUnavailable as exc:
        source = f"RULES ONLY - model unavailable: {exc}"
        df["final_score"] = [score_row(r)[0] for _, r in df[FEATURE_COLUMNS].fillna(0).iterrows()]
    print(f"scorer: {source}\n")

    df["tier"] = df.final_score.map(tier)
    t = df.groupby("tier").agg(rows=("is_fraud", "size"), fraud=("is_fraud", "sum"))
    t["fraud_rate"] = (t.fraud / t.rows).map("{:.1%}".format)
    print(t.to_string(), "\n")
    for cut, label in ((31, "MEDIUM or above (step-up/block)"), (71, "HIGH only (block)")):
        pred = df.final_score >= cut
        tp = int((pred & (df.is_fraud == 1)).sum())
        prec = tp / max(int(pred.sum()), 1)
        rec = tp / max(int((df.is_fraud == 1).sum()), 1)
        print(f"{label:<34} flagged={int(pred.sum()):>6}  precision={prec:.3f}  recall={rec:.3f}")
    if "fraud_type" in df:
        print("\nmean score by fraud type:")
        print(df.groupby(df.fraud_type.fillna("none")).final_score.mean().round(1).to_string())


if __name__ == "__main__":
    main()
