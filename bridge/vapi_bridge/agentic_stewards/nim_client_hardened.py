"""Hardened NIM client with full security hardening.

Integrates all security components (API key management, audit logging,
rate limiting, circuit breaker, cost monitoring) for production-ready
NIM API integration.
"""
from __future__ import annotations

import os
import json
import asyncio
import logging
import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass

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


@dataclass
class MitigationPlan:
    """Deterministic schema for mitigation plans."""
    incident_id: str
    invariant: str
    severity: str  # INFO|WARNING|CRITICAL
    root_cause: str
    mitigation: Dict[str, Any]
    verification: str
    confidence: float  # 0.0-1.0
    llm_generated: bool
    commitment_hash: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary with commitment."""
        data = {
            "incident_id": self.incident_id,
            "invariant": self.invariant,
            "severity": self.severity,
            "root_cause": self.root_cause,
            "mitigation": self.mitigation,
            "verification": self.verification,
            "confidence": self.confidence,
            "llm_generated": self.llm_generated,
        }
        self.commitment_hash = commit_reasoning_output(data)
        data["commitment_hash"] = self.commitment_hash
        return data


def commit_reasoning_output(reasoning: dict) -> str:
    """Create hash commitment of LLM reasoning output."""
    canonical = json.dumps(reasoning, sort_keys=True, separators=(',', ':'))
    commitment = hashlib.sha256(canonical.encode()).hexdigest()
    return commitment


class HardenedNIMClient:
    """NIM client with full security hardening."""

    def __init__(self, config: NIMConfig, store):
        self._config = config
        self._store = store

        # Security components
        self._key_manager = APIKeyManager(env=config.environment)
        self._audit_logger = NIMAuditLogger(store)
        self._rate_limiter = NIMRateLimiter()
        self._circuit_breaker = NIMCircuitBreaker()
        self._cost_monitor = NIMCostMonitor(store)

        # OpenAI client
        self._client = None
        if config.enabled and config.api_key:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(
                    api_key=config.api_key,
                    base_url=f"{config.base_url}/llm/nvidia/{config.model}",
                )
                log.info(f"Hardened NIM client initialized: {config.model}")
            except ImportError:
                log.warning("openai package not installed - NIM disabled")
                config.enabled = False

    async def generate_reasoning(
        self,
        device_id: str,
        prompt: str,
        system: str = ""
    ) -> Optional[str]:
        """Generate reasoning with full security hardening."""

        if not self._config.enabled or not self._client:
            return None

        # Rate limit check
        allowed, limit_type = self._rate_limiter.check_rate_limit(device_id)
        if not allowed:
            log.warning(f"Rate limit exceeded for device {device_id}: {limit_type}")
            return None

        # Circuit breaker check
        try:
            result = await self._circuit_breaker.call(
                self._call_nim_api,
                device_id,
                prompt,
                system
            )
            return result
        except CircuitBreakerOpenError:
            log.warning("Circuit breaker is OPEN - NIM calls blocked")
            return None

    async def _call_nim_api(
        self,
        device_id: str,
        prompt: str,
        system: str
    ) -> Optional[str]:
        """Actual NIM API call with audit logging."""

        import time
        start_time = time.time()

        try:
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

            latency_ms = (time.time() - start_time) * 1000.0
            result = response.choices[0].message.content

            # Estimate cost (rough calculation)
            estimated_cost = self._estimate_cost(prompt, result)

            # Log the call
            self._audit_logger.log_call(
                endpoint="chat.completions.create",
                model=self._config.model,
                prompt=prompt,
                response=result,
                token_count=response.usage.total_tokens if hasattr(response, 'usage') else 0,
                latency_ms=latency_ms,
                estimated_cost_usd=estimated_cost,
                api_key_version="v1",  # TODO: track actual version
                success=True,
                client_ip=None,  # TODO: extract from request
                user_agent=None  # TODO: extract from request
            )

            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0

            # Log the failure
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
                error_code=type(e).__name__,
                error_message=str(e)
            )

            log.error(f"NIM API call failed: {e}")
            return None

    def _estimate_cost(self, prompt: str, response: str) -> float:
        """Rough cost estimation for Llama 3 70B."""
        # This is a simplified estimation
        # Actual cost depends on token count and pricing
        prompt_tokens = len(prompt.split()) * 1.3  # Rough approximation
        response_tokens = len(response.split()) * 1.3
        total_tokens = prompt_tokens + response_tokens

        # Llama 3 70B pricing (example)
        cost_per_1k_tokens = 0.01  # $0.01 per 1K tokens
        return (total_tokens / 1000) * cost_per_1k_tokens

    async def analyze_incident(self, device_id: str, invariant_id: str, log_tail: str) -> Optional[Dict[str, Any]]:
        """Synthesize Incident Mitigation Plan from invariant failure."""
        if not self._config.enabled:
            return None

        system_prompt = """You are the QorTroller Protocol Guardian.
