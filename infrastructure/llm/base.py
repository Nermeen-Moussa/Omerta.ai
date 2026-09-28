"""Provider-agnostic LLM contracts (Phase 9).

``LLMProvider`` is the stable protocol. Implementations live beside it; the
investigator agent depends only on this interface, so providers can be swapped
via environment configuration without touching agent code.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMResponse:
    """Normalized LLM completion result."""

    content: str
    provider: str
    model: str


class LLMProvider(Protocol):
    """Minimal chat interface every provider must implement."""

    name: str
    model: str

    async def complete(self, system: str, user: str, **kwargs: Any) -> LLMResponse:
        """Return one completion for the given messages."""
        ...  # pragma: no cover - interface definition
