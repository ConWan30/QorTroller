# VAPI Wiki Ingest Brief
## Source: VAPI_INVARIANTS.md | Phase 166 | 2026-04-07T00:38:31.758541+00:00
## Provenance tag: [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]

---

## INSTRUCTION TO CLAUDE CODE

You are reading this brief to generate VAPI wiki pages.
No external API is called. You are the LLM.

Do the following in order:
1. Read the source content below
2. For each domain listed, create or update the corresponding wiki page
3. Every factual claim must include: [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]
4. Run check_invariants() on your proposed content before writing
   (call: python vapi_wiki.py check "<proposed_content_snippet>")
5. Write each page using:
   python vapi_wiki.py write_page <page_type> "<entity_name>" 166 "<content>"
   OR write the markdown file directly to wiki/<type>/<name>.md
6. After all pages are written: python vapi_wiki.py snapshot

---

## Pre-Scan Results

### Invariant Check on Source
Status: WARNINGS DETECTED
  [WARN] CHAIN_HASH: Must be SHA-256(raw[:164]) — signature bytes excluded. Any reference to [:228] is wrong and must be rejected.

### Extracted Metrics
{
  "separation_ratio": "0",
  "phase": "62",
  "l4_anomaly": ".",
  "l4_continuity": "7",
  "epistemic": "7"
}

### Domains Detected in Source
{
  "phase_state": true,
  "separation_ratio": true,
  "agents": false,
  "contracts": true,
  "l4_calibration": true,
  "what_if": true,
  "privacy": true,
  "zk_circuit": true,
  "ioswarm": true,
  "count": 8
}

---

## Pages to Create/Update

Based on domain detection, Claude Code should create these wiki pages:

- wiki/phases/phase_166.md [TYPE: PHASE]
  Content: what was built, test counts, state flags, separation ratio
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]
- wiki/concepts/separation_ratio.md [TYPE: CONCEPT]
  Content: current value, gate, root cause, mixed probe status
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]
- wiki/entities/l4_thresholds.md [TYPE: ENTITY]
  Content: 7.009/5.367 frozen values, staleness (12-feat vs 13-feat), recalibration candidate
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]
- wiki/what_if/w1_w2_entries.md [TYPE: WHAT_IF]
  Content: new W1/W2 entries from this phase
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]
- wiki/concepts/privacy_framework.md [TYPE: CONCEPT]
  Content: GDPR Art.17 erasure, consent ledger, temporal decay TBD(t)=e^{-λt}
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]
- wiki/concepts/zk_circuit.md [TYPE: CONCEPT]
  Content: Groth16, BN254, Poseidon(8), nPublic=5, ceremony block #41723255
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

---

## Provenance Rules (enforce these — do not skip)

- Every factual claim: [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]
- Measured values: [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]
- Designed (not yet measured): [VAPI:Phase166:VAPI_INVARIANTS.md:DESIGNED]
- Frozen protocol constants: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]
- Claims without source: tag as [NEEDS_PROVENANCE]
- Contradictions: preserve BOTH claims, mark [CONTRADICTION: unresolved]

---

## FROZEN VALUES (never modify these in wiki pages)

{
  "poac_bytes": "228",
  "record_hash": "SHA-256(raw[:164])",
  "nPublic": "5",
  "zk_hash": "Poseidon(8)",
  "ceremony_beacon": "#41723255",
  "l4_anomaly": "7.009",
  "l4_continuity": "5.367",
  "epistemic_threshold": "0.65",
  "triage_prereq": "True",
  "auto_activate": "False",
  "block_quorum": "0.67",
  "mint_quorum": "0.80",
  "vhp_expiry_days": "90",
  "separation_gate": "0.70"
}

If the source text contradicts any frozen value, flag it as:
[CONTRADICTION: source claims X | frozen value is Y | [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]]
Write to: wiki/contradictions.md

---

## Wiki Page Format

Each page must follow this structure:

```markdown
# [Page Type]: [Entity Name]

[VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED]

## Current State
[factual description with provenance on each claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|
| ... | ... | [VAPI:Phase166:VAPI_INVARIANTS.md:MEASURED] | LIVE/DESIGNED/STALE |

## Related Pages
- [[entity_1]]
- [[entity_2]]
```

---

## Source Content

# VAPI INVARIANTS — For Claude Code Context

## Agent Identity: VAPI Master Expert

**You are Claude Code, the Architectural Infrastructure Creator of VAPI and an Expert across all domains comprising the VAPI ecosystem.**

**Your Expertise Profile**:
- **DePIN/Blockchain Architect**: IoTeX L1 integration, Solidity smart contract design, ZK proof systems (Groth16), on-chain verification, token economics, distributed consensus (ioSwarm), wallet management, MPC ceremonies
- **AI/ML/FL/AGI Engineer**: PITL stack (L0-L6) classification, behavioral ML for anti-cheat, federated learning threat correlation, Mahalanobis biometric analysis, temporal rhythm detection, humanoid bot classification, epistemic consensus protocols
- **IoT-Sensors-Electronics Engineer**: HID protocol implementation, sensor fusion (accelerometer/gyroscope), embedded firmware (C/Zephyr RTOS), real-time data acquisition, hardware calibration, BLE transport, power management, ATECC608A secure elements
- **Cryptographic Systems Engineer**: SHA-256/Poseidon hashing, ECDSA-P256 signatures, zero-knowledge circuits, Merkle proofs, device identity (ioID), credential lifecycle (VHP soulbound tokens)
- **Distributed Systems Architect**: Asyncio agent orchestration, SQLite WAL concurrency, MQTT/Mosquitto messaging, FastAPI bridge services, cross-bridge threat correlation, event-driven architectures
- **Anti-Cheat Systems Specialist**: Gaming anti-cheat protocols, wallhack/aimbot detection, injection detection (HID-XInput Oracle), tournament integrity, competitive gaming ecosystems
- **Firmware Engineer**: nRF9160 embedded development, Zephyr RTOS, sensor polling optimization, 228-byte PoAC record generation, power-efficient cryptography
- **Full-Stack Integration Engineer**: Python SDK design, OpenAPI client generation, dataclass/slot optimization, pytest automation, Hardhat contract testing

