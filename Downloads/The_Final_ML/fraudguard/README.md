# FraudGuard AI (risk model)

Rules + XGBoost + Isolation Forest. Scores a transaction 0–100 and labels it
**ANOMALY** (final score >= 60) or **NORMAL**, with the reasons.

```
scripts/   feature_engineering.py  rule_engine.py  train_models.py  scoring.py  predict.py  api.py
models/    xgboost_model.joblib  isolation_forest.joblib  feature_scaler.joblib  score_scaling.json
reports/   evaluation_report.json  sample_high_risk_evidence.csv  risk_scores.csv
samples/   example transactions (JSON)
data/      7 raw CSVs for retraining (not committed)
```

## Docker (run from this folder)

```bash
docker compose up --build api          # API on http://localhost:8100  (docs: /docs)

curl -X POST http://localhost:8100/predict \
     -H "Content-Type: application/json" \
     -d @samples/suspicious_transaction.json

docker compose run --rm predict        # CLI prediction on the sample file
docker compose run --rm train          # retrain (needs the 7 CSVs in data/)
```

## Without Docker

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd scripts
python predict.py --demo
python predict.py --input ../samples/sample_transactions.json
MODELS_DIR=../models uvicorn api:app --port 8100
```

## Input

The 19 engineered features in `feature_engineering.FEATURE_COLUMNS`
(`amount`, `amount_to_avg_ratio`, `is_new_device`, `is_vpn`, `txn_count_1hour`, ...).
They are built from a customer's history by `feature_engineering.py`.

## Response

```json
{"verdict": "ANOMALY", "is_anomaly": true, "final_score": 100.0, "rule_score": 100,
 "ml_score": 100.0, "fraud_probability": 0.9981, "anomaly_score": 100.0,
 "isolation_forest_flag": true, "reasons": [{"points": 30, "reason": "..."}]}
```
