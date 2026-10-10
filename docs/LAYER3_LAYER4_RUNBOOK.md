# Layer 3 + Layer 4 runbook (local: VS Code + WSL + Docker)

Terminals: **A** = backend (uvicorn), **B** = frontend (vite), **C** = a NEW terminal for git, scripts, tests.
Always run commands from `/mnt/d/Omerta.ai` (repo root) unless stated.

## 0. Put the code on its own branch (Terminal C)
    git status                       # commit or stash anything you want to keep first
    git checkout main && git pull origin main
    git checkout -b feature/layer3-layer4
    git apply --3way /path/to/layer3-layer4.patch      # patch is in the folder you downloaded it to
    git status                       # new + changed files should appear

## 1. Install dependencies (Terminal C)
    uv sync                          # installs xgboost / pandas / joblib added to pyproject.toml

## 2. Offline checks - no servers needed (Terminal C)
    uv run pytest tests/test_layer3_engine.py tests/test_layer4_aml.py -q
    uv run python scripts/demo_layer3_layer4.py
    uv run python scripts/fraudguard/validate_integration.py --data-dir /path/to/your/7/csvs --sample 5000
Look at the `source` column / `scorer:` line: it must say FRAUDGUARD, not RULES_ONLY. If it says
RULES_ONLY the XGBoost/pickle failed to load - retrain (section 7).

## 3. Infrastructure (Terminal C)
    docker compose up -d postgres neo4j
    uv run alembic upgrade head      # if it says "already exists": see section 8
    uv run python -m infrastructure.database.seed

## 4. Turn the layers on - edit `.env`, then RESTART Terminal A (Ctrl+C, run uvicorn again)
    RISK_ENGINE=layer3
    STEP_UP_DEV_ECHO=true            # shows the 2FA code on screen (dev only)
    LAYER4_ENABLED=true
    AML_THRESHOLD_EGP=1000           # demo value so small transfers can trigger smurfing
Terminal A:  uv run uvicorn apps.api.main:app --reload --port 8000
Terminal B:  cd frontend && npm run dev      (already running is fine)

## 5. Scenarios to test in the UI (log in as a customer -> Send Money)
| # | Do this | Expect |
|---|---------|--------|
| 1 | Small transfer to a recipient you already paid | Completes (LOW / ALLOW) |
| 2 | First-ever transfer to a new person, amount much larger than your usual | "Verify this transfer" dialog (MEDIUM). Enter the DEV code -> completes |
| 3 | Same as 2, enter a wrong code | "Incorrect verification code" (retry) |
| 4 | Same as 2, wrong code 3 times | Blocked + alert + ticket (step-up failed -> investigation queue) |
| 5 | Transfer through a VPN / from a new device + new country | Blocked (HIGH): no money moves, ref shown, ticket in admin Support/Cases |
| 6 | Three transfers of 600-900 EGP to the same person within a few minutes (threshold 1000) | 3rd one still completes, then an `AML_STRUCTURING` alert + ticket appear in the admin console |
| 7 | One customer sends to 5+ different recipients (each < 1000, total >= 1000) | `AML_FAN_OUT` alert |
| 8 | 5+ different customers send to one account | `AML_FAN_IN` alert on the receiver |
Check results: admin login -> Transactions / Risk monitoring / Support cases; Neo4j browser at
http://localhost:17474 (user `neo4j`, password `omerta_dev_password`):
    MATCH (a:Account)-[:SENT]->(t:Transaction)-[:RECEIVED_BY]->(b:Account) WHERE t.source='layer4_live' RETURN a,t,b LIMIT 50
SQL (Postgres): `SELECT alert_type, risk_score, risk_level FROM alerts ORDER BY id DESC LIMIT 10;`
NOTE: the amounts you can send depend on the seeded balances; a block/step-up depends on the model score
for YOUR data, so some scenarios may land in a neighbouring tier - that is what the offline script
(section 2) lets you inspect.

## 6. How the pieces connect
transfer -> Layer 3 (features -> FraudGuard score 0-100 -> typology -> tier)
  LOW 0-30   -> ALLOW -> transfer completes -> Layer 4
  MEDIUM     -> STEP_UP code -> pass: completes -> Layer 4 | fail x3: block + escalate
  HIGH 71+   -> BLOCK, no funds move, alert + investigation ticket
Layer 4 (after a CONFIRMED transfer): ingest into Neo4j -> patterns over the last 72 h (from Postgres):
STRUCTURING, FAN_OUT, FAN_IN, PASS_THROUGH, CYCLE -> finding? alert + ticket : nothing.
Layer 4 flags and escalates; it does not freeze funds (policy choice - say if you want auto-hold).

## 7. Retrain the model on your CSVs (if loading fails or you want fresh numbers)
    cd scripts/fraudguard
    uv run python train_models.py --data /path/to/your/7/csvs --models ../../models/fraudguard --reports ../../models/fraudguard
This overwrites the .joblib files in `models/fraudguard/` with ones built for YOUR installed xgboost/scikit-learn.

## 8. Troubleshooting
- Alembic "relation already exists": DB already has tables. `uv run alembic current` - if empty and the schema is
  current, `uv run alembic stamp head`; else reset the dev DB volume (docker compose down -v) and re-run section 3.
- Vite `ECONNREFUSED 8000`: backend (Terminal A) is not running.
- Neo4j down: transfers still work; the log shows `layer4_neo4j_ingest_skipped`.
- Step-up code not shown: `STEP_UP_DEV_ECHO=true` + restart Terminal A.
- `source: RULES_ONLY`: see section 2.

## 9. Push (Terminal C)
    git add -A && git status        # make sure no nested Omerta.ai/ or Downloads/ folder is staged
    git commit -m "feat: Layer 3 ML scoring + Layer 4 graph/AML engine"
    git push -u origin feature/layer3-layer4
Then open a Pull Request into main on GitHub. You don't need to delete anything from the main repo.
