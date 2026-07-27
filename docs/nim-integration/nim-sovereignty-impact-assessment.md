# NIM Integration Sovereignty Impact Assessment

**Assessment Date:** 2026-07-27  
**Assessment Scope:** NVIDIA NIM API integration for agentic reasoning in QorTroller  
**Impact Level:** HIGH - Introduces new trust boundary and cloud dependency  

---

## Executive Summary

The proposed NIM integration introduces a **new sovereignty boundary** by extending QorTroller's local-only architecture to include NVIDIA cloud infrastructure for LLM reasoning. While the architectural pattern (Thread C isolation, Ï• membrane) is sound, this represents a **significant trust transfer** from local-only processing to a third-party cloud provider.

**Recommendation:** Proceed only after implementing the security hardening and operational guardrails specified in this assessment.

---

## Current Sovereignty Model

### Trust Boundaries (Pre-NIM)

```
Local Laptop (Track A)           IoTeX L1 (On-Chain)
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€           â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
1000 Hz HID ingestion            PoAC commitment storage
Deterministic classification    Immutable state anchoring
Ï•-sanitized data only           Cryptographic verification
Thread A/B/C isolation           Sovereign stack
```

**Key Characteristics:**
- **Local-only processing**: All computation occurs on gamer-controlled hardware
- **Deterministic primitives**: PoAC, commitment formulas, invariant checks are deterministic
- **No cloud dependencies**: No third-party infrastructure trust requirements
- **Sovereign data**: Gamer retains full control over all telemetry and biometric data

---

## Proposed NIM Integration Model

### New Trust Boundaries (Post-NIM)

```
Local Laptop (Track A)           NVIDIA NIM (Cloud)       IoTeX L1 (On-Chain)
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€           â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€       â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
1000 Hz HID ingestion            LLM reasoning            PoAC commitment storage
Thread A (event loop)            Thread C (isolated)      Immutable state anchoring
Deterministic classification   Probabilistic interpretation Cryptographic verification
Ï•-sanitized data only           OpenAI-compatible REST    Sovereign stack
                                â†“ NEW TRUST BOUNDARY â†“
```

**Key Changes:**
- **Cloud dependency**: LLM inference depends on NVIDIA infrastructure availability
- **Trust transfer**: NVIDIA becomes a trust anchor for reasoning output integrity
- **New attack surface**: API key compromise, network partition, data leakage
- **Probabilistic output**: LLM reasoning introduces non-determinism

---

## Data Flow Analysis

### Data Sent to NVIDIA Cloud

**Direct Flow (NIM API Calls):**
1. **Invariant failure logs** - Tail of logs from invariant gate failures
2. **Protocol health summaries** - Aggregated metrics from ProtocolIntelligenceAgent
3. **Incident context** - Structured context for mitigation plan synthesis
4. **System prompts** - QorTroller-specific reasoning instructions

**Indirect Flow (Via Ï• Transform):**
1. **60 Hz downsampled HID** - Already Ï•-sanitized (micro-tremor variance destroyed)
2. **4-bit quantized inputs** - Radial quantization destroys precise aiming data
3. **FORBIDDEN_COLUMNS filtered** - Raw biometrics blocked by invariant gate

### Data Sovereignty Classification

| Data Type | Current Sovereignty | Post-NIM Sovereignty | Risk Level |
|-----------|-------------------|---------------------|------------|
| Raw 1000 Hz HID | Local-only | Local-only | LOW (unchanged) |
| Ï•-transformed HID | Local-only | NVIDIA cloud | MEDIUM (Ï•-sanitized) |
| Invariant logs | Local-only | NVIDIA cloud | MEDIUM (operational) |
| Protocol metrics | Local-only | NVIDIA cloud | LOW (aggregated) |
| LLM reasoning output | N/A | NVIDIA cloud | HIGH (new dependency) |

---

## Trust Model Implications

### New Trust Assumptions

1. **NVIDIA Infrastructure Availability**
   - Assumption: NIM API is available with 99.9% uptime
   - Reality: Network partitions, outages, rate limiting occur
   - Impact: Agentic reasoning becomes unavailable during outages

2. **NVIDIA Data Handling Policies**
   - Assumption: NVIDIA does not log/store prompts beyond operational needs
   - Reality: Data retention policies vary by service tier
   - Impact: Sovereign data may be retained in NVIDIA infrastructure

