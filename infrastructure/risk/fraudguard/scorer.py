"""Load the FraudGuard artifacts and score feature dicts (0-100 composite).

Weights (rule 0.30 / ML 0.45 / anomaly 0.25) and the scaling bounds are the
ones the model was evaluated with (see models/fraudguard/evaluation_report.json).
Loading is lazy and failure-tolerant: callers get ``FraudGuardUnavailable`` and
decide the fallback, so a missing/incompatible artifact never takes transfers down.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np

from infrastructure.risk.fraudguard import FEATURE_COLUMNS, NEUTRAL_DEFAULTS
from infrastructure.risk.fraudguard.rule_engine import score_row

logger = logging.getLogger(__name__)

WEIGHTS = {"rule": 0.30, "ml": 0.45, "anomaly": 0.25}
DEFAULT_MODELS_DIR = Path(__file__).resolve().parents[3] / "models" / "fraudguard"


class FraudGuardUnavailable(RuntimeError):
    """Artifacts missing or not loadable in this environment."""


def _scale(x: float, lo: float, hi: float) -> float:
    return float(np.clip((x - lo) / (hi - lo) * 100, 0, 100)) if hi > lo else float(np.clip(x, 0, 100))


class FraudGuardScorer:
    def __init__(self, models_dir: Path | str | None = None) -> None:
        self._dir = Path(models_dir) if models_dir else DEFAULT_MODELS_DIR
        self._art: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def _load(self) -> dict[str, Any]:
        if self._art is not None:
            return self._art
        with self._lock:
            if self._art is not None:
                return self._art
            try:
                import joblib

                art = {
                    "xgb": joblib.load(self._dir / "xgboost_model.joblib"),
                    "iso": joblib.load(self._dir / "isolation_forest.joblib"),
                    "scaler": joblib.load(self._dir / "feature_scaler.joblib"),
                    "bounds": json.loads((self._dir / "score_scaling.json").read_text("utf-8")),
                }
            except Exception as exc:  # missing file, xgboost not installed, pickle mismatch...
                raise FraudGuardUnavailable(f"{type(exc).__name__}: {exc}") from exc
            self._art = art
            logger.info("fraudguard_loaded: dir=%s", self._dir)
            return art

    def score(self, features: dict[str, float]) -> dict[str, Any]:
        """Score one transaction. Missing features take neutral defaults."""
        import pandas as pd

        art = self._load()
        row = {**NEUTRAL_DEFAULTS, **features}
        df = pd.DataFrame([row])[FEATURE_COLUMNS].fillna(0)
        try:
            xs = art["scaler"].transform(df)
            proba = float(art["xgb"].predict_proba(df)[:, 1][0])
            anomaly_raw = float(-art["iso"].score_samples(xs)[0])
            iso_flag = bool(art["iso"].predict(xs)[0] == -1)
        except Exception as exc:
            raise FraudGuardUnavailable(f"inference failed: {type(exc).__name__}: {exc}") from exc

        rule_score, reasons = score_row(df.iloc[0])
        ml_score = _scale(proba, *art["bounds"]["ml"])
        anomaly_score = _scale(anomaly_raw, *art["bounds"]["anomaly"])
        final = float(np.clip(
            WEIGHTS["rule"] * rule_score + WEIGHTS["ml"] * ml_score + WEIGHTS["anomaly"] * anomaly_score,
            0, 100,
        ))
        return {
            "final_score": round(final, 1),
            "rule_score": int(rule_score),
            "ml_score": round(ml_score, 1),
            "fraud_probability": round(proba, 4),
            "anomaly_score": round(anomaly_score, 1),
            "isolation_forest_flag": iso_flag,
            "reasons": [{"points": p, "reason": r} for p, r in sorted(reasons, reverse=True)],
        }


    def score_many(self, df: "Any") -> "Any":
        """Vectorised scoring of a DataFrame holding the 19 feature columns.
        Returns a DataFrame with final_score / rule_score / ml_score / anomaly_score."""
        import pandas as pd

        art = self._load()
        X = df[FEATURE_COLUMNS].fillna(0)
        xs = art["scaler"].transform(X)
        proba = art["xgb"].predict_proba(X)[:, 1]
        anomaly_raw = -art["iso"].score_samples(xs)
        rule = np.array([score_row(r)[0] for _, r in X.iterrows()], dtype=float)
        lo_m, hi_m = art["bounds"]["ml"]
        lo_a, hi_a = art["bounds"]["anomaly"]
        ml = np.clip((proba - lo_m) / (hi_m - lo_m) * 100, 0, 100)
        an = np.clip((anomaly_raw - lo_a) / (hi_a - lo_a) * 100, 0, 100)
        final = np.clip(WEIGHTS["rule"] * rule + WEIGHTS["ml"] * ml + WEIGHTS["anomaly"] * an, 0, 100)
        return pd.DataFrame({"final_score": final.round(1), "rule_score": rule,
                             "ml_score": ml.round(1), "anomaly_score": an.round(1)}, index=df.index)


_scorer: FraudGuardScorer | None = None


def get_scorer() -> FraudGuardScorer:
    global _scorer
    if _scorer is None:
        from infrastructure.config import get_settings

        d = getattr(get_settings(), "fraudguard_models_dir", None)
        _scorer = FraudGuardScorer(d)
    return _scorer
