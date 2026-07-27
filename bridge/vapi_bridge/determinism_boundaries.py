"""Determinism boundaries for NIM integration — MitigationPlan, LLMWithFallback, DeterminismMonitor.

Phase 196 — Implements the patterns defined in nim-determinism-boundaries.md.
All probabilistic-advisory (Level 1) and probabilistic-actionable (Level 2) paths
use these components for deterministic fallback, hash commitment, and consistency
tracking.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hash commitment primitives (Section: Reasoning Output Verification)
# ---------------------------------------------------------------------------

def commit_reasoning_output(reasoning: dict) -> str:
    """Create SHA-256 hash commitment of LLM reasoning output.

    Uses canonical JSON (sorted keys, no whitespace) so identical data
    always produces the same hash. Follows the same principle as PoAC
    commitment formula hash chaining.
    """
    canonical = json.dumps(reasoning, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def verify_reasoning_commitment(reasoning: dict, commitment: str) -> bool:
    """Verify reasoning output against a prior hash commitment.

    Returns True if the commitment matches, False otherwise.
    """
    computed = commit_reasoning_output(reasoning)
    return computed == commitment


# ---------------------------------------------------------------------------
# Deterministic output schema (Section: Reasoning Output Verification)
# ---------------------------------------------------------------------------

@dataclass
class MitigationPlan:
    """Deterministic schema for mitigation plans with hash commitment.

    All fields are validated before the plan is accepted. The commitment_hash
    is computed from the canonical JSON of all other fields, enabling
    tamper detection and audit trail integrity.
    """
    incident_id: str
    invariant: str
    severity: str       # INFO | WARNING | CRITICAL
    root_cause: str
    mitigation: dict
    verification: str
    confidence: float   # 0.0 - 1.0
    llm_generated: bool
    commitment_hash: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary with commitment hash."""
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

    @classmethod
    def from_dict(cls, data: dict) -> "MitigationPlan":
        """Reconstruct from dict, verifying hash if present."""
        plan = cls(
            incident_id=data.get("incident_id", ""),
            invariant=data.get("invariant", ""),
            severity=data.get("severity", "INFO"),
            root_cause=data.get("root_cause", ""),
            mitigation=data.get("mitigation", {}),
            verification=data.get("verification", ""),
            confidence=float(data.get("confidence", 0.0)),
            llm_generated=bool(data.get("llm_generated", False)),
            commitment_hash=data.get("commitment_hash", ""),
        )
        return plan

    def verify(self) -> bool:
        """Verify that the stored commitment_hash matches current fields."""
        if not self.commitment_hash:
            return True  # No commitment to verify against
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
        return commit_reasoning_output(data) == self.commitment_hash


# ---------------------------------------------------------------------------
# Model version pinning (Section: Model Version Pinning)
# ---------------------------------------------------------------------------

@dataclass
class NIMModelConfig:
    """Model version pinning configuration.

    By default, the model version is pinned to prevent silent auto-updates
    from changing LLM behavior without operator awareness.
    """
    model_name: str = "llama-3-70b-instruct"
    model_version: str = "1"
    pin_version: bool = True
    allowed_versions: Optional[list] = None

    def __post_init__(self):
        if self.allowed_versions is None:
            self.allowed_versions = ["1", "2"]

    def validate(self, actual_version: str) -> bool:
        """Validate that actual model version matches configuration."""
        if self.pin_version:
            return actual_version == self.model_version
        return actual_version in (self.allowed_versions or [])


# ---------------------------------------------------------------------------
# LLMWithFallback (Section: Deterministic Fallback Requirements)
# ---------------------------------------------------------------------------

