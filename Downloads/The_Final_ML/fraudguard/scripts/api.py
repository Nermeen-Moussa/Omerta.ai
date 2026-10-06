"""
FraudGuard AI — HTTP API
=========================
POST /predict   one transaction's features  -> ANOMALY / NORMAL + explanation
POST /predict/batch   list of transactions
GET  /health

Run:  uvicorn api:app --host 0.0.0.0 --port 8000
Docs: http://localhost:8000/docs
"""
import os
from typing import List

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from scoring import DEFAULT_THRESHOLD, load_artifacts, score_frame

MODELS_DIR = os.environ.get("MODELS_DIR", "/app/models")
THRESHOLD = float(os.environ.get("THRESHOLD", DEFAULT_THRESHOLD))

app = FastAPI(title="FraudGuard AI", version="1.0")
ART = load_artifacts(MODELS_DIR)


class Transaction(BaseModel):
    amount: float
    amount_to_avg_ratio: float = 1.0
    amount_to_max_ratio: float = 1.0
    amount_zscore: float = 0.0
    is_new_device: int = Field(0, ge=0, le=1)
    is_new_country: int = Field(0, ge=0, le=1)
    txn_count_5min: int = 0
    txn_count_1hour: int = 0
    is_unusual_hour: int = Field(0, ge=0, le=1)
    device_customer_count: int = 1
    chargeback_rate: float = 0.0
    refund_rate: float = 0.0
    is_flagged: int = Field(0, ge=0, le=1)
    merchant_age_days: float = 999
    min_since_password_change: float = 100000
    min_since_beneficiary_added: float = 100000
    min_since_device_registered: float = 100000
    is_vpn: int = Field(0, ge=0, le=1)
    hist_count: int = 0


def _score(txns: List[Transaction]):
    df = pd.DataFrame([t.model_dump() for t in txns])
    try:
        return score_frame(df, ART, THRESHOLD)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/health")
def health():
    return {"status": "ok", "threshold": THRESHOLD, "approximate_scaling": ART["approx"]}


@app.post("/predict")
def predict(txn: Transaction):
    return _score([txn])[0]


@app.post("/predict/batch")
def predict_batch(txns: List[Transaction]):
    return _score(txns)