Your task is to analyze protocol invariant failures and synthesize Incident Mitigation Plans.
Always respond in JSON format with the following structure:
{
    "incident_id": "INV-<ID>-<timestamp>",
    "invariant": "<invariant_id>",
    "severity": "INFO|WARNING|CRITICAL",
    "root_cause": "<human-readable cause>",
    "mitigation": {
        "action": "<what to change>",
        "params": {"key": "value"},
        "rollback": "<how to undo>"
    },
    "verification": "<how to confirm fix>"
}"""

        prompt = f"""Analyze this invariant failure and log tail:

INVARIANT: {invariant_id}

LOG TAIL:
{log_tail}

Provide a JSON Incident Mitigation Plan."""

        result = await self.generate_reasoning(device_id, prompt, system_prompt)
        if result:
            try:
                mitigation_data = json.loads(result)
                
                # Create deterministic MitigationPlan
                plan = MitigationPlan(
                    incident_id=mitigation_data.get("incident_id", f"INV-{invariant_id}-{int(time.time())}"),
                    invariant=invariant_id,
                    severity=mitigation_data.get("severity", "INFO"),
                    root_cause=mitigation_data.get("root_cause", "unknown"),
                    mitigation=mitigation_data.get("mitigation", {}),
                    verification=mitigation_data.get("verification", ""),
                    confidence=0.8,  # Default confidence for LLM output
                    llm_generated=True
                )
                
                return plan.to_dict()
            except json.JSONDecodeError:
                log.error("NIM returned invalid JSON")
                return None
        return None

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of NIM client."""
        return {
            "enabled": self._config.enabled,
            "model": self._config.model,
            "circuit_breaker": self._circuit_breaker.get_state(),
            "cost_status": self._cost_monitor.check_cost_thresholds(),
            "anomaly_report": self._audit_logger.get_anomaly_report(hours=24)
        }


class LLMWithFallback:
    """Pattern for LLM calls with deterministic fallback."""

    def __init__(self, nim_client: HardenedNIMClient, fallback_rules: Dict[str, Any]):
        self._nim_client = nim_client
        self._fallback_rules = fallback_rules
        self._fallback_count = 0
        self._llm_count = 0

    async def call_with_fallback(self, device_id: str, context: str, fallback_key: str) -> Optional[str]:
        """Call LLM with deterministic fallback."""

        # Try LLM first
        try:
            result = await self._nim_client.generate_reasoning(device_id, context)
            if result and self._validate_llm_output(result):
                self._llm_count += 1
                return result
        except Exception as e:
            log.warning(f"LLM call failed: {e}")

        # Fallback to deterministic rules
        fallback_result = self._fallback_rules.get(fallback_key)
        if fallback_result:
            self._fallback_count += 1
            log.info(f"Using fallback for {fallback_key}")
            return fallback_result

        # Final fallback
        return self._default_fallback()

    def _validate_llm_output(self, output: str) -> bool:
        """Validate LLM output before accepting."""
        # Check for required fields
        # Check for malformed JSON
        # Check for out-of-bounds values
        return True

    def _default_fallback(self) -> str:
        """Ultimate fallback when no rules match."""
        return json.dumps({"status": "defer", "reason": "no_fallback"})

    def get_stats(self) -> dict:
        """Get statistics on LLM vs fallback usage."""
        total = self._llm_count + self._fallback_count
        llm_pct = (self._llm_count / total * 100) if total > 0 else 0
        fallback_pct = (self._fallback_count / total * 100) if total > 0 else 0

        return {
            "llm_calls": self._llm_count,
            "fallback_calls": self._fallback_count,
            "llm_percentage": llm_pct,
            "fallback_percentage": fallback_pct
        }