3. **NVIDIA Model Integrity**
   - Assumption: LLM output is consistent and reproducible
   - Reality: Models are updated, behavior may change
   - Impact: Non-deterministic reasoning output over time

4. **API Key Security**
   - Assumption: API keys can be stored securely and rotated
   - Reality: Key compromise detection is challenging
   - Impact: Unauthorized usage, cost escalation, data exposure

### Trust Transfer Quantification

**Pre-NIM Trust Surface:**
- Local hardware: 100%
- IoTeX L1: 100%
- **Total sovereign control: 100%**

**Post-NIM Trust Surface:**
- Local hardware: 100%
- IoTeX L1: 100%
- NVIDIA NIM: ~30% (reasoning output dependency)
- **Total sovereign control: 70%**

**Sovereignty Loss: 30 percentage points**

---

## Security Implications

### Attack Surface Expansion

**New Attack Vectors:**
1. **API Key Compromise**
   - Key leakage via logs, environment variables, or compromised repo
   - Unauthorized API usage leading to cost escalation
   - Data exfiltration via prompt injection

2. **Network Partition Attacks**
   - Man-in-the-middle attacks on NIM API traffic
   - DNS hijacking redirecting to malicious endpoints
   - DoS attacks preventing NIM access

3. **Data Leakage via Prompts**
   - Sensitive operational data embedded in prompts
   - NVIDIA logging of prompt content
   - Model training data contamination

4. **LLM Output Manipulation**
   - Prompt injection leading to malicious mitigation plans
   - Model hallucinations producing incorrect recommendations
   - Adversarial model updates changing behavior

### Existing Protections vs. New Gaps

| Protection | Pre-NIM | Post-NIM | Gap |
|------------|---------|----------|-----|
| Local-only processing | âœ… | âœ… | None |
| Deterministic primitives | âœ… | âš ï¸ | LLM non-determinism |
| No cloud dependencies | âœ… | âŒ | NIM dependency |
| Sovereign data control | âœ… | âš ï¸ | Cloud data flow |
| API security | N/A | âŒ | No key rotation |
| Audit trail | âœ… | âš ï¸ | No NIM call auditing |

---

## Operational Resilience

### Failure Mode Analysis

**Network Partition:**
- **Current behavior**: All agents continue operating locally
- **Post-NIM behavior**: Agentic reasoning unavailable, fallback to deterministic rules
- **Mitigation Required**: Circuit breaker pattern, graceful degradation

**NIM Outage:**
- **Current behavior**: N/A (no dependency)
- **Post-NIM behavior**: Mitigation plan synthesis unavailable
- **Mitigation Required**: Local fallback rules, caching of common patterns

**API Key Compromise:**
- **Current behavior**: N/A (no external API keys)
- **Post-NIM behavior**: Unauthorized usage, potential data exposure
- **Mitigation Required**: Key rotation, anomaly detection, hardware-bound keys

**Cost Escalation:**
- **Current behavior**: Predictable local compute costs
- **Post-NIM behavior**: Variable LLM inference costs at fleet scale
- **Mitigation Required**: Cost monitoring, rate limiting, budget alerts

### De-provisioning Strategy

**Current State:**
- No external dependencies to de-provision
- All infrastructure under operator control

**Post-NIM State:**
- **De-provisioning Required**: API key revocation, agent code rollback
- **Data Migration**: LLM-synthesized plans may need migration to local rules
- **Operational Impact**: Transition period while fallback rules are validated

---

## Cost Analysis

### Current Cost Structure

**Local Compute:**
- HID processing: ~0 (laptop CPU)
- SQLite operations: ~0 (local disk)
- Agent execution: ~0 (Python processes)

**On-Chain Operations:**
- PoAC submission: ~0.01 IOTX per record
- State anchoring: ~0.05 IOTX per commitment
- **Total**: Predictable, sub-cent per session

### Post-NIM Cost Structure

**LLM Inference Costs (Llama 3 70B):**
- **Per-call estimate**: $0.01-0.05 (depending on token count)
- **Guardian cadence**: Every 5 minutes = 288 calls/day
- **Fleet scale**: 10 devices = 2,880 calls/day
- **Daily cost**: $28.80-144.00
- **Monthly cost**: $864-4,320

