"""End-to-end scenario tester for Layer 3 (ML scoring / step-up / block) and Layer 4 (AML).

Talks to your RUNNING backend over HTTP, creating fresh throw-away customers each run
(no manual clicking, nothing existing is modified).

Prerequisites
  * backend running on http://127.0.0.1:8000  (uv run uvicorn apps.api.main:app --reload --port 8000)
  * .env contains:  RISK_ENGINE=layer3  STEP_UP_DEV_ECHO=true  LAYER4_ENABLED=true
                    LAYER4_NEO4J_INGEST=false  AML_THRESHOLD_EGP=1000
Run (new terminal, repo root):
    uv run python scripts/e2e_scenarios.py
    uv run python scripts/e2e_scenarios.py --aml-threshold 1000 --base-url http://127.0.0.1:8000
`--aml-threshold` MUST equal AML_THRESHOLD_EGP in the backend's .env.
"""

import argparse
import secrets
import subprocess
import sys

import httpx

ACCT_PW = "AccountLoginPass2026!"
XFER_PW = "TransferSecure2026!"


class User:
    def __init__(self, name, token, number, account_id):
        self.name, self.number, self.account_id = name, number, account_id
        self.headers = {"Authorization": f"Bearer {token}"}


def register(http, label, balance=200000.0):
    tag = secrets.token_hex(3)
    body = {
        "full_name": f"{label} {tag}", "email": f"{label.lower()}.{tag}@e2e.omerta.ai",
        "username": f"{label.lower()}_{tag}", "national_id_number": "".join(secrets.choice("0123456789") for _ in range(14)),
        "password": ACCT_PW, "confirm_password": ACCT_PW,
        "transfer_password": XFER_PW, "confirm_transfer_password": XFER_PW,
        "country": "EG", "preferred_currency": "EGP", "initial_balance": balance, "device_consent": True,
    }
    r = http.post("/api/v1/auth/register", json=body)
    if r.status_code != 201:
        sys.exit(f"register failed ({r.status_code}): {r.text[:300]}")
    d = r.json()
    h = {"Authorization": f"Bearer {d['access_token']}"}
    acc = http.get("/api/v1/customer/accounts", headers=h).json()[0]["account_id"]
    return User(body["full_name"], d["access_token"], d["customer"]["omerta_user_number"], acc)


def send(http, sender, recipient, amount, code=None, challenge=None, **extra):
    body = {"sender_account_id": sender.account_id, "recipient_user_number": recipient.number,
            "amount": amount, "currency": "EGP", "password": XFER_PW, "note": "e2e", **extra}
    if code:
        body.update(step_up_code=code, step_up_challenge_id=challenge)
    r = http.post("/api/v1/customer/transfers", json=body, headers=sender.headers)
    try:
        j = r.json()
    except Exception:
        j = {"raw": r.text[:200]}
    return r.status_code, j


def describe(status, j):
    if status == 201:
        return f"COMPLETED  score={j.get('risk_score')} level={j.get('risk_level')}"
    d = j.get("detail", j) if isinstance(j, dict) else j
    err = d.get("error") if isinstance(d, dict) else None
    extra = ""
    if isinstance(d, dict) and d.get("tier"):
        extra = f" tier={d.get('tier')} score={d.get('risk_score')} typology={d.get('typology')}"
    return f"HTTP {status} {err}{extra}"


_WARNED: list = []


def aml_counts():
    sql = "SELECT alert_type, count(*) FROM alerts WHERE alert_type LIKE 'AML_%' GROUP BY 1 ORDER BY 1"
    try:
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "omerta", "-d", "omerta", "-At", "-F", "|", "-c", sql],
            capture_output=True, text=True, timeout=30, check=True).stdout
        return {l.split("|")[0]: int(l.split("|")[1]) for l in out.splitlines() if "|" in l}
    except Exception as exc:
        if not _WARNED:
            _WARNED.append(1)
            print(f"   (could not read alerts from Postgres via docker: {exc}) - run this script from the repo root)")
        return None


