"""Comprehensive audit logging for NIM API calls.

Tracks all NIM API calls with full metadata for security monitoring,
cost tracking, and anomaly detection.
"""
from __future__ import annotations

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
    """Metadata for a NIM API call."""
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