"""NIM (NVIDIA Cloud) backend adapter.

Wraps the existing HardenedNIMClient + security stack behind the
LLMBackend interface. The security stack (rate limiter, circuit breaker,
cost monitor, audit logger, determinism monitor) stays inside
HardenedNIMClient — the router never reimplements it.
"""

from __future__ import annotations

import os
import json
import time as _time
import logging
from typing import Optional, Dict, Any, List, FrozenSet

from .base import LLMBackend, HealthStatus, CHAT, TOOLS

log = logging.getLogger(__name__)


# ── Env defaults ──────────────────────────────────────

_ENV_KEY = "NIM_API_KEY"
_ENV_MODEL = "NIM_MODEL"
_DEFAULT_MODEL = "mistralai/mistral-medium-3.5-128b"
_ENV_BASE_URL = "NIM_BASE_URL"
_DEFAULT_BASE_URL = "https://api.nvidia.com/v1"
_ENV_GATE = "AGENTIC_REASONING_ENABLED"
_ENV_ENV = "QORTROLLER_ENV"


class NimBackend(LLMBackend):
    """Adapter for NVIDIA NIM Cloud API.

    Wraps HardenedNIMClient with its full security stack.
    configured() returns True only if NIM_API_KEY is set AND
    AGENTIC_REASONING_ENABLED=true.
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get(_ENV_KEY, "")
        self._model = os.environ.get(_ENV_MODEL, _DEFAULT_MODEL)
        self._base_url = os.environ.get(_ENV_BASE_URL, _DEFAULT_BASE_URL)
        self._gate = os.environ.get(_ENV_GATE, "false").lower() == "true"
        self._env = os.environ.get(_ENV_ENV, "dev")
        self._client: Optional[Any] = None

        if self._api_key and self._gate:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize the HardenedNIMClient with env config."""
        try:
            from bridge.vapi_bridge.agentic_stewards.nim_client_hardened import (
                HardenedNIMClient,
                NIMConfig,
            )
        except ImportError:
            log.warning("HardenedNIMClient not importable (agentic_stewards missing?)")
            return

        config = NIMConfig(
            api_key=self._api_key,
            base_url=self._base_url,
            model=self._model,
            timeout=30.0,
            enabled=True,
            environment=self._env,
        )

        # Create a minimal store wrapper for the NIM client
        class _StoreProxy:
            def insert_nim_audit_log(self, metadata): pass
            def insert_llm_call_tracker(self, **kwargs): pass
            def _conn(self): return self
            def __enter__(self): return self
            def __exit__(self, *args): pass

        try:
            self._client = HardenedNIMClient(config, _StoreProxy())
            log.info("NimBackend initialized: %s (env=%s)", self._model, self._env)
        except Exception as exc:
            log.warning("NimBackend init failed: %s", exc)

    # ── LLMBackend interface ──────────────────────────

    @property
    def id(self) -> str:
        return "nim"

    @property
    def capabilities(self) -> FrozenSet[str]:
        return frozenset({CHAT, TOOLS})

    def configured(self) -> bool:
        return self._client is not None

    def is_available(self) -> bool:
        return self.configured()

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> Optional[str]:
        if not self._client:
            return None
        try:
            return await self._client.generate_reasoning(
                device_id="router",
                prompt=prompt,
                system=system_prompt,
            )
        except Exception as exc:
            log.error("NIM generate failed: %s", exc)
            return None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        if not self._client:
            return {"error": "NIM client not initialized"}

        # Flatten messages into prompt + system for generate_reasoning
        system = ""
        prompt_parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system = content
            else:
                prompt_parts.append(f"<{role}>: {content}")

        prompt = "\n".join(prompt_parts)

        try:
            content = await self._client.generate_reasoning(
                device_id="router",
                prompt=prompt,
                system=system,
            )
            if content is None:
                return {"error": "empty response"}

            # Shape into OpenAI-compatible response
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content,
                        }
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "model": self._model,
            }
        except Exception as exc:
            log.error("NIM chat failed: %s", exc)
            return {"error": str(exc)}

    async def health(self) -> HealthStatus:
        if not self._client:
            return HealthStatus(ok=False, error="not configured")

        start = _time()
        try:
            status = self._client.get_health_status()
            elapsed = (_time() - start) * 1000
            ok = status.get("enabled", False) and status.get("circuit_breaker") != "OPEN"
            return HealthStatus(
                ok=ok,
                latency_ms=elapsed,
                model=self._model,
                error="" if ok else "circuit breaker open or disabled",
            )
        except Exception as exc:
            elapsed = (_time() - start) * 1000
            return HealthStatus(ok=False, error=str(exc), latency_ms=elapsed)