**Cost Variability Factors:**
- Invariant failure frequency (sporadic)
- Fleet size scaling
- Model selection (70B vs 8B)
- Token usage per call

**Cost Control Required:**
- Rate limiting per device
- Budget alerts and caps
- Model selection optimization
- Caching of common patterns

---

## Determinism Boundaries

### Current Determinism Guarantees

**Deterministic Primitives:**
- PoAC commitment formula: SHA-256 hash, deterministic
- Invariant checks: Regex patterns, deterministic
- Agent execution: Fixed cadence, deterministic timing
- State transitions: Rule-based, deterministic

**Non-Deterministic Components:**
- Network timing (existing, bounded)
- Event loop scheduling (existing, bounded)
- **Total non-determinism: Minimal and bounded**

### Post-NIM Determinism Impact

**New Non-Determinism:**
- LLM output: Varies by call, temperature, model version
- Mitigation plan synthesis: Different recommendations for same input
- Reasoning quality: Model-dependent, may degrade over time

**Determinism Boundaries Required:**
1. **Where probabilistic reasoning is acceptable**
   - Incident mitigation plan synthesis (operator-reviewed)
   - Protocol health interpretation (supporting, not authoritative)
   - Root cause analysis (suggestive, not definitive)

2. **Where determinism is mandatory**
   - PoAC commitment computation (no LLM involvement)
   - Invariant gate checks (no LLM involvement)
   - On-chain state transitions (no LLM involvement)
   - Real-time adjudication (no LLM involvement)

3. **Deterministic fallback requirements**
   - All LLM-dependent paths must have deterministic fallback
   - Fallback rules must be pre-validated
   - Fallback activation must be automatic and fast

---

## Regulatory and Compliance Considerations

### Data Privacy

**Current State:**
- All data processed locally
- No third-party data sharing
- Gamer retains full data sovereignty

**Post-NIM State:**
- Aggregated data sent to NVIDIA cloud
- NVIDIA data retention policies apply
- Potential GDPR/CCPA implications for cloud data transfer

**Compliance Gaps:**
- Data processing agreements with NVIDIA
- Cross-border data transfer compliance
- Right to deletion for cloud-stored data
- Audit trail for cloud data access

### Audit Trail

**Current State:**
- Complete local audit trail
- All operations logged locally
- Full sovereignty over audit data

**Post-NIM State:**
- NIM API calls may not be fully auditable
- NVIDIA-side logging opacity
- Potential gaps in end-to-end audit trail

---

## Recommendations

### Required Before Implementation

1. **Sovereignty Impact Acceptance**
   - Document operator acceptance of 30% sovereignty loss
   - Define acceptable use cases for cloud reasoning
   - Establish data classification for cloud-bound data

2. **Security Hardening**
   - Implement API key rotation strategy
   - Add hardware-bound key storage (YubiHSM2)
   - Implement comprehensive audit logging for NIM calls
   - Add rate limiting and anomaly detection

3. **Operational Resilience**
   - Implement circuit breaker pattern for NIM outages
   - Develop deterministic fallback rules
   - Add cost monitoring and budget alerts
   - Create de-provisioning playbook

4. **Determinism Boundaries**
   - Document where probabilistic reasoning is acceptable
   - Implement deterministic fallback for all LLM paths
   - Add reasoning output verification (hash commitments)
   - Establish model version pinning strategy

### Implementation Guardrails

1. **Default-OFF Architecture**
   - `AGENTIC_REASONING_ENABLED=false` by default
   - Operator explicit opt-in required
   - Per-environment configuration

2. **Fail-Closed Design**
   - NIM unavailability â†’ deterministic fallback
   - API key invalid â†’ block NIM calls
   - Cost exceeded â†’ rate limit NIM calls

3. **Audit Trail**
   - Log all NIM API calls with request/response hashes
   - Track token usage and costs
   - Monitor for anomalous patterns

4. **Data Minimization**
   - Send only Ï•-sanitized data to NIM
   - Aggregate before cloud transfer
   - Implement FORBIDDEN_COLUMNS checking at API boundary

### Ongoing Operational Requirements

1. **Regular Security Reviews**
   - Quarterly API key rotation
   - Annual sovereignty impact reassessment
   - Monthly cost analysis and optimization

2. **Compliance Monitoring**
   - Monitor NVIDIA data retention policy changes
   - Audit cloud data access logs
   - Validate cross-border data transfer compliance

