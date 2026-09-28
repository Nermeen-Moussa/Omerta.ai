"""API-key authentication with roles (Phase 17).

Design: the API is an internal analyst tool. When no API keys are configured
(development/test default) auth is DISABLED and everything behaves as before.
When keys are configured, every non-health/static request must present
``X-API-Key``; the key maps to a role:

- ANALYST: read + run investigations (the working role);
- ADMIN: everything ANALYST has (supervision/administration - reserved for
  later review-action endpoints; enforcement stays human-only regardless).

Keys come from environment configuration only - never from source. A wrong
key is 401; a valid key with an insufficient role is 403. Keys are never
logged; errors say only which header was missing/invalid.
"""

import hmac
import logging
from enum import StrEnum

logger = logging.getLogger(__name__)

API_KEY_HEADER = "X-API-Key"


class Role(StrEnum):
    ANALYST = "ANALYST"
    ADMIN = "ADMIN"


ROLE_RANK: dict[Role, int] = {Role.ANALYST: 1, Role.ADMIN: 2}


def configured_keys() -> dict[str, Role]:
    """API keys -> roles from settings (empty dict = auth disabled)."""
    from infrastructure.config import get_settings

    settings = get_settings()
    keys: dict[str, Role] = {}
    if settings.api_key_analyst:
        keys[settings.api_key_analyst] = Role.ANALYST
    if settings.api_key_admin:
        keys[settings.api_key_admin] = Role.ADMIN
    return keys


def auth_enabled() -> bool:
    return bool(configured_keys())


def resolve_role(api_key: str | None) -> Role | None:
    """Constant-time-ish key check (hmac.compare_digest per candidate)."""
    if not api_key:
        return None
    for candidate, role in configured_keys().items():
        if hmac.compare_digest(api_key, candidate):
            return role
    return None


def has_role(role: Role | None, minimum: Role) -> bool:
    if role is None:
        return False
    return ROLE_RANK[role] >= ROLE_RANK[minimum]