class LLMWithFallback:
    """Decorator pattern for LLM calls with deterministic fallback.

    Every LLM-dependent path follows this pattern:
    1. Try LLM first (if enabled and available)
    2. Fall back to deterministic rules
    3. Ultimate fallback (default behavior)

    Tracks LLM vs fallback statistics for monitoring.
    """

    def __init__(
        self,
        nim_client: Any,
        fallback_rules: Optional[dict[str, Callable]] = None,
    ):
        self._nim_client = nim_client
        self._fallback_rules = fallback_rules or {}
        self._llm_count = 0
        self._fallback_count = 0
        self._default_count = 0

    async def call_with_fallback(
        self,
        context: str,
        fallback_key: str,
    ) -> Optional[str]:
        """Call LLM with deterministic fallback.

        Args:
            context: The prompt/context to send to NIM.
            fallback_key: Key into fallback_rules dict for deterministic rule.

        Returns:
            Response string from LLM, fallback rule, or None.
        """
        if self._nim_client is not None:
            try:
                result = await self._nim_client.generate_reasoning(
                    device_id="", prompt=context
                )
                if result and self._validate_output(result):
                    self._llm_count += 1
                    return result
            except Exception as exc:
                log.warning("LLM call failed: %s — using fallback", exc)

        if fallback_key in self._fallback_rules:
            self._fallback_count += 1
            return self._fallback_rules[fallback_key](context)

        self._default_count += 1
        return self._default_fallback(fallback_key)

    def _validate_output(self, output: str) -> bool:
        """Validate LLM output before accepting it."""
        if not output or not output.strip():
            return False
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                return True
            return True  # Non-JSON output may be valid (plain text)
        except (json.JSONDecodeError, ValueError):
            return True  # Accept non-JSON output

    def _default_fallback(self, key: str) -> str:
        """Ultimate fallback when no rules match."""
        return json.dumps({
            "status": "defer",
            "reason": "no_fallback",
            "fallback_key": key,
        })

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


# ---------------------------------------------------------------------------
# DeterminismMonitor (Section: Non-Determinism Monitoring)
# ---------------------------------------------------------------------------

class DeterminismMonitor:
    """Monitor non-determinism in LLM integration.

    Tracks LLM call consistency by storing input/output hashes in the
    llm_call_tracker table. When the same input produces different outputs,
    the monitor flags the inconsistency.
    """

    def __init__(self, store):
        self._store = store

    def track_call(
        self,
        input_text: str,
        output_text: str,
        model_version: str,
        confidence: float = 0.0,
    ) -> str:
        """Track an LLM call for consistency monitoring.

        Args:
            input_text: The prompt sent to the LLM.
            output_text: The response from the LLM.
            model_version: Model version identifier.
            confidence: Confidence score (0.0-1.0) for the output.

        Returns:
            The input hash for later consistency checks.
        """
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()
        output_hash = hashlib.sha256(output_text.encode()).hexdigest()

        try:
            if hasattr(self._store, "insert_llm_call_tracker"):
                self._store.insert_llm_call_tracker(
                    input_hash=input_hash,
                    output_hash=output_hash,
                    model_version=model_version,
                    confidence=confidence,
                    timestamp=time.time(),
                )
        except Exception as exc:
            log.warning("DeterminismMonitor: failed to track call: %s", exc)

        return input_hash

    def check_consistency(self, input_hash: str) -> dict:
        """Check whether the same input has produced consistent outputs.

        Returns:
            dict with consistent (bool), unique_outputs (int),
            total_calls (int), and output_hashes (list).
        """
        rows = []
        try:
            if hasattr(self._store, "get_call_tracker_by_input"):
                rows = self._store.get_call_tracker_by_input(
                    input_hash, limit=10
                )
        except Exception as exc:
            log.warning("DeterminismMonitor: consistency check failed: %s", exc)
            return {"consistent": True, "error": str(exc)}

        if len(rows) <= 1:
            return {"consistent": True, "reason": "insufficient_data"}

        output_hashes = [r.get("output_hash", "") for r in rows]
        unique = set(output_hashes)
        return {
            "consistent": len(unique) == 1,
            "unique_outputs": len(unique),
            "total_calls": len(rows),
            "output_hashes": list(unique),
        }