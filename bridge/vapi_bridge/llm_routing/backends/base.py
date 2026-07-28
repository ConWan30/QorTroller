"""Abstract base class for all LLM backend adapters.

Every backend — QuickSilver, NIM, LOCAL — implements this interface.
The router never reaches into backend internals; it only calls these methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, FrozenSet


# ── Capability flags ──────────────────────────────────

CHAT = "CHAT"
TOOLS = "TOOLS"
VISION = "VISION"
STREAM = "STREAM"


# ── Health response ───────────────────────────────────

@dataclass
class HealthStatus:
    """Response from a backend health check."""
    ok: bool
    latency_ms: float = 0.0
    model: str = ""
    error: str = ""


# ── Provider response ─────────────────────────────────

@dataclass
class ProviderResponse:
    """Raw response from a single backend attempt.
    The router wraps this into a RouteResult with provenance.
    """
    content: Optional[str] = None
    success: bool = False
    latency_ms: float = 0.0
    model: str = ""
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── LLMBackend interface ──────────────────────────────

class LLMBackend(ABC):
    """Interface every LLM backend adapter implements."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Backend identifier: 'quicksilver' | 'nim' | 'local'."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> FrozenSet[str]:
        """Capability flags: {CHAT, TOOLS, VISION, STREAM}.
        Used by the router to skip backends that can't handle a request.
        """
        ...

    @abstractmethod
    def configured(self) -> bool:
        """Is this backend's config present (API key, endpoint, model)?

        Called once at router init to build the provider chain.
        Does NOT check reachability — that's health().
        Must be fast (no I/O).
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Quick synchronous check — configured AND not in cooldown.

        Called on every routing attempt before the async call.
        Must be fast (no I/O).
        """
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> Optional[str]:
        """Simple prompt → text convenience wrapper.

        Implementations typically delegate to chat() with a
        two-message [{role:"system", content:system_prompt},
                     {role:"user", content:prompt}] array.
        Returns the text response, or None on failure.
        """
        ...

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """OpenAI-shaped chat completions interface.

        Args:
            messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
            tools: Optional OpenAI tool definitions.
            temperature: 0.0 = deterministic, 1.0 = creative.
            max_tokens: Maximum tokens in the response.

        Returns:
            OpenAI-shaped dict on success:
            {"choices": [{"message": {"role": "assistant", "content": "..."}, ...}],
             "usage": {"prompt_tokens": N, "completion_tokens": N, "total_tokens": N},
             "model": "..."}
            or error-shaped:
            {"error": {"message": "...", "type": "..."}}
        """
        ...

    @abstractmethod
    async def health(self) -> HealthStatus:
        """Probe backend reachability.

        Returns:
            HealthStatus with ok=True if the backend responded,
            ok=False with error message otherwise.
        """
        ...