"""ML risk engine (Phase 14): LightGBM provider behind the RiskProvider seam.

Training is a deterministic, reproducible offline step (see
``scripts/train_risk_model.py``): synthetic demo data (honestly labeled as
such) -> temporal-free stratified split -> LightGBM classifier -> metrics ->
model artifact persisted under ``models/``. ``MLRiskProvider`` loads the
artifact and serves predictions through the exact ``RiskProvider`` contract
(source = ``ML``, model_version = e.g. ``lgbm-risk-v1``) - the Risk MCP,
investigator, API, and evidence pipeline are unchanged.

The model produces a risk SIGNAL only; enforcement decisions remain human.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from domain import schemas

from infrastructure.risk.features import FEATURE_NAMES, FEATURE_VERSION, feature_row
from infrastructure.risk.mock_provider import risk_level_for_score

logger = logging.getLogger(__name__)

ML_SOURCE = "ML"
MODEL_VERSION = "lgbm-risk-v1"
MODEL_DIR = Path("models")
MODEL_FILE = MODEL_DIR / "risk_lgbm_v1.json"
METRICS_FILE = MODEL_DIR / "risk_lgbm_v1_metrics.json"

LGBM_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "max_depth": 6,
    "min_child_samples": 40,
    "subsample": 0.9,
    "subsample_freq": 1,
    "colsample_bytree": 0.9,
    "reg_lambda": 1.0,
    "random_state": 20260928,
    "n_jobs": 1,
    "verbose": -1,
}


def _ensure_dir() -> None:
    MODEL_DIR.mkdir(exist_ok=True)


def train_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_valid: np.ndarray,
    y_valid: np.ndarray,
) -> tuple[Any, dict[str, Any]]:
    """Train the LightGBM classifier; return (model, metrics dict)."""
    import lightgbm as lgb
    from sklearn.metrics import (
        average_precision_score,
        confusion_matrix,
        precision_recall_fscore_support,
        roc_auc_score,
    )

    model = lgb.LGBMClassifier(**LGBM_PARAMS)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_valid, y_valid)],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )
    proba = model.predict_proba(X_valid)[:, 1]
    preds = (proba >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_valid, preds, average="binary", zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(y_valid, preds).ravel()
    metrics = {
        "model_version": MODEL_VERSION,
        "feature_version": FEATURE_VERSION,
        "trained_at": datetime.now(UTC).isoformat(),
        "n_train": int(len(y_train)),
        "n_valid": int(len(y_valid)),
        "n_features": len(FEATURE_NAMES),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc_score(y_valid, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_valid, proba)), 4),
        "false_positive_rate": round(float(fp / max(fp + tn, 1)), 4),
        "false_negative_rate": round(float(fn / max(fn + tp, 1)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "best_iteration": int(model.best_iteration_ or model.n_estimators),
    }
    return model, metrics


def save_model(model: Any, metrics: dict[str, Any]) -> None:
    """Persist the booster + metrics (JSON artifact, deterministic content)."""
    _ensure_dir()
    model.booster_.save_model(str(MODEL_FILE))
    METRICS_FILE.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")


class MLRiskProvider:
    """RiskProvider implementation over the trained LightGBM artifact.

    Same contract as MockRiskProvider: deterministic for a fixed artifact,
    explicit provenance (source=ML), bounded score, feature-level provenance
    via model-native importance-based contributions.
    """

    source = ML_SOURCE
    model_version = MODEL_VERSION

    def __init__(self, model_path: Path | None = None) -> None:
        import lightgbm as lgb

        path = model_path or MODEL_FILE
        if not path.exists():
            raise FileNotFoundError(
                f"ML risk model artifact not found at {path}; run "
                "`uv run python scripts/train_risk_model.py` first."
            )
        self._booster = lgb.Booster(model_file=str(path))
        self._importance = dict(
            zip(
                FEATURE_NAMES,
                self._booster.feature_importance(importance_type="gain").tolist(),
                strict=True,
            )
        )
        total = sum(self._importance.values()) or 1.0
        self._importance = {name: value / total for name, value in self._importance.items()}
        logger.info("ml_risk_provider_loaded: model=%s features=%s", MODEL_VERSION, FEATURE_VERSION)

    async def score(self, features: schemas.RiskFeatures) -> schemas.RiskScoreOut:
        vector = [feature_row(features)]
        proba = float(self._booster.predict(vector)[0])
        score = round(min(max(proba, 0.0), 1.0), 4)

        # Contributions = global gain importance of the active features,
        # renormalized over this row's nonzero terms (honest approximation:
        # model-native importance, NOT SHAP).
        active = {
            name: self._importance.get(name, 0.0)
            for name, value in zip(FEATURE_NAMES, vector[0], strict=True)
            if value
        }
        active_total = sum(active.values()) or 1.0
        contributions = {name: round(value / active_total, 4) for name, value in active.items()}

        return schemas.RiskScoreOut(
            transaction_id=features.transaction_id,
            risk_score=score,
            risk_level=risk_level_for_score(score),
            source=self.source,
            model_version=self.model_version,
            contributions=contributions,
        )


def get_ml_provider() -> MLRiskProvider:
    """Factory used when RISK_PROVIDER=ml (artifact must exist)."""
    return MLRiskProvider()
