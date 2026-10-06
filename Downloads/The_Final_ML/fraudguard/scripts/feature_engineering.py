"""
FraudGuard AI — Feature Engineering
====================================
Builds a leakage-safe feature table from the raw synthetic CSVs.

Leakage safety: every "customer behavior" statistic (avg amount, usual
country, usual devices, velocity...) is computed using an EXPANDING window
over each customer's transactions in chronological order, using only
transactions that happened STRICTLY BEFORE the current one (.shift(1)).
This mirrors how the Behavior Agent would work in production: it only
knows the past when it scores a new transaction.
"""

import pandas as pd
import numpy as np


def load_raw(data_dir):
    customers = pd.read_csv(f"{data_dir}/customers.csv")
    devices = pd.read_csv(f"{data_dir}/devices.csv")
    customer_devices = pd.read_csv(f"{data_dir}/customer_devices.csv")
    merchants = pd.read_csv(f"{data_dir}/merchants.csv")
    transactions = pd.read_csv(f"{data_dir}/transactions.csv", parse_dates=["txn_timestamp"])
    events = pd.read_csv(f"{data_dir}/account_events.csv", parse_dates=["event_timestamp"])
    labels = pd.read_csv(f"{data_dir}/ground_truth_labels.csv")
    return customers, devices, customer_devices, merchants, transactions, events, labels


