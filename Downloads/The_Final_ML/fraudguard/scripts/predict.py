"""
FraudGuard AI — Predict (CLI)
==============================
Says whether a transaction is an ANOMALY (likely fraud) or NORMAL.

Input = engineered features (the 19 columns in feature_engineering.FEATURE_COLUMNS).

Usage:
    python predict.py --demo
    python predict.py --input ../samples/sample_transactions.json
    python predict.py --input features.csv
    python predict.py --json '{"amount": 9500, ...}'
    cat tx.json | python predict.py --input -
"""
import argparse
import json
import sys

import pandas as pd

from scoring import DEFAULT_THRESHOLD, load_artifacts, score_frame

DEMO = [
    {   # looks normal
        "amount": 40.0, "amount_to_avg_ratio": 0.9, "amount_to_max_ratio": 0.3,
        "amount_zscore": -0.1, "is_new_device": 0, "is_new_country": 0,
        "txn_count_5min": 0, "txn_count_1hour": 0, "is_unusual_hour": 0,
        "device_customer_count": 1, "chargeback_rate": 0.01, "refund_rate": 0.02,
        "is_flagged": 0, "merchant_age_days": 400, "min_since_password_change": 100000,
        "min_since_beneficiary_added": 100000, "min_since_device_registered": 100000,
        "is_vpn": 0, "hist_count": 50,
    },
    {   # looks like account takeover
        "amount": 9500.0, "amount_to_avg_ratio": 35.0, "amount_to_max_ratio": 4.0,
        "amount_zscore": 12.0, "is_new_device": 1, "is_new_country": 1,
        "txn_count_5min": 3, "txn_count_1hour": 9, "is_unusual_hour": 1,
        "device_customer_count": 6, "chargeback_rate": 0.15, "refund_rate": 0.1,
        "is_flagged": 1, "merchant_age_days": 3, "min_since_password_change": 10,
        "min_since_beneficiary_added": 15, "min_since_device_registered": 12,
        "is_vpn": 1, "hist_count": 20,
    },
]


def load_input(path):
    if path != "-" and path.lower().endswith(".csv"):
        return pd.read_csv(path)
    data = json.load(sys.stdin if path == "-" else open(path))
    return pd.DataFrame(data if isinstance(data, list) else [data])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help=".json or .csv file with the 19 feature columns ('-' = stdin JSON)")
    ap.add_argument("--json", help="a JSON object (or list) passed directly on the command line")
    ap.add_argument("--demo", action="store_true", help="score two built-in example transactions")
    ap.add_argument("--models", default="../models")
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = ap.parse_args()

    if args.demo:
        df = pd.DataFrame(DEMO)
    elif args.json:
        d = json.loads(args.json)
        df = pd.DataFrame(d if isinstance(d, list) else [d])
    elif args.input:
        df = load_input(args.input)
    else:
        ap.error("give --demo, --json or --input")

    art = load_artifacts(args.models)
    try:
        results = score_frame(df, art, args.threshold)
    except ValueError as e:
        raise SystemExit(str(e))

    for i, r in enumerate(results):
        print(f"\nTransaction #{i}: {r['verdict']}  (final score {r['final_score']} / 100, threshold {args.threshold:g})")
        print(f"  rule={r['rule_score']}  ml={r['ml_score']} (p={r['fraud_probability']})  "
              f"anomaly={r['anomaly_score']}  isolation-forest-flag={r['isolation_forest_flag']}")
        why = "; ".join(f"+{x['points']} {x['reason']}" for x in r["reasons"]) or "no rules triggered"
        print(f"  why: {why}")
    if art["approx"]:
        print("\nNote: models/score_scaling.json not found -> 0-100 scaling is approximate.")


if __name__ == "__main__":
    main()
