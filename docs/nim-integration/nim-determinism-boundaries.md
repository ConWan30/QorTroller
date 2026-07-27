# NIM Integration Determinism Boundaries

**Document Version:** 1.0  
**Last Updated:** 2026-07-27  
**Status:** OPERATIONAL POLICY  

---

## Overview

This document defines the boundaries between deterministic and probabilistic reasoning in QorTroller post-NIM integration. It specifies where LLM reasoning is acceptable, where determinism is mandatory, and how to implement deterministic fallbacks for all LLM-dependent paths.

---

## Determinism Classification Framework

### Classification Levels

**DETERMINISTIC (Level 0):**
- No LLM involvement permitted
- Must produce identical output for identical inputs
- Critical for security, correctness, and regulatory compliance

**PROBABILISTIC-ADVISORY (Level 1):**
- LLM reasoning permitted for suggestions
- Output requires human validation before action
- Used for decision support, not decision making

**PROBABILISTIC-ACTIONABLE (Level 2):**
- LLM reasoning permitted for automated actions
- Requires deterministic verification guards
- Used for well-bounded, reversible operations

**PROBABILISTIC-AUTHORITATIVE (Level 3):**
- LLM reasoning permitted for direct action
- Requires strong verification and rollback capability
- **NOT RECOMMENDED** for QorTroller

---

## Determinism Boundaries by Component

### 1. PoAC Commitment Computation

**Classification:** DETERMINISTIC (Level 0)

**Rationale:**
- PoAC is the cryptographic root of trust
- Any non-determinism breaks the commitment chain
- Regulatory requirement for immutable records

**LLM Involvement:** FORBIDDEN

**Determinism Requirements:**
- SHA-256 hash computation must be deterministic
- Byte ordering must be fixed (big-endian)
- Domain tag must be constant
- Input validation must be rule-based

**Verification:**
```python
# Test: Identical inputs produce identical outputs
def test_poac_determinism():
    input_data = b"VAPI-RETINA-STATE-v3" + device_id + ts_ns + events_root + worldstate_digest
    output1 = compute_poac_commitment(input_data)
    output2 = compute_poac_commitment(input_data)
    assert output1 == output2
```

---

### 2. Invariant Gate Checks

**Classification:** DETERMINISTIC (Level 0)

**Rationale:**
- Invariant gate is the correctness boundary
- Non-deterministic checks could allow invalid states
- CI/CD requires reproducible gate results

**LLM Involvement:** FORBIDDEN

**Determinism Requirements:**
- Regex pattern matching must be deterministic
- File content hashing must be deterministic
- Line counting must be exact
- Boolean logic must be rule-based

**Verification:**
```python
# Test: Invariant checks are deterministic
def test_invariant_determinism():
    result1 = check_invariant("INV-RETINA-STATE-V3", file_content)
    result2 = check_invariant("INV-RETINA-STATE-V3", file_content)
    assert result1 == result2
```

---

### 3. On-Chain State Transitions

**Classification:** DETERMINISTIC (Level 0)

**Rationale:**
- Blockchain transactions are irreversible
- Non-determinism could cause chain divergence
- Financial and security implications

**LLM Involvement:** FORBIDDEN

**Determinism Requirements:**
- Transaction construction must be deterministic
- Gas estimation must be consistent
- Signature generation must be deterministic
- State transition logic must be rule-based

**Verification:**
```python
# Test: Transaction construction is deterministic
def test_transaction_determinism():
    tx1 = construct_transaction(state, action)
    tx2 = construct_transaction(state, action)
    assert tx1.to_hex() == tx2.to_hex()
```

---

### 4. Real-Time Adjudication

**Classification:** DETERMINISTIC (Level 0)

**Rationale:**
- Real-time decisions affect live gameplay
- Non-determinism could cause unfair outcomes
- Latency requirements preclude LLM calls

**LLM Involvement:** FORBIDDEN

**Determinism Requirements:**
- Classification rules must be deterministic
- Threshold comparisons must be exact
- Boolean logic must be rule-based
- Timing must be clock-based, not probabilistic

**Verification:**
```python
# Test: Adjudication is deterministic
def test_adjudication_determinism():
    verdict1 = adjudicate_session(session_data)
    verdict2 = adjudicate_session(session_data)
    assert verdict1 == verdict2
```

---

### 5. Incident Mitigation Plan Synthesis

**Classification:** PROBABILISTIC-ADVISORY (Level 1)