def build_features(data_dir):
    customers, devices, customer_devices, merchants, txns, events, labels = load_raw(data_dir)

    txns = txns.sort_values(["customer_id", "txn_timestamp"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # 1. Expanding (past-only) behavioral stats per customer
    # ------------------------------------------------------------------
    g = txns.groupby("customer_id")["amount"]
    txns["hist_count"] = g.cumcount()                                   # # prior txns
    txns["hist_avg_amount"] = g.apply(lambda s: s.shift(1).expanding().mean()).reset_index(level=0, drop=True)
    txns["hist_max_amount"] = g.apply(lambda s: s.shift(1).expanding().max()).reset_index(level=0, drop=True)
    txns["hist_std_amount"] = g.apply(lambda s: s.shift(1).expanding().std()).reset_index(level=0, drop=True)

    global_avg = txns["amount"].mean()
    global_max = txns["amount"].max()
    txns["hist_avg_amount"] = txns["hist_avg_amount"].fillna(global_avg)
    txns["hist_max_amount"] = txns["hist_max_amount"].fillna(global_max)
    txns["hist_std_amount"] = txns["hist_std_amount"].fillna(txns["amount"].std())

    txns["amount_to_avg_ratio"] = txns["amount"] / txns["hist_avg_amount"].replace(0, np.nan)
    txns["amount_to_max_ratio"] = txns["amount"] / txns["hist_max_amount"].replace(0, np.nan)
    txns["amount_to_avg_ratio"] = txns["amount_to_avg_ratio"].fillna(1.0)
    txns["amount_to_max_ratio"] = txns["amount_to_max_ratio"].fillna(1.0)
    txns["amount_zscore"] = (txns["amount"] - txns["hist_avg_amount"]) / txns["hist_std_amount"].replace(0, np.nan)
    txns["amount_zscore"] = txns["amount_zscore"].fillna(0.0).clip(-20, 20)

    # ------------------------------------------------------------------
    # 2. New device / new country (relative to prior history only)
    # ------------------------------------------------------------------
    def flag_new_value(df, col, new_col):
        seen = {}
        flags = np.zeros(len(df), dtype=bool)
        for i, (cust, val) in enumerate(zip(df["customer_id"].values, df[col].values)):
            s = seen.setdefault(cust, set())
            flags[i] = val not in s
            s.add(val)
        df[new_col] = flags
        return df

    txns = flag_new_value(txns, "device_id", "is_new_device")
    txns = flag_new_value(txns, "country", "is_new_country")

    # ------------------------------------------------------------------
    # 3. Velocity features (trailing windows, past-only)
    # ------------------------------------------------------------------
    def velocity_counts(df):
        out_5min, out_1hour = [], []
        for cust, sub in df.groupby("customer_id"):
            ts = sub["txn_timestamp"].values.astype("datetime64[s]")
            c5, c1h = [], []
            for i in range(len(ts)):
                t0 = ts[i]
                window5 = np.sum((ts[:i] > t0 - np.timedelta64(5, "m")) & (ts[:i] <= t0))
                window1h = np.sum((ts[:i] > t0 - np.timedelta64(60, "m")) & (ts[:i] <= t0))
                c5.append(window5)
                c1h.append(window1h)
            out_5min.extend(c5)
            out_1hour.extend(c1h)
        df["txn_count_5min"] = out_5min
        df["txn_count_1hour"] = out_1hour
        return df

    txns = velocity_counts(txns)

    # ------------------------------------------------------------------
    # 4. Time-of-day anomaly (based on customer's past usual hours)
    # ------------------------------------------------------------------
    txns["hour"] = txns["txn_timestamp"].dt.hour
    hist_hours = {}
    is_unusual_hour = np.zeros(len(txns), dtype=bool)
    for i, (cust, hour) in enumerate(zip(txns["customer_id"].values, txns["hour"].values)):
        hrs = hist_hours.setdefault(cust, [])
        if len(hrs) >= 5:
            lo, hi = np.percentile(hrs, [5, 95])
            is_unusual_hour[i] = not (lo - 1 <= hour <= hi + 1)
        hrs.append(hour)
    txns["is_unusual_hour"] = is_unusual_hour

    # ------------------------------------------------------------------
    # 5. Device sharing (graph-lite signal): how many distinct customers
    #    use this device overall (computed from customer_devices.csv)
    # ------------------------------------------------------------------
    device_sharing = customer_devices.groupby("device_id")["customer_id"].nunique().rename("device_customer_count")
    txns = txns.merge(device_sharing, on="device_id", how="left")
    txns["device_customer_count"] = txns["device_customer_count"].fillna(1)

    # ------------------------------------------------------------------
    # 6. Merchant risk features
    # ------------------------------------------------------------------
    merchants = merchants.copy()
    merchants["merchant_created_at"] = pd.to_datetime(merchants["created_at"], utc=True)
    txns = txns.merge(
        merchants[["merchant_id", "chargeback_rate", "refund_rate", "is_flagged", "merchant_created_at"]],
        on="merchant_id", how="left"
    )
    txns["merchant_age_days"] = (txns["txn_timestamp"] - txns["merchant_created_at"]).dt.total_seconds() / 86400
    txns["merchant_age_days"] = txns["merchant_age_days"].clip(lower=0).fillna(999)
    txns["is_flagged"] = txns["is_flagged"].fillna(False).astype(int)

    # ------------------------------------------------------------------
    # 7. Account-takeover chain features (time since sensitive events)
    # ------------------------------------------------------------------
    def time_since_event(txns, events, event_type, out_col, cap_minutes=100000):
        ev = events[events["event_type"] == event_type][["customer_id", "event_timestamp"]].sort_values("event_timestamp")
        result = np.full(len(txns), cap_minutes, dtype=float)
        ev_by_cust = {cust: sub["event_timestamp"].values.astype("datetime64[s]")
                      for cust, sub in ev.groupby("customer_id")}
        for i, (cust, ts) in enumerate(zip(txns["customer_id"].values, txns["txn_timestamp"].values.astype("datetime64[s]"))):
            times = ev_by_cust.get(cust)
            if times is None:
                continue
            past = times[times <= ts]
            if len(past) > 0:
                delta_min = (ts - past[-1]) / np.timedelta64(1, "m")
                result[i] = min(delta_min, cap_minutes)
        txns[out_col] = result
        return txns

    txns = time_since_event(txns, events, "PASSWORD_CHANGE", "min_since_password_change")
    txns = time_since_event(txns, events, "BENEFICIARY_ADDED", "min_since_beneficiary_added")
    txns = time_since_event(txns, events, "DEVICE_REGISTERED", "min_since_device_registered")

    # ------------------------------------------------------------------
    # 8. Misc
    # ------------------------------------------------------------------
    txns["is_vpn"] = txns["is_vpn"].astype(int)

    # ------------------------------------------------------------------
    # 9. Attach ground truth (kept separate from feature matrix at train time)
    # ------------------------------------------------------------------
    features = txns.merge(labels, on="transaction_id", how="left")
    features["is_fraud"] = features["is_fraud"].fillna(False).astype(int)

    return features


FEATURE_COLUMNS = [
    "amount", "amount_to_avg_ratio", "amount_to_max_ratio", "amount_zscore",
    "is_new_device", "is_new_country", "txn_count_5min", "txn_count_1hour",
    "is_unusual_hour", "device_customer_count", "chargeback_rate", "refund_rate",
    "is_flagged", "merchant_age_days", "min_since_password_change",
    "min_since_beneficiary_added", "min_since_device_registered", "is_vpn",
    "hist_count",
]


if __name__ == "__main__":
    import sys
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "../data"
    feats = build_features(data_dir)
    out_path = f"{data_dir}/features.csv"
    feats.to_csv(out_path, index=False)
    print(f"Wrote {len(feats):,} rows with {len(FEATURE_COLUMNS)} features -> {out_path}")
