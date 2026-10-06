"""In-process token-bucket rate limiting (Phase 17).

A single-node safeguard against runaway clients and basic flooding - not a
distributed rate limiter (the deployment is single-API-node; Redis/Kafka are
deliberately out of scope). Buckets are keyed by API key (when authenticated)
or client IP. Each bucket refills at ``rate_per_minute / 60`` tokens per
second up to ``capacity``; an empty bucket yields HTTP 429.
"""

import time
from collections import defaultdict


class TokenBucket:
    __slots__ = ("capacity", "tokens", "refill_per_second", "updated_at")

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_per_second = refill_per_second
        self.updated_at = time.monotonic()

    def take(self) -> bool:
        now = time.monotonic()
        self.tokens = min(
            self.capacity, self.tokens + (now - self.updated_at) * self.refill_per_second
        )
        self.updated_at = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    def __init__(self, per_minute: int, burst: int | None = None) -> None:
        # per_minute == 0 means DISABLED (kept as 0, never clamped to 1).
        self.rate_per_minute = max(0, per_minute)
        self.capacity = max(1, burst if burst is not None else max(per_minute, 1))
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(self.capacity, self.rate_per_minute / 60.0)
        )

    def allow(self, key: str) -> bool:
        if self.rate_per_minute <= 0:
            return True
        return self._buckets[key].take()

    def reset(self) -> None:
        self._buckets.clear()


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """Limiter configured from settings (created once per process)."""
    global _limiter
    if _limiter is None:
        from infrastructure.config import get_settings

        settings = get_settings()
        _limiter = RateLimiter(
            per_minute=settings.rate_limit_per_minute,
            burst=settings.rate_limit_burst,
        )
    return _limiter


def reset_limiter() -> None:
    global _limiter
    _limiter = None
