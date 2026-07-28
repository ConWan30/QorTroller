"""LOCAL OpenAI-compatible LLM adapter (R1).

Default-OFF. Targets Ollama / any OpenAI-compatible local server.
Does NOT touch PoAC / PV-CI / classify / PoSP. No FROZEN surface.
Claude is not a backend target.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import requests

# Defaults match Ollama's OpenAI-compatible surface.
_DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
_DEFAULT_MODEL = "deepseek-r1:14b"
_DEFAULT_TIMEOUT_S = 8.0

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in _TRUTHY


@dataclass(frozen=True, slots=True)
class LocalHealth:
    """Honest health snapshot for the LOCAL backend."""

    ok: bool
    enabled: bool
    base_url: str
    model: str
    detail: str
    latency_ms: Optional[float] = None
    live: bool = False  # True only when a real probe reached the server

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "enabled": self.enabled,
            "base_url": self.base_url,
            "model": self.model,
            "detail": self.detail,
            "latency_ms": self.latency_ms,
            "live": self.live,
            "backend": "local",
        }


class LocalOpenAIClient:
    """OpenAI-compatible chat client for a local server (Ollama et al.).

    Rails:
      - LOCAL_LLM_ENABLED must be truthy or every call is a no-op (default-OFF).
      - Fail-open: network errors -> None / unhealthy, never raise to callers of
        chat(); health() always returns a LocalHealth.
      - No API key required for typical Ollama; optional LOCAL_LLM_API_KEY if set.
      - Does not load dotenv or hardcode secrets.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        enabled: Optional[bool] = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
        api_key: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.base_url = (base_url or os.environ.get("LOCAL_LLM_BASE_URL") or _DEFAULT_BASE_URL).rstrip(
            "/"
        )
        self.model = model or os.environ.get("LOCAL_LLM_MODEL") or _DEFAULT_MODEL
        self.enabled = (
            bool(enabled) if enabled is not None else _env_truthy("LOCAL_LLM_ENABLED")
        )
        self.timeout_s = float(timeout_s)
        self.api_key = api_key if api_key is not None else os.environ.get("LOCAL_LLM_API_KEY", "")
        self._session = session or requests.Session()

    @property
    def configured(self) -> bool:
        """True when the operator has opted in (LOCAL_LLM_ENABLED)."""
        return self.enabled

    def health(self) -> LocalHealth:
        """Probe the local server. Fail-open: never raises."""
        if not self.enabled:
            return LocalHealth(
                ok=False,
                enabled=False,
                base_url=self.base_url,
                model=self.model,
                detail="local_llm_disabled",
                live=False,
            )

        url = f"{self.base_url}/models"
        t0 = time.perf_counter()
        try:
            resp = self._session.get(
                url,
                headers=self._headers(),
                timeout=self.timeout_s,
                proxies={"http": None, "https": None},
            )
            latency = (time.perf_counter() - t0) * 1000.0
            if resp.status_code >= 400:
                return LocalHealth(
                    ok=False,
                    enabled=True,
                    base_url=self.base_url,
                    model=self.model,
                    detail=f"http_{resp.status_code}",
                    latency_ms=latency,
                    live=True,
                )
            detail = "ok"
            try:
                payload = resp.json()
                models = payload.get("data") if isinstance(payload, dict) else None
                if isinstance(models, list) and models:
                    ids = {m.get("id") for m in models if isinstance(m, dict)}
                    if self.model not in ids:
                        detail = f"model_not_listed:{self.model}"
            except Exception:
                detail = "ok_non_json"
            return LocalHealth(
                ok=True,
                enabled=True,
                base_url=self.base_url,
                model=self.model,
                detail=detail,
                latency_ms=latency,
                live=True,
            )
        except requests.RequestException as exc:
            latency = (time.perf_counter() - t0) * 1000.0
            return LocalHealth(
                ok=False,
                enabled=True,
                base_url=self.base_url,
                model=self.model,
                detail=f"unreachable:{type(exc).__name__}",
                latency_ms=latency,
                live=False,
            )
        except Exception as exc:  # pragma: no cover
            return LocalHealth(
                ok=False,
                enabled=True,
                base_url=self.base_url,
                model=self.model,
                detail=f"error:{type(exc).__name__}",
                live=False,
            )

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        """POST /chat/completions. Returns content string or None (fail-open)."""
        if not self.enabled:
            return None

        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": list(messages),
        }
        if temperature is not None:
            payload["temperature"] = temperature

        try:
            resp = self._session.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=self.timeout_s,
                proxies={"http": None, "https": None},
            )
            resp.raise_for_status()
            result = resp.json()
            return result["choices"][0]["message"]["content"]
        except Exception:
            return None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
