"""QuickSilver backend adapter.

Wraps the existing QuickSilverClient (qortroller.py:459) behind the
LLMBackend interface. No behavior changes — thin delegation.
"""

from __future__ import annotations

import os
import asyncio
import logging
from typing import Optional, Dict, Any, List, FrozenSet

from .base import LLMBackend, HealthStatus, CHAT, TOOLS

log = logging.getLogger(__name__)


# ── Env defaults ──────────────────────────────────────

_ENV_KEY = "QUICKSILVER_API_KEY"
_ENV_MODEL = "QUICKSILVER_MODEL"
_DEFAULT_MODEL = "deepseek-v4-flash"
_ENV_URL = "QUICKSILVER_API_URL"
_DEFAULT_URL = "https://api.quicksilverpro.io/v1/chat/completions"


class QuickSilverBackend(LLMBackend):
    """Adapter for QuickSilver Pro API.

    Wraps the existing QuickSilverClient from qortroller.py.
    configured() returns True only if QUICKSILVER_API_KEY is set.
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get(_ENV_KEY, "")
        self._model = os.environ.get(_ENV_MODEL, _DEFAULT_MODEL)
        self._api_url = os.environ.get(_ENV_URL, _DEFAULT_URL)
        self._client: Optional[Any] = None

        if self._api_key:
            try:
                from qortroller import QuickSilverClient  # type: ignore
                self._client = QuickSilverClient(
                    api_key=self._api_key,
                    model=self._model,
                )
            except ImportError:
                log.warning("QuickSilverClient not importable (qortroller.py missing?)")
            except Exception as exc:
                log.warning("QuickSilverClient init failed: %s", exc)

    # ── LLMBackend interface ──────────────────────────

    @property
    def id(self) -> str:
        return "quicksilver"

    @property
    def capabilities(self) -> FrozenSet[str]:
        return frozenset({CHAT, TOOLS})

    def configured(self) -> bool:
        return self._client is not None and bool(self._api_key)

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
            return {"error": "QuickSilverClient not initialized"}

        try:
            # The existing client is sync — run in thread pool
            return await asyncio.to_thread(
                self._client.chat,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            log.error("QuickSilver chat failed: %s", exc)
            return {"error": str(exc)}

    async def health(self) -> HealthStatus:
        if not self._client:
            return HealthStatus(ok=False, error="not configured")

        start = _time()
        try:
            result = await self.generate("ping", "")
            elapsed = (_time() - start) * 1000
            if result is not None:
                return HealthStatus(ok=True, latency_ms=elapsed, model=self._model)
            return HealthStatus(ok=False, error="empty response", latency_ms=elapsed)
        except Exception as exc:
            elapsed = (_time() - start) * 1000
            return HealthStatus(ok=False, error=str(exc), latency_ms=elapsed)


import time as _time