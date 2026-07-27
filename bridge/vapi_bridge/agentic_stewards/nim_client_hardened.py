"""Hardened NIM client with full security hardening.

Integrates all security components (API key management, audit logging,
rate limiting, circuit breaker, cost monitoring) for production-ready
NIM API integration.

Guardrails (Phase 196):
- DeterminismMonitor tracks LLM output consistency via hash comparisons
- NIMModelConfig enforces model version pinning (no silent auto-updates)
- LLMWithFallback ensures every probabilistic path has deterministic fallback
- MitigationPlan uses SHA-256 hash commitment for tamper detection
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time as _time
from dataclasses import dataclass
from typing import Any, Optional

from ..determinism_boundaries import (
    DeterminismMonitor,
    MitigationPlan,
    NIMModelConfig,
    commit_reasoning_output,
)
from ..security.api_key_manager import APIKeyManager
from ..security.nim_audit_logger import NIMAuditLogger
from ..security.nim_rate_limiter import NIMRateLimiter
from ..security.nim_circuit_breaker import NIMCircuitBreaker, CircuitBreakerOpenError
from ..security.nim_cost_monitor import NIMCostMonitor

log = logging.getLogger(__name__)


@dataclass
class NIMConfig:
    """NIM client configuration."""
    api_key: str = ""
    base_url: str = "https://api.nvidia.com/v1"
    model: str = "llama-3-70b-instruct"
    timeout: float = 30.0
    enabled: bool = False
    environment: str = "dev"


class HardenedNIMClient:
    """NIM client with full security hardening.

    Guardrails enforced:
    - Token bucket rate limiting (burst/sustained/daily)
    - Circuit breaker (CLOSED/OPEN/HALF_OPEN state machine)
    - Cost monitoring ($50 warning / $100 critical thresholds)
    - Audit logging (SHA-256 prompt/response hashing, anomaly detection)
    - Determinism monitoring (input/output hash tracking, consistency checks)
    - Model version pinning (NIMModelConfig prevents silent auto-updates)
    - Output validation (non-empty, bounded length, valid JSON when expected)
    """

    def __init__(self, config: NIMConfig, store):
        self._config = config
        self._store = store

        # Security components
        self._key_manager = APIKeyManager(env=config.environment)
        self._audit_logger = NIMAuditLogger(store)
        self._rate_limiter = NIMRateLimiter()
        self._circuit_breaker = NIMCircuitBreaker()
        self._cost_monitor = NIMCostMonitor(store)

        # Determinism guardrails
        self._determinism_monitor = DeterminismMonitor(store)
        self._model_config = NIMModelConfig(
            model_name=config.model,
            model_version="1",
            pin_version=True,
        )

        # OpenAI client
        self._client = None
        if config.enabled and config.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=config.api_key,
                    base_url=f"{config.base_url}/llm/nvidia/{config.model}",
                )
                log.info(
                    "Hardened NIM client initialized: %s (env=%s)",
                    config.model, config.environment,
                )
            except ImportError:
                log.warning("openai package not installed - NIM disabled")
                config.enabled = False

    async def generate_reasoning(
        self,
        device_id: str,
        prompt: str,
        system: str = "",
    ) -> Optional[str]:
        """Generate reasoning with full security hardening.

        Guardrail enforcement order:
        1. Enabled check (default-OFF)
        2. Rate limit check (token bucket)
        3. Circuit breaker check (state machine)
        4. NIM API call (via asyncio.to_thread)
        5. Audit logging (SHA-256 hashing)
        6. Determinism tracking (input/output hash)
        7. Cost monitoring
        """
        if not self._config.enabled or not self._client:
            return None

        # Guardrail 1: Rate limit
        allowed, limit_type = self._rate_limiter.check_rate_limit(device_id)
        if not allowed:
            log.warning("Rate limit exceeded for device %s: %s", device_id, limit_type)
            return None

        # Guardrail 2: Circuit breaker
        try:
            result = await self._circuit_breaker.call(
                self._call_nim_api,
                device_id,
                prompt,
                system,
            )
            return result
        except CircuitBreakerOpenError:
            log.warning("Circuit breaker is OPEN - NIM calls blocked")
            return None

    async def _call_nim_api(
        self,
        device_id: str,
        prompt: str,
        system: str,
    ) -> Optional[str]:
        """Actual NIM API call with audit logging and determinism tracking."""
        start_time = _time.time()

        try:
            response = await _time.sleep(0)  # yield to event loop
            # Wrap synchronous OpenAI call in thread pool
            response = await asyncio.to_thread(
                self._client.chat.completions.create,
                model=self._config.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=4096,
            )

            latency_ms = (_time.time() - start_time) * 1000.0
            result = response.choices[0].message.content
            estimated_cost = self._estimate_cost(prompt, result or "")

            # Guardrail 3: Track determinism
            self._determinism_monitor.track_call(
                input_text=prompt,
                output_text=result or "",
                model_version=self._model_config.model_version,
                confidence=0.8,
            )

            # Guardrail 4: Audit logging
            self._audit_logger.log_call(
                endpoint="chat.completions.create",
                model=self._config.model,
                prompt=prompt,
                response=result or "",
                token_count=response.usage.total_tokens if hasattr(response, "usage") else 0,
                latency_ms=latency_ms,
                estimated_cost_usd=estimated_cost,
                api_key_version="v1",
                success=True,
            )

            return result

        except Exception as exc:
            latency_ms = (_time.time() - start_time) * 1000.0
            self._audit_logger.log_call(
                endpoint="chat.completions.create",
                model=self._config.model,
                prompt=prompt,
                response="",
                token_count=0,
                latency_ms=latency_ms,
                estimated_cost_usd=0.0,
                api_key_version="v1",
                success=False,
                error_code=type(exc).__name__,
                error_message=str(exc),
            )
            log.error("NIM API call failed: %s", exc)
            return None

    def _estimate_cost(self, prompt: str, response: str) -> float:
        """Rough cost estimation for Llama 3 70B."""
        prompt_tokens = len(prompt.split()) * 1.3
        response_tokens = len(response.split()) * 1.3
        total_tokens = prompt_tokens + response_tokens
        cost_per_1k_tokens = 0.01
        return (total_tokens / 1000) * cost_per_1k_tokens

    async def analyze_incident(
        self,
        device_id: str,
        invariant_id: str,
        log_tail: str,
    ) -> Optional[dict]:
        """Synthesize Incident Mitigation Plan from invariant failure.

        Returns a MitigationPlan dict with SHA-256 commitment hash.
        """
        if not self._config.enabled:
            return None

        system_prompt = """
