# NIM Integration Security Hardening

**Document Version:** 1.0  
**Last Updated:** 2026-07-27  
**Status:** IMPLEMENTATION PLAN  

---

## Overview

This document specifies the security hardening requirements for NIM integration to address the sovereignty and security gaps identified in the impact assessment. All hardening measures must be implemented before NIM client wrapper deployment.

---

## 1. API Key Rotation Strategy

### 1.1 Key Lifecycle Management

**Key Generation:**
- Use cryptographically secure random generator (secrets.token_urlsafe)
- Minimum 32-byte entropy for API keys
- Separate keys per environment (dev/staging/prod)
- Key naming convention: `NIM_{ENV}_{PURPOSE}_{VERSION}`

**Key Rotation Schedule:**
- **Automatic rotation**: Every 90 days
- **Event-driven rotation**: On suspected compromise
- **Version tracking**: Maintain key version history (last 5 versions)
- **Grace period**: 7-day overlap during rotation

**Key Storage:**
- **Development**: Environment variables (accepted risk)
- **Staging**: Encrypted config file with file permissions 0600
- **Production**: Hardware security module (YubiHSM2) required

### 1.2 Key Rotation Implementation

```python
# bridge/vapi_bridge/security/api_key_manager.py

import os
import secrets
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict
from enum import Enum

log = logging.getLogger(__name__)

class KeyStatus(Enum):
    ACTIVE = "active"
    ROTATING = "rotating"
    REVOKED = "revoked"
    COMPROMISED = "compromised"

@dataclass
class APIKeyVersion:
    version: str
    key: str
    status: KeyStatus
    created_at: float
    expires_at: float
    last_used_at: Optional[float] = None

class APIKeyManager:
    """Manages API key lifecycle with automatic rotation."""
    
    def __init__(self, env: str = "prod"):
        self.env = env
        self.keys: Dict[str, APIKeyVersion] = {}
        self.rotation_interval_days = 90
        self.grace_period_days = 7
        
    def generate_key(self, purpose: str) -> str:
        """Generate a new API key with version tracking."""
        version = f"v{int(time.time())}"
        key = secrets.token_urlsafe(32)  # 32-byte entropy
        
        key_version = APIKeyVersion(
            version=version,
            key=key,
            status=KeyStatus.ACTIVE,
            created_at=time.time(),
            expires_at=time.time() + (self.rotation_interval_days * 86400)
        )
        
        key_id = f"NIM_{self.env.upper()}_{purpose.upper()}_{version}"
        self.keys[key_id] = key_version
        
        log.info(f"Generated new API key: {key_id}")
        return key_id
    
    def rotate_key(self, key_id: str) -> Optional[str]:
        """Rotate an existing key with grace period overlap."""
        if key_id not in self.keys:
            log.error(f"Key not found for rotation: {key_id}")
            return None
        
        old_key = self.keys[key_id]
        
        # Mark old key as rotating
        old_key.status = KeyStatus.ROTATING
        old_key.expires_at = time.time() + (self.grace_period_days * 86400)
        
        # Generate new key
        purpose = key_id.split("_")[2].lower()
        new_key_id = self.generate_key(purpose)
        
        log.info(f"Rotated key: {key_id} -> {new_key_id}")
        return new_key_id
    
    def revoke_key(self, key_id: str, reason: str = "manual") -> bool:
        """Immediately revoke a key."""
        if key_id not in self.keys:
            return False
        
        self.keys[key_id].status = KeyStatus.REVOKED
        log.warning(f"Revoked key: {key_id}, reason: {reason}")
        return True
    
    def get_active_key(self, purpose: str) -> Optional[str]:
        """Get the active key for a purpose."""
        # Find keys matching purpose
        matching_keys = [
            (k_id, k_v) for k_id, k_v in self.keys.items()
            if k_id.startswith(f"NIM_{self.env.upper()}_{purpose.upper()}")
        ]
        
        # Return active key
        for key_id, key_version in matching_keys:
            if key_version.status == KeyStatus.ACTIVE:
                if time.time() < key_version.expires_at:
                    return key_version.key
                else:
                    # Auto-expire
                    key_version.status = KeyStatus.REVOKED
        
        return None
    
    def check_rotation_needed(self) -> list:
        """Check which keys need rotation."""
        needs_rotation = []
        now = time.time()
        
        for key_id, key_version in self.keys.items():
            if key_version.status == KeyStatus.ACTIVE:
                # Rotate if 80% of lifetime elapsed
                lifetime = key_version.expires_at - key_version.created_at
                age = now - key_version.created_at
                if age > (lifetime * 0.8):
                    needs_rotation.append(key_id)
        
        return needs_rotation
```

