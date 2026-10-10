"""Step-up challenge (2FA / biometric stand-in) for MEDIUM-risk transfers.

A one-time code is bound to (customer, recipient, amount, currency) so it cannot
authorise a different transfer. 5-minute expiry, 3 attempts, single use.

In-memory store: fine for a single dev process; use Redis/DB when running several
workers. Delivery is pluggable: pass a ``deliver`` callable (e.g. email service).
In dev, ``include_dev_code`` echoes the code back so the demo works without SMTP.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

TTL_SECONDS = 300
MAX_ATTEMPTS = 3


@dataclass
class _Challenge:
    customer_id: int
    binding: str
    code_hash: str
    salt: str
    expires_at: float
    attempts: int = 0


_STORE: dict[str, _Challenge] = {}


def _binding(customer_id: int, recipient: str, amount: str, currency: str) -> str:
    return f"{customer_id}|{recipient}|{amount}|{currency.upper()}"


def _hash(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode()).hexdigest()


def _purge(now: float) -> None:
    for k in [k for k, c in _STORE.items() if c.expires_at < now]:
        _STORE.pop(k, None)


def issue_challenge(
    *, customer_id: int, recipient: str, amount: str, currency: str,
    deliver: Callable[[str], None] | None = None, include_dev_code: bool = False,
) -> dict:
    now = time.time()
    _purge(now)
    code = f"{secrets.randbelow(10**6):06d}"
    salt = secrets.token_hex(8)
    cid = f"STEP-{secrets.token_hex(6).upper()}"
    _STORE[cid] = _Challenge(customer_id, _binding(customer_id, recipient, amount, currency),
                             _hash(code, salt), salt, now + TTL_SECONDS)
    if deliver:
        deliver(code)
    out = {"challenge_id": cid, "expires_in_seconds": TTL_SECONDS, "method": "OTP"}
    if include_dev_code:
        out["dev_code"] = code
    return out


def verify_challenge_detailed(
    *, challenge_id: str | None, code: str | None, customer_id: int,
    recipient: str, amount: str, currency: str,
) -> str:
    """Return OK | WRONG (retry allowed) | LOCKED (attempts exhausted) | INVALID
    (missing/expired/unknown/mismatched challenge -> issue a new one)."""
    if not challenge_id or not code:
        return "INVALID"
    now = time.time()
    ch = _STORE.get(challenge_id)
    if ch is None or ch.expires_at < now:
        _STORE.pop(challenge_id, None)
        return "INVALID"
    if ch.customer_id != customer_id or ch.binding != _binding(customer_id, recipient, amount, currency):
        return "INVALID"
    ch.attempts += 1
    if hmac.compare_digest(ch.code_hash, _hash(code.strip(), ch.salt)):
        _STORE.pop(challenge_id, None)
        return "OK"
    if ch.attempts >= MAX_ATTEMPTS:
        _STORE.pop(challenge_id, None)
        return "LOCKED"
    return "WRONG"


def verify_challenge(**kwargs) -> bool:
    """Boolean convenience wrapper (True only for OK)."""
    return verify_challenge_detailed(**kwargs) == "OK"