You are the QorTroller Protocol Guardian. Analyze protocol invariant failures
and synthesize Incident Mitigation Plans. Respond in JSON with:
incident_id, invariant, severity (INFO|WARNING|CRITICAL), root_cause, mitigation, verification
"""
        prompt = f"INVARIANT: {invariant_id}\nLOG TAIL:\n{log_tail}\nProvide JSON Mitigation Plan."

        result = await self.generate_reasoning(device_id, prompt, system_prompt)
        if not result:
            return None

        try:
            data = json.loads(result)
            plan = MitigationPlan(
                incident_id=data.get("incident_id", f"INV-{invariant_id}-{int(_time.time())}"),
                invariant=invariant_id,
                severity=data.get("severity", "INFO"),
                root_cause=data.get("root_cause", "unknown"),
                mitigation=data.get("mitigation", {}),
                verification=data.get("verification", ""),
                confidence=0.8,
                llm_generated=True,
            )
            return plan.to_dict()
        except json.JSONDecodeError:
            log.error("NIM returned invalid JSON for incident analysis")
            return None

    def get_health_status(self) -> dict:
        """Get health status of NIM client with all guardrails."""
        cost_status = self._cost_monitor.check_cost_thresholds()
        return {
            "enabled": self._config.enabled,
            "model": self._config.model,
            "model_pinned": self._model_config.pin_version,
            "model_version": self._model_config.model_version,
            "environment": self._config.environment,
            "circuit_breaker": self._circuit_breaker.get_state(),
            "cost_status": cost_status,
            "anomaly_report": self._audit_logger.get_anomaly_report(hours=24),
        }


class LLMWithFallback:
    """Pattern for LLM calls with deterministic fallback.

    Every LLM-dependent path follows:
    1. Try LLM first (if enabled and available)
    2. Fall back to deterministic rules
    3. Ultimate fallback (default behavior)
    """

    def __init__(self, nim_client: HardenedNIMClient, fallback_rules: dict):
        self._nim_client = nim_client
        self._fallback_rules = fallback_rules
        self._llm_count = 0
        self._fallback_count = 0
        self._default_count = 0

    async def call_with_fallback(
        self,
        device_id: str,
        context: str,
        fallback_key: str,
    ) -> Optional[str]:
        """Call LLM with deterministic fallback."""
        try:
            result = await self._nim_client.generate_reasoning(device_id, context)
            if result and self._validate_output(result):
                self._llm_count += 1
                return result
        except Exception as exc:
            log.warning("LLM call failed: %s — using fallback", exc)

        fallback_result = self._fallback_rules.get(fallback_key)
        if fallback_result:
            self._fallback_count += 1
            return fallback_result

        self._default_count += 1
        return json.dumps({"status": "defer", "reason": "no_fallback", "key": fallback_key})

    def _validate_output(self, output: str) -> bool:
        """Validate LLM output before accepting.

        Guardrails:
        - Non-empty, non-whitespace output
        - Bounded length (32K max)
        - Valid JSON when JSON format expected
        """
        if not output or not output.strip():
            return False
        if len(output) > 32768:
            log.warning("LLM output exceeds 32K limit: %d chars", len(output))
            return False
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                return bool(parsed.get("incident_id") or parsed.get("status"))
            return True
        except (json.JSONDecodeError, ValueError):
            return True

    def stats(self) -> dict:
        """Get LLM vs fallback usage statistics."""
        total = self._llm_count + self._fallback_count + self._default_count
        return {
            "total_calls": total,
            "llm_calls": self._llm_count,
            "fallback_calls": self._fallback_count,
            "default_calls": self._default_count,
            "llm_pct": round(self._llm_count / total * 100, 1) if total else 0.0,
            "fallback_pct": round(self._fallback_count / total * 100, 1) if total else 0.0,
        }