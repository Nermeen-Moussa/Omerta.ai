"""OpenAI-compatible chat-completions provider over httpx.

Works with OpenAI, Groq, Ollama, vLLM, and other compatible gateways by
combining ``LLM_PROVIDER``/``LLM_MODEL``/``LLM_API_KEY`` with an optional
``LLM_BASE_URL`` override. The API key never appears in exceptions or logs
that reach tool consumers.
"""

import logging
from typing import Any

import httpx

from infrastructure.llm.base import LLMResponse

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_TOKENS = 1024
TEMPERATURE = 0.0  # investigations must be reproducible


class OpenAICompatibleProvider:
    """Minimal chat-completions client with deterministic settings."""

    def __init__(
        self,
        *,
        name: str,
        model: str,
        api_key: str | None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        self.name = name
        self.model = model
        self._api_key = api_key
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout = timeout
        self._max_tokens = max_tokens

    async def complete(self, system: str, user: str, **kwargs: Any) -> LLMResponse:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": kwargs.get("temperature", TEMPERATURE),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            # Never include the request (which carries the auth header).
            logger.error("llm http status %s", exc.response.status_code)
            raise RuntimeError(
                f"LLM request failed with status {exc.response.status_code}"
            ) from None
        except httpx.HTTPError as exc:
            logger.error("llm transport error: %s", type(exc).__name__)
            raise RuntimeError("LLM transport error") from None

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM response missing expected content") from exc
        return LLMResponse(content=content, provider=self.name, model=self.model)
