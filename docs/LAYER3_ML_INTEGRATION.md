# Layer 3 - Real-Time ML Scoring (FraudGuard integration)

Implements the "Layer 3" design: classify fraud typology -> composite risk score ->
tiered action. Enabled with `RISK_ENGINE=layer3` (default `legacy` keeps old behaviour).

| Score | Tier   | Action                                                                 |
|-------|--------|------------------------------------------------------------------------|
| 0-30  | LOW    | ALLOW - transfer completes                                             |
| 31-70 | MEDIUM | STEP_UP - one-time code; pass = complete, wrong x3 = block + escalate  |
| 71-100| HIGH   | BLOCK_ESCALATE - no funds move; alert + investigation ticket (Layer 4) |

Typologies (heuristic, explainable): `SCAM`, `THIRD_PARTY_FRAUD`, `FIRST_PARTY_FRIENDLY_FRAUD`.
Impossible travel is a hard policy floor to HIGH.

## Where things are
- `infrastructure/risk/fraudguard/` - vendored FraudGuard (rules + XGBoost + Isolation Forest), `scorer.py` loads `models/fraudguard/*.joblib`
- `domain/services/layer3_engine.py` - features, typology, tiers, decision (pure logic)
- `domain/services/step_up_service.py` - OTP challenge (bound to recipient+amount, 5 min, 3 tries, single use; in-memory)
- `domain/services/transfer_service.py` - gate runs BEFORE the ledger update (`_run_layer3`, `_block_and_escalate`)
- `scripts/fraudguard/` - retraining scripts (need the 7 CSVs in `data/`)

## Honest limits
- FraudGuard was trained on a merchant/card-style synthetic dataset. Omerta is P2P, so
  `merchant_age_days` = recipient account age and `chargeback/refund_rate` = 0 (proxies).
- Reported metrics (evaluation_report.json) are on synthetic, generator-labelled data; not production accuracy.
- If XGBoost/artifacts fail to load, Layer 3 falls back to rules-only scoring (`source: RULES_ONLY`) - transfers never crash.
- Step-up codes are not yet sent by email/SMS; set `STEP_UP_DEV_ECHO=true` in dev to see the code.
