"""
FraudGuard AI — shared scoring logic used by predict.py (CLI) and api.py (HTTP).
"""
import json
import os

import joblib
import numpy as np
import pandas as pd

from feature_engineering import FEATURE_COLUMNS
from rule_engine import score_row

WEIGHTS = {"rule": 0.30, "ml": 0.45, "anomaly": 0.25}
DEFAULT_THRESHOLD = 60.0


def _scale(x, lo, hi):
    return float(np.clip((x - lo) / (hi - lo) * 100, 0, 100)) if hi > lo else float(np.clip(x, 0, 100))


def load_artifacts(models_dir):
    art = {
        "xgb": joblib.load(os.path.join(models_dir, "xgboost_model.joblib")),
        "iso": joblib.load(os.path.join(models_dir, "isolation_forest.joblib")),
        "scaler": joblib.load(os.path.join(models_dir, "feature_scaler.joblib")),
        "approx": False,
    }
    path = os.path.join(models_dir, "score_scaling.json")
    if os.path.exists(path):
        with open(path) as f:
            art["bounds"] = json.load(f)
    else:  # fallback: 0-100 scaling is only approximate
        art["bounds"] = {"ml": [0.0, 1.0], "anomaly": [0.40, 0.70]}
        art["approx"] = True
    return art


def score_frame(df, art, threshold=DEFAULT_THRESHOLD):
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    X = df[FEATURE_COLUMNS].fillna(0)
    Xs = art["scaler"].transform(X)
    proba = art["xgb"].predict_proba(X)[:, 1]
    anomaly_raw = -art["iso"].score_samples(Xs)
    iso_flag = art["iso"].predict(Xs) == -1

    out = []
    for i in range(len(df)):
        rule_score, reasons = score_row(df.iloc[i])
        ml_score = _scale(proba[i], *art["bounds"]["ml"])
        anomaly_score = _scale(anomaly_raw[i], *art["bounds"]["anomaly"])
        final = float(np.clip(WEIGHTS["rule"] * rule_score + WEIGHTS["ml"] * ml_score
                              + WEIGHTS["anomaly"] * anomaly_score, 0, 100))
        out.append({
            "verdict": "ANOMALY" if final >= threshold else "NORMAL",
            "is_anomaly": final >= threshold,
            "final_score": round(final, 1),
            "rule_score": int(rule_score),
            "ml_score": round(ml_score, 1),
            "fraud_probability": round(float(proba[i]), 4),
            "anomaly_score": round(anomaly_score, 1),
            "isolation_forest_flag": bool(iso_flag[i]),
            "reasons": [{"points": p, "reason": r} for p, r in sorted(reasons, reverse=True)],
        })
    return out