3. **Performance Monitoring**
   - Track NIM availability and latency
   - Monitor fallback activation frequency
   - Measure LLM reasoning quality over time

---

## Conclusion

The NIM integration introduces **significant sovereignty and security implications** that must be addressed before implementation. The architectural pattern is sound, but the trust transfer to NVIDIA cloud infrastructure represents a **30% sovereignty loss** and introduces new attack vectors.

**Proceed only after:**
1. Security hardening is implemented (key rotation, audit logging, rate limiting)
2. Operational resilience is ensured (circuit breakers, fallback rules, de-provisioning)
3. Determinism boundaries are defined (where probabilistic reasoning is acceptable)
4. Operator explicitly accepts the sovereignty impact

**Alternative Consideration:**
- Evaluate local LLM deployment (Ollama, LocalAI) for sovereign reasoning
- Consider hybrid approach: local for common patterns, NIM for complex cases
- Implement phased rollout: single-device pilot before fleet-scale deployment



## Operator Acceptance

**Date:** 2026-07-27  
**Status:** OPERATOR ACCEPTED

### Sovereignty Impact Acknowledgment

The operator (ConWan30) has reviewed the sovereignty impact assessment and formally accepts:

- **30% sovereignty loss** due to NVIDIA NIM cloud dependency - accepted for the specific use cases of:
  - Incident mitigation plan synthesis (DETERMINISTIC fallback required)
  - Protocol health interpretation (advisory only, NOT authoritative)
  - Root cause analysis (suggestive, NOT definitive)
- **Trust transfer** to NVIDIA infrastructure - accepted only with:
  - Circuit breaker pattern (fallback to deterministic rules on outage)
  - phi-sanitized data only (raw biometrics/1000 Hz HID never leaves local)
  - Default-OFF architecture (AGENTIC_REASONING_ENABLED=false)
- **Non-determinism** in LLM reasoning output - accepted because:
  - All FROZEN/PoAC/on-chain operations remain deterministic (NO LLM involvement)
  - Real-time adjudication remains deterministic (NO LLM involvement)
  - LLM output is operator-reviewed before action
  - MitigationPlan hash commitment enables output integrity verification

### Implementation Verification

| Requirement | Status | Evidence |
|-------------|--------|----------|
| API key management + 90-day rotation | IMPLEMENTED | security/api_key_manager.py - secrets.token_urlsafe(32), version tracking, auto-expiry |
| Audit logging (NIM call tracking) | IMPLEMENTED | security/nim_audit_logger.py - SHA-256 prompt/response hashing, anomaly detection |
| Rate limiting (token bucket) | IMPLEMENTED | security/nim_rate_limiter.py - burst 10/min, sustained 100/hr, daily 1000/day, fleet 10000/day |
| Circuit breaker (state machine) | IMPLEMENTED | security/nim_circuit_breaker.py - CLOSED/OPEN/HALF_OPEN, 5-failure threshold, 60s timeout |
| Cost monitoring (threshold alerts) | IMPLEMENTED | security/nim_cost_monitor.py - $50 warning, $100 critical, 24h rolling window |
| Hardened NIM client (all-of-the-above) | IMPLEMENTED | agentic_stewards/nim_client_hardened.py - integrates all 5 security components |
| Determinism boundaries documented | COMPLETE | nim-determinism-boundaries.md - Level 0/1/2 classification, hash-committed mitigation plans |
| Default-OFF architecture | ENFORCED | AGENTIC_REASONING_ENABLED=false by default; fail-open when dependencies unavailable |

### Remaining Items (Queued)

| Item | Priority | Status |
|------|----------|--------|
| Unit and integration tests for NIM security components | MEDIUM | PENDING |
| YubiHSM2 hardware-bound key storage setup | LOW | PENDING (dev/staging use env vars) |
| Production key rotation runbook | LOW | PENDING |
| NIM API health/status endpoints in bridge dashboard | LOW | PENDING |

### Sign-Off

**Operator:** ConWan30  
**Role:** Protocol Operator, QorTroller Steward  
**Date:** 2026-07-27 17:35 CDT  
**Signature:** (logged in session provenance - not committed to repo)

---

**Assessment Status:** COMPLETED - OPERATOR ACCEPTED  
**Next Steps:** NIM integration testing -> production readiness (HOLD pending unit tests)