def new_alerts(before, after):
    if before is None or after is None:
        return "unknown (see admin console / SQL)"
    diff = {k: after.get(k, 0) - before.get(k, 0) for k in after if after.get(k, 0) != before.get(k, 0)}
    return ", ".join(f"{k} x{v}" for k, v in diff.items()) or "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--aml-threshold", type=float, default=1000.0)
    a = ap.parse_args()
    T = a.aml_threshold
    http = httpx.Client(base_url=a.base_url, timeout=60)
    try:
        http.get("/openapi.json").raise_for_status()
    except Exception as exc:
        sys.exit(f"Backend not reachable at {a.base_url}: {exc}\nStart it first (Terminal A).")

    print("\n##### LAYER 3 #####")
    alice, bob = register(http, "Alice"), register(http, "Bob")

    print("\n[S1] Routine small transfers to a known recipient (expect COMPLETED, LOW)")
    for amt in (150, 200, 250):
        print("   ", amt, "->", describe(*send(http, alice, bob, amt)))

    print("\n[S2] Amount ladder: first-time transfer to a NEW recipient, rising amounts")
    stepup = None
    for amt in (500, 5000, 20000, 60000, 150000):
        rcp = register(http, "Rcp", balance=1000)
        st, j = send(http, alice, rcp, amt)
        print(f"    {amt:>7} EGP ->", describe(st, j))
        d = j.get("detail", {}) if isinstance(j, dict) else {}
        if st == 428 and d.get("error") == "STEP_UP_REQUIRED" and stepup is None:
            stepup = (amt, rcp, d)

    print("\n[S3] Step-up flow")
    if not stepup:
        print("    SKIPPED - no amount reached the MEDIUM tier with the current model/data. That is a valid")
        print("    result (see the ladder above); try the 'ml_score' by running scripts/demo_layer3_layer4.py.")
    else:
        amt, rcp, d = stepup
        print(f"    challenge issued for {amt} EGP; dev_code present: {'dev_code' in d} (needs STEP_UP_DEV_ECHO=true)")
        st, j = send(http, alice, rcp, amt, code="000000" if d.get("dev_code") != "000000" else "111111", challenge=d["challenge_id"])
        print("    wrong code    ->", describe(st, j), "(expect STEP_UP_INVALID_CODE)")
        if d.get("dev_code"):
            st, j = send(http, alice, rcp, amt, code=d["dev_code"], challenge=d["challenge_id"])
            print("    correct code  ->", describe(st, j), "(expect COMPLETED)")
        # lockout on a fresh challenge
        rcp2 = register(http, "Rcp", balance=1000)
        st, j = send(http, alice, rcp2, amt)
        d2 = j.get("detail", {}) if isinstance(j, dict) else {}
        if st == 428 and d2.get("challenge_id"):
            for i in range(3):
                st, j = send(http, alice, rcp2, amt, code="999999", challenge=d2["challenge_id"])
                print(f"    wrong code #{i + 1} ->", describe(st, j))
            print("    (expect the 3rd to be TRANSFER_BLOCKED_HIGH_RISK -> alert + ticket for investigation)")

    print("\n[S4] VPN session (existing VPN policy gate; expect HTTP 403 VPN_TRANSFER_BLOCKED)")
    print("    ", describe(*send(http, alice, bob, 100, is_vpn=True)))

    print("\n##### LAYER 4 (alerts are read from Postgres) #####")
    print(f"AML threshold assumed: {T:,.0f} EGP (must match AML_THRESHOLD_EGP in .env)")

    print("\n[S5] Control: 3 small transfers well below the band (expect NO alert)")
    s, r = register(http, "Ctl"), register(http, "CtlR", 1000)
    before = aml_counts()
    for _ in range(3):
        send(http, s, r, round(T * 0.05, 2))
    print("    new AML alerts:", new_alerts(before, aml_counts()))

    print("\n[S6] Smurfing: 3 x 0.8*threshold to one recipient (expect AML_STRUCTURING)")
    s, r = register(http, "Smurf"), register(http, "SmurfR", 1000)
    before = aml_counts()
    for _ in range(3):
        print("    ", describe(*send(http, s, r, round(T * 0.8, 2))))
    print("    new AML alerts:", new_alerts(before, aml_counts()))

    print("\n[S7] Fan-out: one sender -> 6 different recipients, 0.3*threshold each (expect AML_FAN_OUT)")
    s = register(http, "Fan")
    before = aml_counts()
    for _ in range(6):
        print("    ", describe(*send(http, s, register(http, "FanR", 1000), round(T * 0.3, 2))))
    print("    new AML alerts:", new_alerts(before, aml_counts()))
    print("    (Layer 4 only analyses CONFIRMED transfers: if these were blocked by Layer 3 there is nothing to analyse)")

    print("\n[S8] Fan-in: 6 different senders -> one account, 0.3*threshold each (expect AML_FAN_IN)")
    col = register(http, "Collector", 1000)
    before = aml_counts()
    for _ in range(6):
        print("    ", describe(*send(http, register(http, "Src"), col, round(T * 0.3, 2))))
    print("    new AML alerts:", new_alerts(before, aml_counts()))
    print("\nDone. Tickets/alerts are also visible in the admin console (Transactions, Risk monitoring, Support cases).\n")


if __name__ == "__main__":
    main()
