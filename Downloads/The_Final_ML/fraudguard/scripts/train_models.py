"""
FraudGuard AI — Phase 2 Pipeline
==================================
Rules + ML Risk Model

Steps:
  1. Load engineered features (from feature_engineering.py)
  2. Score every transaction with the Rule Engine        -> rule_score
  3. Train XGBoost (supervised)                            -> ml_score
  4. Train Isolation Forest (unsupervised anomaly)          -> anomaly_score
  5. Combine into a weighted Final Risk Score
  6. Evaluate all three components + the final score against ground truth
  7. Save models + risk_scores.csv (matches the `risk_scores` DB table)

Run:
    python train_models.py --data ../data --models ../models --reports ../reports
"""

import argparse
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    average_precision_score, roc_auc_score, confusion_matrix
)
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import joblib

from feature_engineering import build_features, FEATURE_COLUMNS
from rule_engine import score_dataframe as apply_rules


# Weights for combining the three scores into the Final Risk Score.
# (Design-doc default — meant to be recalibrated against real feedback data.)
WEIGHTS = {"rule": 0.30, "ml": 0.45, "anomaly": 0.25}


def to_0_100(x):
    x = np.asarray(x, dtype=float)
    lo, hi = np.percentile(x, 1), np.percentile(x, 99)
    if hi <= lo:
        return np.clip(x, 0, 100)
    scaled = (x - lo) / (hi - lo) * 100
    return np.clip(scaled, 0, 100)


def train_xgboost(X_train, y_train, X_test, y_test):
    pos = y_train.sum()
    neg = len(y_train) - pos
    scale_pos_weight = neg / max(pos, 1)

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    return model


def train_isolation_forest(X_all):
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_all)
    # contamination ~ known fraud rate in the synthetic data (~0.9%)
    iso = IsolationForest(
        n_estimators=300, contamination=0.01, random_state=42, n_jobs=-1
    )
    iso.fit(X_scaled)
    return iso, scaler


def evaluate(y_true, scores_0_100, name, threshold=60):
    y_pred = (scores_0_100 >= threshold).astype(int)
    y_score = scores_0_100 / 100.0

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    pr_auc = average_precision_score(y_true, y_score)
    roc_auc = roc_auc_score(y_true, y_score)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fpr = fp / (fp + tn) if (fp + tn) else 0
    fnr = fn / (fn + tp) if (fn + tp) else 0

    report = {
        "component": name,
        "threshold": threshold,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc_auc, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "confusion_matrix": {"TN": int(tn), "FP": int(fp), "FN": int(fn), "TP": int(tp)},
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="../data")
    parser.add_argument("--models", default="../models")
    parser.add_argument("--reports", default="../reports")
    args = parser.parse_args()

    print("Loading + engineering features...")
    feats = build_features(args.data)

    print("Scoring with Rule Engine...")
    feats = apply_rules(feats)

    X = feats[FEATURE_COLUMNS].fillna(0)
    y = feats["is_fraud"].values

    # Stratified train/test split (holdout for honest evaluation)
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, feats.index, test_size=0.25, stratify=y, random_state=42
    )

    print(f"Train size: {len(X_train):,} | Test size: {len(X_test):,} | "
          f"Fraud in test: {y_test.sum():,} ({y_test.mean()*100:.2f}%)")

    # ---------------- ML model ----------------
    print("\nTraining XGBoost classifier...")
    xgb_model = train_xgboost(X_train, y_train, X_test, y_test)
    ml_proba_all = xgb_model.predict_proba(X)[:, 1]
    feats["ml_score"] = to_0_100(ml_proba_all)

    # ---------------- Anomaly model ----------------
    print("Training Isolation Forest (unsupervised)...")
    iso_model, scaler = train_isolation_forest(X)
    anomaly_raw = -iso_model.score_samples(scaler.transform(X))  # higher = more anomalous
    feats["anomaly_score"] = to_0_100(anomaly_raw)

    # ---------------- Final Risk Score ----------------
    feats["final_score"] = (
        WEIGHTS["rule"] * feats["rule_score"]
        + WEIGHTS["ml"] * feats["ml_score"]
        + WEIGHTS["anomaly"] * feats["anomaly_score"]
    ).clip(0, 100)

    # ---------------- Evaluation (on held-out test rows only) ----------------
    test_mask = feats.index.isin(idx_test)
    reports = []
    for col, name in [("rule_score", "Rule Engine"), ("ml_score", "XGBoost (ML)"),
                       ("anomaly_score", "Isolation Forest"), ("final_score", "Final Risk Score")]:
        reports.append(evaluate(feats.loc[test_mask, "is_fraud"], feats.loc[test_mask, col], name))

    print("\n" + "=" * 90)
    print(f"{'Component':<20}{'Precision':>10}{'Recall':>10}{'F1':>8}{'PR-AUC':>9}{'ROC-AUC':>9}{'FPR':>8}{'FNR':>8}")
    print("-" * 90)
    for r in reports:
        print(f"{r['component']:<20}{r['precision']:>10.3f}{r['recall']:>10.3f}{r['f1']:>8.3f}"
              f"{r['pr_auc']:>9.3f}{r['roc_auc']:>9.3f}{r['false_positive_rate']:>8.3f}{r['false_negative_rate']:>8.3f}")
    print("=" * 90)

    # ---------------- Feature importance ----------------
    importance = dict(zip(FEATURE_COLUMNS, [round(float(v), 4) for v in xgb_model.feature_importances_]))
    importance = dict(sorted(importance.items(), key=lambda kv: kv[1], reverse=True))
    print("\nTop feature importances (XGBoost):")
    for k, v in list(importance.items())[:8]:
        print(f"  {k:<32} {v:.4f}")

    # ---------------- Save everything ----------------
    import os
    os.makedirs(args.models, exist_ok=True)
    os.makedirs(args.reports, exist_ok=True)

    joblib.dump(xgb_model, f"{args.models}/xgboost_model.joblib")
    joblib.dump(iso_model, f"{args.models}/isolation_forest.joblib")
    joblib.dump(scaler, f"{args.models}/feature_scaler.joblib")

    # Save the percentile bounds used by to_0_100() so predict.py can score new
    # transactions on exactly the same 0-100 scale.
    scaling = {
        "ml": [float(np.percentile(ml_proba_all, 1)), float(np.percentile(ml_proba_all, 99))],
        "anomaly": [float(np.percentile(anomaly_raw, 1)), float(np.percentile(anomaly_raw, 99))],
    }
    with open(f"{args.models}/score_scaling.json", "w") as f:
        json.dump(scaling, f, indent=2)

    risk_scores = feats[["transaction_id", "rule_score", "ml_score", "anomaly_score", "final_score"]].copy()
    risk_scores["graph_score"] = 0  # placeholder — computed in Phase 4 (Neo4j Graph Layer)
    risk_scores["behavior_score"] = feats["amount_zscore"].abs().clip(0, 100)  # simple proxy until Phase 3
    risk_scores.to_csv(f"{args.reports}/risk_scores.csv", index=False)

    evidence_sample = feats.loc[feats["final_score"] >= 80,
                                 ["transaction_id", "is_fraud", "final_score", "rule_reasons"]].head(10)
    evidence_sample.to_csv(f"{args.reports}/sample_high_risk_evidence.csv", index=False)

    with open(f"{args.reports}/evaluation_report.json", "w") as f:
        json.dump({"weights": WEIGHTS, "results": reports, "feature_importance": importance}, f, indent=2)

    print(f"\nSaved: risk_scores.csv, models (.joblib), evaluation_report.json, sample_high_risk_evidence.csv")


if __name__ == "__main__":
    main()