### 1.3 Hardware-Bound Key Storage (YubiHSM2)

**Production Requirement:**
- YubiHSM2 for production API key storage
- Keys never leave HSM in plaintext
- HSM handles cryptographic operations

**Implementation:**
```python
# bridge/vapi_bridge/security/hsm_key_store.py

import logging
from typing import Optional

try:
    from yubihsm import YubiHsm
    from yubihsm.objects import AuthenticationKey, SymmetricKey
    YUBIHSM_AVAILABLE = True
except ImportError:
    YUBIHSM_AVAILABLE = False

log = logging.getLogger(__name__)

class HSMKeyStore:
    """YubiHSM2-backed key storage for production."""
    
    def __init__(self, device_url: str = "yubihsm://"):
        self.device_url = device_url
        self.session = None
        
        if not YUBIHSM_AVAILABLE:
            log.error("yubihsm package not available - HSM disabled")
            return
        
        try:
            self.hsm = YubiHsm.connect(device_url)
            log.info(f"Connected to YubiHSM2 at {device_url}")
        except Exception as e:
            log.error(f"Failed to connect to YubiHSM2: {e}")
    
    def store_key(self, key_id: str, api_key: str) -> bool:
        """Store API key in HSM."""
        if not YUBIHSM_AVAILABLE or self.hsm is None:
            log.error("HSM not available - cannot store key")
            return False
        
        try:
            # Create symmetric key in HSM
            key = SymmetricKey.create(
                self.session,
                key_id,
                0,  # domains
                SymmetricKey.ALGORITHM_AES256,
                api_key.encode()
            )
            log.info(f"Stored key in HSM: {key_id}")
            return True
        except Exception as e:
            log.error(f"Failed to store key in HSM: {e}")
            return False
    
    def retrieve_key(self, key_id: str) -> Optional[str]:
        """Retrieve API key from HSM."""
        if not YUBIHSM_AVAILABLE or self.hsm is None:
            log.error("HSM not available - cannot retrieve key")
            return None
        
        try:
            key = SymmetricKey.get(self.session, key_id)
            api_key = key.get_opaque().decode()
            return api_key
        except Exception as e:
            log.error(f"Failed to retrieve key from HSM: {e}")
            return None
```

---

## 2. Comprehensive Audit Logging

### 2.1 NIM Call Audit Schema

**Audit Log Table:**
```sql
CREATE TABLE nim_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,  -- UUID for each NIM call
    timestamp REAL NOT NULL,
    environment TEXT NOT NULL,  -- dev/staging/prod
    
    -- Request metadata
    endpoint TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,  -- SHA-256 of prompt
    prompt_length INTEGER NOT NULL,
    
    -- Response metadata
    response_hash TEXT NOT NULL,  -- SHA-256 of response
    response_length INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    
    -- Cost tracking
    estimated_cost_usd REAL NOT NULL,
    
    -- Security metadata
    api_key_version TEXT NOT NULL,
    client_ip TEXT,
    user_agent TEXT,
    
    -- Outcome
    success BOOLEAN NOT NULL,
    error_code TEXT,
    error_message TEXT,
    
    -- Anomaly detection
    anomaly_score REAL DEFAULT 0.0,
    anomaly_flags TEXT,  -- JSON array of anomaly flags
    
    INDEX idx_call_id (call_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_environment (environment),
    INDEX idx_anomaly_score (anomaly_score)
);
```

### 2.2 Audit Logger Implementation

