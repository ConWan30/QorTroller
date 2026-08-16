#!/usr/bin/env python3
"""
QorTroller clients
==================
QuickSilverClient (LLM) + BridgeClient (HTTP), extracted verbatim from
qortroller.py (second step of the monolith split; qortroller.py re-exports
both as a façade). Env-derived constants are mirrored from qortroller.py's
configuration block on purpose — both files read the same env vars.
"""

from __future__ import annotations

import os
import time
from typing import Any, Optional

import requests

# Mirrored from qortroller.py CONFIGURATION (keep values in sync)
QUICKSILVER_API_KEY = os.environ.get("QUICKSILVER_API_KEY", "")
QUICKSILVER_API_URL = "https://api.quicksilverpro.io/v1/chat/completions"
QUICKSILVER_MODEL = os.environ.get("QUICKSILVER_MODEL", "deepseek-v4-flash")
BRIDGE_BASE_URL = os.environ.get("BRIDGE_BASE_URL", "http://localhost:8000")
VERSION = "2.0.0"


# ═══════════════════════════════════════════════════════════════════════════════
#  QUICKSILVER PRO LLM CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class QuickSilverClient:
    """Client for QuickSilver Pro API. Model-agnostic — swap models freely."""

    def __init__(self, api_key: str = QUICKSILVER_API_KEY,
                 model: str = QUICKSILVER_MODEL):
        self.api_key = api_key
        self.model = model
        self.api_url = QUICKSILVER_API_URL
        self._session = None

    def _import_requests(self):
        """Lazy import to avoid dependency on unavailable packages."""
        try:
            import requests
            return requests
        except ImportError:
            raise ImportError(
                "requests not installed. Run: pip install requests"
            )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict], tools: Optional[list[dict]] = None,
             temperature: float = 0.7, max_tokens: int = 4096) -> dict:
        """Send a chat completion request to QuickSilver Pro."""
        if not self.configured:
            return {
                "error": "QUICKSILVER_API_KEY not configured",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": (
                            "I cannot process this request because the "
                            "QUICKSILVER_API_KEY is not configured.\n\n"
                            "Set it in your environment or .env file:\n"
                            "  QUICKSILVER_API_KEY=sk-..."
                        )
                    }
                }]
            }

        requests = self._import_requests()
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                self.api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": f"QorTroller/{VERSION}",
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout:
            return {"error": "LLM request timed out after 120s"}
        except requests.exceptions.RequestException as e:
            return {"error": f"LLM request failed: {e}"}

    def ping(self) -> dict:
        """Test connectivity to QuickSilver Pro."""
        if not self.configured:
            return {"ok": False, "error": "API key not configured"}
        requests = self._import_requests()
        try:
            resp = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 10,
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return {"ok": True, "model": self.model}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  BRIDGE CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class BridgeClient:
    """HTTP client for the QorTroller bridge operator API."""

    def __init__(self, base_url: str = BRIDGE_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def _import_requests(self):
        try:
            import requests
            return requests
        except ImportError:
            raise ImportError("requests not installed")

    def health(self) -> dict:
        requests = self._import_requests()
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            data["status"] = "healthy"
            data["latency_s"] = resp.elapsed.total_seconds()
            return data
        except Exception as e:
            return {"status": "unreachable", "error": str(e), "latency_s": None}

    def get(self, path: str, timeout: float = 10) -> Optional[dict]:
        requests = self._import_requests()
        try:
            resp = requests.get(f"{self.base_url}{path}", timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def post(self, path: str, data: dict = None, timeout: float = 30) -> Optional[dict]:
        requests = self._import_requests()
        try:
            resp = requests.post(
                f"{self.base_url}{path}",
                json=data or {},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def is_up(self) -> bool:
        h = self.health()
        return h.get("status") == "healthy"

    def get_agent_statuses(self) -> list[dict]:
        """Get status of all bridge agents."""
        data = self.get("/agent/statuses", timeout=10)
        if data and isinstance(data, list):
            return data
        # Try alternative endpoint
        data = self.get("/agents", timeout=10)
        if data and isinstance(data, list):
            return data
        return []

    def get_contradictions(self) -> list[dict]:
        """Get current FSCA contradictions."""
        data = self.get("/agent/contradictions", timeout=10)
        if data and isinstance(data, list):
            return data
        data = self.get("/fsca/contradictions", timeout=10)
        if data and isinstance(data, list):
            return data
        return []

    def get_separation_status(self) -> Optional[dict]:
        return self.get("/agent/separation-defensibility-status", timeout=10)

    def get_tournament_eligibility(self) -> Optional[dict]:
        return self.get("/agent/tournament-eligibility", timeout=10)

    def get_protocol_state(self) -> dict:
        """Aggregate protocol state from multiple bridge endpoints."""
        return {
            "health": self.health(),
            "agents": self.get_agent_statuses(),
            "contradictions": self.get_contradictions(),
            "separation": self.get_separation_status(),
        }


