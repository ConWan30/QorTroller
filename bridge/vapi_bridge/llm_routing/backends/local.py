"""LOCAL backend adapter — OpenAI-compatible local inference.

Connects to Ollama, vLLM, or llama.cpp server at a localhost endpoint
via the same /v1/chat/completions schema the cloud backends use.
No API key required. Bound to localhost by default.
"""

from __future__ import annotations

import os
import time as _time
import json
import logging
from typing import Optional, Dict, Any, List, FrozenSet

from .base import LLMBackend, HealthStatus, CHAT

log = logging.getLogger(__name__)


# ── Env defaults ──────────────────────────────────────

_ENV_ENABLED = "LOCAL_LLM_ENABLED"
_ENV_BASE_URL = "LOCAL_LLM_BASE_URL"
_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
_ENV_MODEL = "LOCAL_LLM_MODEL"
_DEFAULT_MODEL = "deepseek-r1:14b"
_ENV_API_KEY = "LOCAL_LLM_API_KEY"
_ENV_TIMEOUT = "LOCAL_LLM_TIMEOUT_SECONDS"
_DEFAULT_TIMEOUT = 120
_ENV_MAX_TOKENS = "LOCAL_LLM_MAX_TOKENS"
_DEFAULT_MAX_TOKENS = 4096


class LocalBackend(LLMBackend):
    """Adapter for local OpenAI-compatible inference servers.

    Supports Ollama, vLLM, and llama.cpp server — all expose the same
    /v1/chat/completions endpoint. configured() returns True only if
    LOCAL_LLM_ENABLED=true and the endpoint is reachable.
    """

    def __init__(self) -> None:
        self._enabled = os.environ.get(_ENV_ENABLED, "false").lower() == "true"
        self._base_url = os.environ.get(_ENV_BASE_URL, _DEFAULT_BASE_URL)
        self._model = os.environ.get(_ENV_MODEL, _DEFAULT_MODEL)
        self._api_key = os.environ.get(_ENV_API_KEY, "")
        self._timeout = int(os.environ.get(_ENV_TIMEOUT, str(_DEFAULT_TIMEOUT)))
        self._max_tokens = int(os.environ.get(_ENV_MAX_TOKENS, str(_DEFAULT_MAX_TOKENS)))

        self._client: Optional[Any] = None
        if self._enabled:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize the OpenAI-compatible client."""
        try:
            from openai import AsyncOpenAI

            kwargs: Dict[str, Any] = {
                "base_url": self._base_url,
            }
            if self._api_key:
                kwargs["api_key"] = self._api_key
            else:
                # Ollama doesn't require an API key by default
                kwargs["api_key"] = "ollama"

            self._client = AsyncOpenAI(**kwargs)
            log.info(
                "LocalBackend initialized: %s @ %s",
                self._model, self._base_url,
            )
        except ImportError:
            log.warning(
                "openai package not installed — LOCAL backend unavailable. "
                "Install with: pip install openai"
            )
        except Exception as exc:
            log.warning("LocalBackend init failed: %s", exc)

    # ── LLMBackend interface ──────────────────────────

    @property
    def id(self) -> str:
        return "local"

    @property
    def capabilities(self) -> FrozenSet[str]:
        return frozenset({CHAT})

    def configured(self) -> bool:
        return self._client is not None

    def is_available(self) -> bool:
        return self.configured()

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> Optional[str]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        result = await self.chat(messages)
        if "error" in result:
            return None
        choices = result.get("choices", [])
        if not choices:
            return None
        return choices[0]["message"]["content"]

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        if not self._client:
            return {"error": "LOCAL client not initialized"}

        try:
            kwargs: Dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"] = tools

            response = await self._client.chat.completions.create(**kwargs)

            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": response.choices[0].message.content,
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                "model": response.model,
            }
        except Exception as exc:
            log.error("LOCAL chat failed: %s", exc)
            return {"error": str(exc)}

    async def health(self) -> HealthStatus:
        if not self._client:
            return HealthStatus(ok=False, error="not configured")

        start = _time()
        try:
            # Lightweight probe: list models from the local server
            response = await self._client.models.list()
            elapsed = (_time() - start) * 1000
            available_models = [m.id for m in response.data]

            if self._model in available_models:
                return HealthStatus(ok=True, latency_ms=elapsed, model=self._model)

            # Model not pulled yet — server is up but model missing
            log.warning(
                "LOCAL model '%s' not found. Available: %s",
                self._model, available_models[:5],
            )
            return HealthStatus(
                ok=True,
                latency_ms=elapsed,
                model=self._model,
                error=f"model '{self._model}' not loaded. Pull it with: ollama pull {self._model}",
            )

        except Exception as exc:
            elapsed = (_time() - start) * 1000
            return HealthStatus(ok=False, error=str(exc), latency_ms=elapsed)