```python
# bridge/vapi_bridge/security/nim_audit_logger.py

import json
import hashlib
import time
import logging
import uuid
from typing import Optional, Dict, Any
from dataclasses import dataclass

log = logging.getLogger(__name__)

@dataclass
class NIMCallMetadata:
    call_id: str
    timestamp: float
    environment: str
    endpoint: str
    model: str
    prompt_hash: str
    prompt_length: int
    response_hash: str
    response_length: int
    token_count: int
    latency_ms: float
    estimated_cost_usd: float
    api_key_version: str
    client_ip: Optional[str]
    user_agent: Optional[str]
    success: bool
    error_code: Optional[str]
    error_message: Optional[str]
    anomaly_score: float = 0.0
    anomaly_flags: Optional[str] = None

class NIMAuditLogger:
    """Comprehensive audit logging for NIM API calls."""
    
    def __init__(self, store):
        self._store = store
    
    def log_call(
        self,
        endpoint: str,
        model: str,
        prompt: str,
        response: str,
        token_count: int,
        latency_ms: float,
        estimated_cost_usd: float,
        api_key_version: str,
        success: bool,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Log a NIM API call with full metadata."""
        
        call_id = str(uuid.uuid4())
        timestamp = time.time()
        environment = self._get_environment()
        
        # Compute hashes for integrity
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        response_hash = hashlib.sha256(response.encode()).hexdigest()
        
        # Detect anomalies
        anomaly_score, anomaly_flags = self._detect_anomalies(
            prompt_length=len(prompt),
            response_length=len(response),
            token_count=token_count,
            latency_ms=latency_ms,
            estimated_cost_usd=estimated_cost_usd
        )
        
        metadata = NIMCallMetadata(
            call_id=call_id,
            timestamp=timestamp,
            environment=environment,
            endpoint=endpoint,
            model=model,
            prompt_hash=prompt_hash,
            prompt_length=len(prompt),
            response_hash=response_hash,
            response_length=len(response),
            token_count=token_count,
            latency_ms=latency_ms,
            estimated_cost_usd=estimated_cost_usd,
            api_key_version=api_key_version,
            client_ip=client_ip,
            user_agent=user_agent,
            success=success,
            error_code=error_code,
            error_message=error_message,
            anomaly_score=anomaly_score,
            anomaly_flags=json.dumps(anomaly_flags) if anomaly_flags else None
        )
        
        # Store in database
        self._store.insert_nim_audit_log(metadata)
        
        # Log high-severity anomalies
        if anomaly_score > 0.7:
            log.warning(
                f"High-severity anomaly detected for NIM call {call_id}: "
                f"score={anomaly_score:.2f}, flags={anomaly_flags}"
            )
        
        return call_id
    
    def _detect_anomalies(
        self,
        prompt_length: int,
        response_length: int,
        token_count: int,
        latency_ms: float,
        estimated_cost_usd: float
    ) -> tuple[float, list]:
        """Detect anomalous patterns in NIM calls."""
        anomalies = []
        score = 0.0
        
        # Anomaly 1: Unusually large prompt
        if prompt_length > 10000:
            anomalies.append("large_prompt")
            score += 0.3
        
        # Anomaly 2: Unusually high token count
        if token_count > 4000:
            anomalies.append("high_token_count")
            score += 0.3
        
        # Anomaly 3: Unusual latency
        if latency_ms > 10000:  # > 10 seconds
            anomalies.append("high_latency")
            score += 0.2
        
        # Anomaly 4: Unusual cost
        if estimated_cost_usd > 0.10:  # > $0.10 per call
            anomalies.append("high_cost")
            score += 0.2
        
        return min(score, 1.0), anomalies
    
    def _get_environment(self) -> str:
        """Determine current environment."""
        import os
        env = os.environ.get("QORTROLLER_ENV", "dev")
        return env
    
    def get_anomaly_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate anomaly report for the last N hours."""
        cutoff = time.time() - (hours * 3600)
        
        with self._store._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM nim_audit_log "
                "WHERE timestamp >= ? AND anomaly_score > 0.5 "
                "ORDER BY anomaly_score DESC",
                (cutoff,)
            ).fetchall()
        
        return {
            "period_hours": hours,
            "high_anomaly_count": len(rows),
            "anomalies": [dict(row) for row in rows]
        }
```

---

## 3. Rate Limiting and Anomaly Detection

### 3.1 Rate Limiting Strategy

**Rate Limits (Per Device):**
- **Burst limit**: 10 calls per minute
- **Sustained limit**: 100 calls per hour
- **Daily limit**: 1000 calls per day
- **Fleet limit**: 10,000 calls per day across all devices