**Rationale:**
- Mitigation plans are complex and context-dependent
- LLM can synthesize patterns from log data
- Operator validation required before implementation

**LLM Involvement:** PERMITTED WITH GUARDRAILS

**Determinism Requirements:**
- LLM output must be treated as advisory
- Operator must review and approve before action
- Deterministic fallback rules for common incidents
- Hash commitment of LLM output for audit trail

**Fallback Strategy:**
```python
def get_mitigation_plan(invariant_id, log_tail):
    # Try LLM first
    llm_plan = nim_client.synthesize_mitigation(invariant_id, log_tail)
    
    if llm_plan and operator_approves(llm_plan):
        return llm_plan
    
    # Fallback to deterministic rules
    return deterministic_mitigation_rules.get(invariant_id, default_plan)
```

**Verification:**
```python
# Test: Fallback is deterministic
def test_mitigation_fallback_determinism():
    plan1 = get_mitigation_plan("INV-RETINA-STATE-V3", log_tail)
    plan2 = get_mitigation_plan("INV-RETINA-STATE-V3", log_tail)
    # Fallback should be deterministic
    assert plan1["action"] == plan2["action"]
```

---

### 6. Protocol Health Interpretation

**Classification:** PROBABILISTIC-ADVISORY (Level 1)

**Rationale:**
- Protocol health is multi-dimensional
- LLM can provide contextual interpretation
- Base score computation remains deterministic

**LLM Involvement:** PERMITTED WITH GUARDRAILS

**Determinism Requirements:**
- Base protocol_health_score must be deterministic
- LLM interpretation is advisory only
- Ready-for-live-mode decision must be deterministic
- Component weights must be fixed

**Deterministic Core:**
```python
def compute_protocol_health_score():
    # Deterministic base score
    base_score = (
        0.35 * gate_progress_score +
        0.25 * fleet_health_score +
        0.20 * divergence_clarity_score +
        0.10 * corpus_pass_score +
        0.10 * class_j_confidence_score
    )
    
    # Deterministic ready decision
    ready = (base_score >= 85.0) and gate_passed and fleet_healthy
    
    return {
        "score": base_score,
        "ready": ready,
        "interpretation": llm_interpretation(base_score)  # Advisory only
    }
```

**Verification:**
```python
# Test: Base score is deterministic
def test_protocol_score_determinism():
    score1 = compute_protocol_health_score(data)
    score2 = compute_protocol_health_score(data)
    assert score1["score"] == score2["score"]
    assert score1["ready"] == score2["ready"]
    # Interpretation may differ (LLM advisory)
```

---

### 7. Root Cause Analysis

**Classification:** PROBABILISTIC-ADVISORY (Level 1)

**Rationale:**
- Root cause analysis requires pattern recognition
- LLM can synthesize across multiple log sources
- Human verification required before accepting

**LLM Involvement:** PERMITTED WITH GUARDRAILS

**Determinism Requirements:**
- LLM suggestions must be validated
- Deterministic heuristics for common patterns
- Audit trail of LLM suggestions vs. human decisions
- Confidence scoring for LLM output

**Fallback Strategy:**
```python
def analyze_root_issue(log_data):
    # Deterministic heuristics first
    heuristic_cause = deterministic_root_cause_analysis(log_data)
    if heuristic_cause.confidence > 0.8:
        return heuristic_cause
    
    # LLM analysis for complex cases
    llm_cause = nim_client.analyze_root_cause(log_data)
    
    # Return both for human review
    return {
        "heuristic": heuristic_cause,
        "llm_suggestion": llm_cause,
        "requires_review": True
    }
```

---

### 8. Agent Calibration Recommendations

**Classification:** PROBABILISTIC-ACTIONABLE (Level 2)

**Rationale:**
- Calibration optimization is complex multi-dimensional problem
- LLM can suggest parameter adjustments
- Automated application with verification guards

**LLM Involvement:** PERMITTED WITH GUARDRAILS

**Determinism Requirements:**
- Parameter changes must be bounded
- Verification tests must pass before applying
- Rollback capability for bad adjustments
- Rate limiting on calibration changes

