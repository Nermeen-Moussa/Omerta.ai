"""Deterministic, no-network LLM provider (tests / offline operation).

Never calls any API and requires no key. It simply echoes a structured
response so the agent pipeline can run end-to-end deterministically.
"""

from typing import Any

from infrastructure.llm.base import LLMResponse


class FakeLLMProvider:
    """Deterministic provider used in tests and when no API is configured."""

    name = "fake"
    model = "fake-model-v1"

    async def complete(self, system: str, user: str, **kwargs: Any) -> LLMResponse:
        """Return a fixed completion; the agent node parses the user payload."""
        marker = "FAKE::"
        content = user if user.startswith(marker) else f"{marker}{user[:120]}"
        return LLMResponse(content=content, provider=self.name, model=self.model)