**Rate Limit Implementation:**
```python
# bridge/vapi_bridge/security/nim_rate_limiter.py

import time
import logging
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)

@dataclass
class RateLimitRule:
    window_seconds: int
    max_calls: int

class NIMRateLimiter:
    """Token bucket rate limiter for NIM API calls."""
    
    def __init__(self):
        # Per-device rate tracking
        self._device_calls: defaultdict[str, list] = defaultdict(list)
        
        # Rate limit rules
        self._rules = {
            "burst": RateLimitRule(window_seconds=60, max_calls=10),
            "sustained": RateLimitRule(window_seconds=3600, max_calls=100),
            "daily": RateLimitRule(window_seconds=86400, max_calls=1000),
        }
        
        # Fleet-wide tracking
        self._fleet_calls: list = []
        self._fleet_limit = 10000  # per day
    
    def check_rate_limit(self, device_id: str) -> tuple[bool, Optional[str]]:
        """Check if a device is within rate limits."""
        now = time.time()
        
        # Check per-device limits
        for rule_name, rule in self._rules.items():
            # Clean old calls
            self._device_calls[device_id] = [
                ts for ts in self._device_calls[device_id]
                if now - ts < rule.window_seconds
            ]
            
            # Check limit
            if len(self._device_calls[device_id]) >= rule.max_calls:
                log.warning(
                    f"Rate limit exceeded for device {device_id}: "
                    f"{rule_name} ({len(self._device_calls[device_id])}/{rule.max_calls})"
                )
                return False, rule_name
        
        # Check fleet-wide limit
        self._fleet_calls = [ts for ts in self._fleet_calls if now - ts < 86400]
        if len(self._fleet_calls) >= self._fleet_limit:
            log.warning(f"Fleet-wide rate limit exceeded: {len(self._fleet_calls)}/{self._fleet_limit}")
            return False, "fleet"
        
        # Record this call
        self._device_calls[device_id].append(now)
        self._fleet_calls.append(now)
        
        return True, None
    
    def get_device_stats(self, device_id: str) -> dict:
        """Get rate limit statistics for a device."""
        now = time.time()
        stats = {}
        
        for rule_name, rule in self._rules.items():
            recent_calls = [
                ts for ts in self._device_calls[device_id]
                if now - ts < rule.window_seconds
            ]
            stats[rule_name] = {
                "calls": len(recent_calls),
                "limit": rule.max_calls,
                "window_seconds": rule.window_seconds
            }
        
        return stats
```

### 3.2 Cost Monitoring and Alerts

**Cost Tracking:**
```python
# bridge/vapi_bridge/security/nim_cost_monitor.py

import time
import logging
from typing import Dict, Optional
from dataclasses import dataclass

log = logging.getLogger(__name__)

@dataclass
class CostThreshold:
    warning_usd: float
    critical_usd: float
    window_hours: int

class NIMCostMonitor:
    """Monitor and alert on NIM API costs."""
    
    def __init__(self, store):
        self._store = store
        self._thresholds = CostThreshold(
            warning_usd=50.0,    # $50 warning
            critical_usd=100.0,  # $100 critical
            window_hours=24      # 24-hour window
        )
    
    def check_cost_thresholds(self) -> Dict[str, Any]:
        """Check if cost thresholds are exceeded."""
        cutoff = time.time() - (self._thresholds.window_hours * 3600)
        
        with self._store._conn() as conn:
            row = conn.execute(
                "SELECT SUM(estimated_cost_usd) as total_cost, "
                "COUNT(*) as call_count "
                "FROM nim_audit_log "
                "WHERE timestamp >= ?",
                (cutoff,)
            ).fetchone()
        
        total_cost = float(row["total_cost"] or 0.0)
        call_count = int(row["call_count"] or 0)
        
        status = "normal"
        if total_cost >= self._thresholds.critical_usd:
            status = "critical"
            log.critical(
                f"NIM cost critical threshold exceeded: "
                f"${total_cost:.2f} > ${self._thresholds.critical_usd:.2f}"
            )
        elif total_cost >= self._thresholds.warning_usd:
            status = "warning"
            log.warning(
                f"NIM cost warning threshold exceeded: "
                f"${total_cost:.2f} > ${self._thresholds.warning_usd:.2f}"
            )
        
        return {
            "window_hours": self._thresholds.window_hours,
            "total_cost_usd": total_cost,
            "call_count": call_count,
            "status": status,
            "warning_threshold_usd": self._thresholds.warning_usd,
            "critical_threshold_usd": self._thresholds.critical_usd
        }
```