**Verification Guards:**
```python
def apply_calibration_recommendations(agent_id, llm_suggestions):
    verified_changes = []
    
    for suggestion in llm_suggestions:
        # Check bounds
        if not within_safe_bounds(suggestion.parameter, suggestion.value):
            continue
        
        # Apply change
        old_value = get_agent_parameter(agent_id, suggestion.parameter)
        set_agent_parameter(agent_id, suggestion.parameter, suggestion.value)
        
        # Verify
        if not run_calibration_tests(agent_id):
            # Rollback
            set_agent_parameter(agent_id, suggestion.parameter, old_value)
            continue
        
        verified_changes.append(suggestion)
    
    return verified_changes
```

---

## Deterministic Fallback Requirements

### Fallback Principles

1. **Always Have a Fallback**
   - Every LLM-dependent path must have a deterministic fallback
   - Fallback must be pre-validated and tested
   - Fallback activation must be automatic

2. **Fallback Equivalence**
   - Fallback should produce functionally equivalent results
   - Performance differences should be minimal
   - User experience should be consistent

3. **Fallback Monitoring**
   - Track fallback activation frequency
   - Alert on high fallback rates
   - Review fallback effectiveness regularly

### Fallback Implementation Pattern

```python
class LLMWithFallback:
    """Pattern for LLM calls with deterministic fallback."""
    
    def __init__(self, nim_client, fallback_rules):
        self._nim_client = nim_client
        self._fallback_rules = fallback_rules
        self._fallback_count = 0
        self._llm_count = 0
    
    async def call_with_fallback(self, context, fallback_key):
        """Call LLM with deterministic fallback."""
        
        # Try LLM first
        try:
            result = await self._nim_client.generate_reasoning(context)
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
```

---

## Reasoning Output Verification

### Hash Commitment Pattern

```python
import hashlib
import json

def commit_reasoning_output(reasoning: dict) -> str:
    """Create hash commitment of LLM reasoning output."""
    
    # Canonical JSON representation
    canonical = json.dumps(reasoning, sort_keys=True, separators=(',', ':'))
    
    # SHA-256 hash
    commitment = hashlib.sha256(canonical.encode()).hexdigest()
    
    return commitment

def verify_reasoning_commitment(reasoning: dict, commitment: str) -> bool:
    """Verify reasoning output against commitment."""
    
    computed = commit_reasoning_output(reasoning)
    return computed == commitment
```

### Deterministic Output Schema

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any

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
    commitment_hash: str
    
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
```

---

## Model Version Pinning

### Version Strategy

**Model Pinning:**
- Pin specific model version in configuration
- Track model version in audit logs
- Test model updates before deployment
- Maintain rollback capability

**Configuration:**
```python
@dataclass
class NIMModelConfig:
    model_name: str = "llama-3-70b-instruct"
    model_version: str = "1"  # Specific version
    pin_version: bool = True  # Prevent auto-updates
    allowed_versions: list = None  # Whitelist of versions
    
    def __post_init__(self):
        if self.allowed_versions is None:
            self.allowed_versions = ["1", "2"]  # Initial versions
```

**Version Validation:**
```python
def validate_model_version(config: NIMModelConfig, actual_version: str) -> bool:
    """Validate that actual model version matches config."""
    
    if config.pin_version:
        return actual_version == config.model_version
    
    return actual_version in config.allowed_versions
```

---

## Non-Determinism Monitoring

### Metrics to Track

**LLM Consistency:**
- Same input, different output frequency
- Output variance for identical inputs
- Confidence score distribution

**Fallback Activation:**
- Fallback activation rate
- Time to fallback activation
- Fallback success rate

**Model Drift:**
- Output quality over time
- Latency changes over time
- Cost changes over time

### Monitoring Implementation

```python
class DeterminismMonitor:
    """Monitor non-determinism in LLM integration."""
    
    def __init__(self, store):
        self._store = store
    
    def track_llm_call(
        self,
        input_hash: str,
        output_hash: str,
        model_version: str,
        confidence: float
    ):
        """Track an LLM call for consistency monitoring."""
        
        self._store.insert_llm_call_tracker(
            input_hash=input_hash,
            output_hash=output_hash,
            model_version=model_version,
            confidence=confidence,
            timestamp=time.time()
        )
    
    def check_consistency(self, input_hash: str) -> dict:
        """Check consistency of outputs for same input."""
        
        with self._store._conn() as conn:
            rows = conn.execute(
                "SELECT output_hash, confidence, model_version "
                "FROM llm_call_tracker "
                "WHERE input_hash = ? "
                "ORDER BY timestamp DESC "
                "LIMIT 10",
                (input_hash,)
            ).fetchall()
        
        if len(rows) <= 1:
            return {"consistent": True, "reason": "insufficient_data"}
        
        # Check if all outputs are identical
        output_hashes = [row["output_hash"] for row in rows]
        consistent = len(set(output_hashes)) == 1
        
        return {
            "consistent": consistent,
            "unique_outputs": len(set(output_hashes)),
            "total_calls": len(rows),
            "output_hashes": output_hashes
        }
