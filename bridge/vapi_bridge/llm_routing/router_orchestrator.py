"""Router orchestration for LLM provider failover with provenance tracking.

Implements QS (QuickSilver) + LOCAL (NIM) failover with comprehensive
provenance tracking and health monitoring.
"""
from __future__ import annotations

import time
import json
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

log = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Available LLM providers."""
    QUICKSILVER = "quicksilver"
    LOCAL_NIM = "local_nim"
    FALLBACK = "fallback"


@dataclass
class RouterConfig:
    """Configuration for LLM router."""
    # Provider priorities
    primary_provider: LLMProvider = LLMProvider.QUICKSILVER
    secondary_provider: LLMProvider = LLMProvider.LOCAL_NIM
    
    # Failover configuration
    auto_failover_enabled: bool = True
    max_failures_before_failover: int = 3
    failback_after_seconds: int = 300  # 5 minutes
    
    # Provenance tracking
    enable_provenance: bool = True
    provenance_retention_days: int = 30
    
    # Health monitoring
    health_check_interval_seconds: int = 60
    provider_timeout_seconds: int = 30


@dataclass
class ProvenanceRecord:
    """Provenance record for an LLM call."""
    call_id: str
    timestamp: float
    provider: LLMProvider
    model: str
    prompt_hash: str
    response_hash: str
    token_count: int
    latency_ms: float
    success: bool
    error_message: Optional[str] = None
    fallback_triggered: bool = False
    fallback_from: Optional[LLMProvider] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouterResult:
    """Result from LLM router call."""
    content: Optional[str]
    provider: LLMProvider
    provenance: ProvenanceRecord
    success: bool
    error: Optional[str] = None


class LLMRouter:
    """Orchestrates LLM provider failover with provenance tracking."""
    
    def __init__(self, config: RouterConfig, store):
        self._config = config
        self._store = store
        
        # Provider clients
        self._qs_client = None
        self._local_client = None
        
        # Provider health tracking
        self._provider_health: Dict[LLMProvider, Dict[str, Any]] = {
            LLMProvider.QUICKSILVER: {"healthy": True, "failures": 0, "last_failure": 0.0},
            LLMProvider.LOCAL_NIM: {"healthy": True, "failures": 0, "last_failure": 0.0},
        }
        
        # Provenance tracking
        self._provenance_records: List[ProvenanceRecord] = []
        
        # Initialize providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize LLM provider clients."""
        try:
            from .qs_client import QuickSilverClient
            self._qs_client = QuickSilverClient()
            log.info("QuickSilver client initialized")
        except Exception as e:
            log.warning(f"QuickSilver client initialization failed: {e}")
            self._provider_health[LLMProvider.QUICKSILVER]["healthy"] = False
        
        try:
            from .local_client import LocalLLMClient
            self._local_client = LocalLLMClient()
            log.info("Local NIM client initialized")
        except Exception as e:
            log.warning(f"Local NIM client initialization failed: {e}")
            self._provider_health[LLMProvider.LOCAL_NIM]["healthy"] = False
    
    async def route_request(
        self,
        prompt: str,
        system_prompt: str = "",
        fallback_content: Optional[str] = None
    ) -> RouterResult:
        """Route LLM request to available provider with failover."""
        
        call_id = self._generate_call_id()
        timestamp = time.time()
        
        # Try primary provider first
        provider = self._config.primary_provider
        result = await self._try_provider(
            call_id, provider, prompt, system_prompt, timestamp
        )
        
        # Failover to secondary if primary failed
        if not result.success and self._config.auto_failover_enabled:
            self._record_provider_failure(provider)
            
            if self._should_failover(provider):
                secondary = self._config.secondary_provider
                log.warning(f"Failover from {provider.value} to {secondary.value}")
                
                result = await self._try_provider(
                    call_id, secondary, prompt, system_prompt, timestamp,
                    fallback_from=provider
                )
                
                # If secondary succeeds, update provenance
                if result.success:
                    result.provenance.fallback_triggered = True
                    result.provenance.fallback_from = provider
        
        # Ultimate fallback if both providers failed
        if not result.success and fallback_content is not None:
            log.warning("All providers failed, using fallback content")
            
            result = RouterResult(
                content=fallback_content,
                provider=LLMProvider.FALLBACK,
                provenance=self._create_fallback_provenance(call_id, timestamp),
                success=True,
                error=None
            )
        
        # Store provenance record
        if self._config.enable_provenance:
            self._store_provenance(result.provenance)
        
        return result
    
    async def _try_provider(
        self,
        call_id: str,
        provider: LLMProvider,
        prompt: str,
        system_prompt: str,
        timestamp: float,
        fallback_from: Optional[LLMProvider] = None
    ) -> RouterResult:
        """Try a specific provider for the request."""
        
        if not self._is_provider_healthy(provider):
            return RouterResult(
                content=None,
                provider=provider,
                provenance=self._create_error_provenance(call_id, provider, timestamp, "Provider unhealthy"),
                success=False,
                error="Provider unhealthy"
            )
        
        try:
            start_time = time.time()
            
            if provider == LLMProvider.QUICKSILVER and self._qs_client:
                content = await self._qs_client.generate(prompt, system_prompt)
            elif provider == LLMProvider.LOCAL_NIM and self._local_client:
                content = await self._local_client.generate(prompt, system_prompt)
            else:
                raise Exception(f"Provider {provider.value} not available")
            
            latency_ms = (time.time() - start_time) * 1000.0
            
            # Create provenance record
            provenance = ProvenanceRecord(
                call_id=call_id,
                timestamp=timestamp,
                provider=provider,
                model=self._get_provider_model(provider),
                prompt_hash=self._hash_content(prompt),
                response_hash=self._hash_content(content or ""),
                token_count=self._estimate_tokens(prompt, content or ""),
                latency_ms=latency_ms,
                success=True,
                fallback_triggered=fallback_from is not None,
                fallback_from=fallback_from
            )
            
            return RouterResult(
                content=content,
                provider=provider,
                provenance=provenance,
                success=True,
                error=None
            )
            
        except Exception as e:
            log.error(f"Provider {provider.value} failed: {e}")
            
            return RouterResult(
                content=None,
                provider=provider,
                provenance=self._create_error_provenance(call_id, provider, timestamp, str(e)),
                success=False,
                error=str(e)
            )
    
    def _is_provider_healthy(self, provider: LLMProvider) -> bool:
        """Check if a provider is healthy."""
        health = self._provider_health.get(provider, {})
        return health.get("healthy", False)
    
    def _should_failover(self, provider: LLMProvider) -> bool:
        """Determine if failover should be triggered."""
        health = self._provider_health.get(provider, {})
        
        # Failover if failure threshold exceeded
        if health.get("failures", 0) >= self._config.max_failures_before_failover:
            return True
        
        # Failover if provider marked unhealthy
        if not health.get("healthy", True):
            return True
        
        return False
    
    def _record_provider_failure(self, provider: LLMProvider):
        """Record a provider failure."""
        if provider in self._provider_health:
            self._provider_health[provider]["failures"] += 1
            self._provider_health[provider]["last_failure"] = time.time()
            
            # Mark unhealthy if threshold exceeded
            if self._provider_health[provider]["failures"] >= self._config.max_failures_before_failover:
                self._provider_health[provider]["healthy"] = False
                log.warning(f"Provider {provider.value} marked unhealthy")
    
    def _generate_call_id(self) -> str:
        """Generate unique call ID."""
        import uuid
        return f"llm_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    def _hash_content(self, content: str) -> str:
        """Hash content for provenance."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """Estimate token count for prompt and response."""
        # Rough estimation: 1 token ≈ 4 characters
        return len(prompt) // 4 + len(response) // 4
    
    def _get_provider_model(self, provider: LLMProvider) -> str:
        """Get model name for provider."""
        if provider == LLMProvider.QUICKSILVER:
            return "deepseek-v4-flash"
        elif provider == LLMProvider.LOCAL_NIM:
            return "llama-3-70b-instruct"
        else:
            return "unknown"
    
    def _create_error_provenance(
        self,
        call_id: str,
        provider: LLMProvider,
        timestamp: float,
        error_message: str
    ) -> ProvenanceRecord:
        """Create provenance record for failed call."""
        return ProvenanceRecord(
            call_id=call_id,
            timestamp=timestamp,
            provider=provider,
            model=self._get_provider_model(provider),
            prompt_hash="",
            response_hash="",
            token_count=0,
            latency_ms=0.0,
            success=False,
            error_message=error_message
        )
    
    def _create_fallback_provenance(
        self,
        call_id: str,
        timestamp: float
    ) -> ProvenanceRecord:
        """Create provenance record for fallback content."""
        return ProvenanceRecord(
            call_id=call_id,
            timestamp=timestamp,
            provider=LLMProvider.FALLBACK,
            model="fallback",
            prompt_hash="",
            response_hash=self._hash_content("fallback"),
            token_count=0,
            latency_ms=0.0,
            success=True
        )
    
    def _store_provenance(self, provenance: ProvenanceRecord):
        """Store provenance record in database."""
        try:
            self._store.insert_llm_provenance(provenance)
        except Exception as e:
            log.error(f"Failed to store provenance record: {e}")
    
    def get_provider_health(self) -> Dict[str, Any]:
        """Get health status of all providers."""
        return {
            provider.value: health
            for provider, health in self._provider_health.items()
        }
    
    def get_provenance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get provenance summary for recent calls."""
        cutoff = time.time() - (hours * 3600)
        
        recent_records = [
            p for p in self._provenance_records
            if p.timestamp >= cutoff
        ]
        
        if not recent_records:
            return {"period_hours": hours, "total_calls": 0}
        
        provider_counts = {}
        success_count = 0
        total_latency = 0.0
        
        for record in recent_records:
            provider_counts[record.provider.value] = provider_counts.get(record.provider.value, 0) + 1
            if record.success:
                success_count += 1
                total_latency += record.latency_ms
        
        return {
            "period_hours": hours,
            "total_calls": len(recent_records),
            "success_rate": success_count / len(recent_records) if recent_records else 0.0,
            "avg_latency_ms": total_latency / success_count if success_count > 0 else 0.0,
            "provider_distribution": provider_counts
        }