---

## 4. Circuit Breaker Pattern

### 4.1 Circuit Breaker Implementation

```python
# bridge/vapi_bridge/security/nim_circuit_breaker.py

import time
import logging
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Failures before opening
    timeout_seconds: int = 60       # How long to stay open
    half_open_max_calls: int = 3   # Test calls in half-open

class NIMCircuitBreaker:
    """Circuit breaker for NIM API calls."""
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_call_count = 0
    
    def call(self, func: Callable, *args, **kwargs) -> any:
        """Execute a call through the circuit breaker."""
        
        if self._state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if time.time() - self._last_failure_time > self._config.timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_call_count = 0
                log.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN (since {self._last_failure_time})"
                )
        
        try:
            result = func(*args, **kwargs)
            
            # Success handling
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_call_count += 1
                if self._half_open_call_count >= self._config.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    log.info("Circuit breaker transitioning to CLOSED")
            else:
                self._failure_count = 0
            
            return result
            
        except Exception as e:
            # Failure handling
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._failure_count >= self._config.failure_threshold:
                self._state = CircuitState.OPEN
                log.error(
                    f"Circuit breaker transitioning to OPEN "
                    f"({self._failure_count} failures)"
                )
            
            raise
    
    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
            "half_open_call_count": self._half_open_call_count
        }

class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass
```

---

## 5. Integration with NIM Client

### 5.1 Hardened NIM Client Wrapper

```python
# bridge/vapi_bridge/agentic_stewards/nim_client_hardened.py

import os
import json
import asyncio
import logging
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
    api_key: str = ""
    base_url: str = "https://api.nvidia.com/v1"
    model: str = "llama-3-70b-instruct"
    timeout: float = 30.0
    enabled: bool = False
    environment: str = "dev"

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
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of NIM client."""
        return {
            "enabled": self._config.enabled,
            "model": self._config.model,
            "circuit_breaker": self._circuit_breaker.get_state(),
            "cost_status": self._cost_monitor.check_cost_thresholds(),
            "anomaly_report": self._audit_logger.get_anomaly_report(hours=24)
        }
```

---

## Implementation Checklist

### Phase 1: Foundation (Week 1)
- [x] Implement APIKeyManager with rotation logic
- [x] Implement NIMAuditLogger with database schema
- [x] Implement NIMRateLimiter with token bucket
- [x] Implement NIMCircuitBreaker with state machine
- [x] Implement NIMCostMonitor with threshold checking

### Phase 2: Integration (Week 2)
- [x] Integrate security components into HardenedNIMClient
- [x] Add database migration for nim_audit_log table
- [x] Add environment configuration for security settings
- [x] Add health check endpoints for security components

### Phase 3: Testing (Week 3)
- [ ] Unit tests for all security components
- [ ] Integration tests for rate limiting
- [ ] Circuit breaker failure scenario tests
- [ ] Cost monitoring accuracy tests
- [ ] Audit logging integrity tests

### Phase 4: Production Readiness (Week 4)
- [ ] YubiHSM2 setup and testing
- [ ] API key rotation procedure documentation
- [ ] Runbook for security incident response
- [ ] Monitoring and alerting setup
- [ ] Operator training on security tools

---

## Operational Procedures

### API Key Rotation Procedure
1. Generate new key using APIKeyManager
2. Update environment configuration
3. Monitor for 7-day grace period
4. Revoke old key after grace period
5. Verify no service disruption

### Security Incident Response
1. Identify affected keys via audit logs
2. Immediately revoke compromised keys
3. Rotate all keys in same environment
4. Review anomaly reports for patterns
5. Update rate limits if abuse detected

### Cost Escalation Response
1. Review cost monitoring dashboard
2. Identify high-usage devices
3. Implement tighter rate limits
4. Consider model downgrade (70B → 8B)
5. Enable caching for common patterns

---

**Status:** PHASE 1+2 COMPLETE  
**Next Steps:** Phase 3 testing (unit + integration tests)