```

---

## Testing Requirements

### Determinism Tests

**Unit Tests:**
- Test all deterministic components produce identical outputs
- Test fallback rules are deterministic
- Test hash commitments are reproducible

**Integration Tests:**
- Test LLM failure triggers fallback correctly
- Test fallback produces equivalent results
- Test monitoring detects non-determinism

**Regression Tests:**
- Test model version changes don't break determinism
- Test configuration changes maintain determinism
- Test fallback rules remain effective over time

### Test Example

```python
import pytest

class TestDeterminismBoundaries:
    
    def test_poac_determinism(self):
        """PoAC computation must be deterministic."""
        input_data = b"test"
        output1 = compute_poac_commitment(input_data)
        output2 = compute_poac_commitment(input_data)
        assert output1 == output2
    
    def test_invariant_determinism(self):
        """Invariant checks must be deterministic."""
        content = "test content"
        result1 = check_invariant("TEST-INV", content)
        result2 = check_invariant("TEST-INV", content)
        assert result1 == result2
    
    def test_mitigation_fallback_determinism(self):
        """Mitigation fallback must be deterministic."""
        plan1 = get_mitigation_plan("INV-TEST", "log")
        plan2 = get_mitigation_plan("INV-TEST", "log")
        assert plan1["fallback_action"] == plan2["fallback_action"]
    
    def test_llm_fallback_activation(self):
        """LLM failure should trigger fallback."""
        # Mock LLM failure
        with mock_llm_failure():
            result = get_mitigation_plan("INV-TEST", "log")
            assert result["used_fallback"] is True
    
    def test_reasoning_commitment(self):
        """Reasoning commitment must be reproducible."""
        reasoning = {"test": "data"}
        hash1 = commit_reasoning_output(reasoning)
        hash2 = commit_reasoning_output(reasoning)
        assert hash1 == hash2
```

---

## Operational Procedures

### Model Update Procedure

1. **Test New Model Version**
   - Run A/B test against current version
   - Verify determinism boundaries are maintained
   - Check fallback effectiveness

2. **Staged Rollout**
   - Deploy to dev environment first
   - Monitor for 24 hours
   - Deploy to staging
   - Monitor for 48 hours
   - Deploy to production with 10% traffic
   - Gradually increase to 100%

3. **Rollback Plan**
   - Maintain previous version in configuration
   - Automate rollback procedure
   - Document rollback criteria

### Fallback Rule Updates

1. **Review Fallback Effectiveness**
   - Analyze fallback activation frequency
   - Review fallback success rate
   - Identify gaps in fallback coverage

2. **Update Fallback Rules**
   - Add new rules for common LLM failures
   - Test new rules deterministically
   - Deploy with monitoring

3. **Validate Post-Deployment**
   - Monitor fallback activation rate
   - Check for unexpected behavior
   - Roll back if issues detected

---

## Summary

**Determinism Boundaries:**

| Component | Classification | LLM Use | Fallback Required |
|-----------|---------------|---------|-------------------|
| PoAC Computation | DETERMINISTIC | FORBIDDEN | N/A |
| Invariant Gate | DETERMINISTIC | FORBIDDEN | N/A |
| On-Chain Transitions | DETERMINISTIC | FORBIDDEN | N/A |
| Real-Time Adjudication | DETERMINISTIC | FORBIDDEN | N/A |
| Mitigation Plans | ADVISORY | PERMITTED | YES |
| Protocol Interpretation | ADVISORY | PERMITTED | YES |
| Root Cause Analysis | ADVISORY | PERMITTED | YES |
| Calibration Recommendations | ACTIONABLE | PERMITTED | YES |

**Key Principles:**
1. Determinism is mandatory for security-critical components
2. LLM use requires deterministic fallbacks
3. All LLM output must be verified and committed
4. Model versions must be pinned and validated
5. Non-determinism must be continuously monitored

---

**Status:** OPERATIONAL POLICY APPROVED  
**Next Steps:** NIM client wrapper implementation (Step 4)