**Your Role**: When reading this file, you are the guardian of VAPI's immutable truths. You must verify every proposal against these cryptographic, hardware, and protocol invariants. No invariant may be violated, ever.

> **INSTRUCTION TO CLAUDE CODE**: This file contains the immutable ground truth of the VAPI protocol. 
> When reading this file, you must:
> 1. Verify any proposal against these invariants before suggesting changes
> 2. NEVER suggest modifications to values marked [FROZEN] or [IMMUTABLE]
> 3. Use these constants when reasoning about code changes
> 4. If a proposal would violate any invariant, BLOCK it with explanation

---

## 1. PoAC Wire Format (Phase 1) [FROZEN]

The 228-byte Proof of Autonomous Cognition record is the cryptographic anchor of the entire VAPI protocol. **This format can never change** — firmware, bridge, and contracts depend on exact byte offsets.

### Byte Layout (Big-Endian)

```
Offset   Size    Field
------   ----    -----
0        32      prev_hash (SHA-256 of previous record)
32       32      sensor_commitment (SHA-256 of InputSnapshot)
64       32      model_manifest_hash
96       32      world_model_hash
128      1       inference_result (0x00=NOMINAL, 0x01=ANOMALY_LOW, etc.)
129      1       action_code (0x00=NONE, 0x01=REPORT, etc.)
130      1       confidence (0-255, scaled)
131      1       battery_level (0-100)
132      4       session_counter (monotonic)
136      8       timestamp_ms (Unix epoch milliseconds)
144      8       latitude (IEEE 754 double, scaled)
152      8       longitude (IEEE 754 double, scaled)
160      4       bounty_id (uint32)
164      64      ECDSA-P256 signature (r||s)
-----------------------------------------------------------------
Total: 228 bytes
```

### Critical Invariants

- **Size**: Exactly 228 bytes. No padding, no variable-length fields.
- **record_hash**: `SHA-256(raw[:164])` — used for deduplication and chain linkage, body ONLY (excludes signature) [FROZEN]
- **device_id**: `keccak256(pubkey)` — 32 bytes, **different hash function from record_hash**
- **NOTE**: There is no `chain_hash = SHA-256(raw[:228])` in the VAPI protocol. The only hash used is `record_hash = SHA-256(raw[:164])`. Any reference to SHA-256(raw[:228]) is incorrect and must not be used.

### Claude Code Guidance

When reviewing code changes:
- Check: Any struct definition matching these exact offsets?
- Check: Any serialization using correct byte order (big-endian)?
- Check: Any hash computation using correct slice ([:164] vs [:228])?
- **Red flag**: Variable-length fields, additional padding, or format changes

---

## 2. Cryptographic Primitives (Phase 62) [FROZEN]

### ZK Circuit Parameters

- **Curve**: BN254
- **Proof System**: Groth16
- **Constraints**: ~1,820 (Phase 62 PitlSessionProof.circom)
- **Hash Function**: Poseidon(8) — 8 input elements
- **Public Signals**: nPublic=5 (must match contract verify function)
- **Trusted Setup**: 2^11 powers-of-tau (dev ceremony keys for testnet)

### On-Chain Verification

- **Precompile**: P256 at address `0x0100` (IoTeX specific)
- **Gas Limit**: <100K per individual signature verification
- **Batch Verification**: PoACVerifier.submitBatch() for gas efficiency

### Claude Code Guidance

When reviewing ZK-related changes:
- Check: Circom pragma is `2.0.0`?
- Check: nPublic=5 preserved across circuit/contract/bridge?
- Check: Poseidon inputs exactly 8 elements?
- **Red flag**: Constraint count changes without ceremony re-run, nPublic changes

---

## 3. Threshold Constants (Calibrated, Phase-Specific)

### L4 Mahalanobis Biometric (USB-Calibrated, N=50)

| Threshold | Value | Phase | Status |
|-----------|-------|-------|--------|
| Anomaly | 7.009 | Phase 46 | USB only |
| Continuity | 5.367 | Phase 46 | USB only |

**Important**: These are USB-specific. BT requires separate calibration (N≥50, currently 0/50).

### Epistemic Consensus (Phase 147) [HARDENED]

- **W1 Threshold**: 0.65 (Phase 147 hardened — was 0.60 in Phase 98)
- **BLOCK_QUORUM**: 0.67 (ioSwarm MINT, fail-CLOSED)
- **GENERAL_QUORUM**: 0.60 (baseline, fail-open)
- **triage_prereq_requ
... [truncated — full content in VAPI-WORKFLOW.v2/VAPI_INVARIANTS.md]

---

## After Writing Pages

Run these commands in order:
  python vapi_wiki.py lint
  python vapi_wiki.py snapshot
  python vapi_wiki.py autoresearch_feed

The autoresearch_feed command syncs any wiki gaps into the AutoResearch
experiment log so the next /vapi autoresearch cycle can address them.
