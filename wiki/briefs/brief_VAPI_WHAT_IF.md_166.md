# VAPI Wiki Ingest Brief
## Source: VAPI_WHAT_IF.md | Phase 166 | 2026-04-08T01:11:24.057410+00:00
## Provenance tag: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

---

## INSTRUCTION TO CLAUDE CODE

You are reading this brief to generate VAPI wiki pages.
No external API is called. You are the LLM.

Do the following in order:
1. Read the source content below
2. For each domain listed, create or update the corresponding wiki page
3. Every factual claim must include: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]
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
  [WARN] EPISTEMIC: Threshold 0.65 (Phase 147 hardening). Cannot regress. triage_prereq_required=True also required.

### Extracted Metrics
{
  "separation_ratio": "1.0",
  "bridge_tests": "4",
  "agents": "20",
  "phase": "10",
  "l4_anomaly": "9",
  "l4_continuity": "7",
  "epistemic": "."
}

### Domains Detected in Source
{
  "phase_state": true,
  "separation_ratio": true,
  "agents": true,
  "contracts": true,
  "l4_calibration": true,
  "what_if": true,
  "privacy": true,
  "zk_circuit": true,
  "ioswarm": true,
  "count": 9
}

---

## Pages to Create/Update

Based on domain detection, Claude Code should create these wiki pages:

- wiki/phases/phase_166.md [TYPE: PHASE]
  Content: what was built, test counts, state flags, separation ratio
  Provenance: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]
- wiki/concepts/separation_ratio.md [TYPE: CONCEPT]
  Content: current value, gate, root cause, mixed probe status
  Provenance: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]
- wiki/entities/agent_fleet.md [TYPE: ENTITY]
  Content: all 166 agents, new agents added this phase, epistemic threshold
  Provenance: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]
- wiki/entities/l4_thresholds.md [TYPE: ENTITY]
  Content: 7.009/5.367 frozen values, staleness (12-feat vs 13-feat), recalibration candidate
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]
- wiki/what_if/w1_w2_entries.md [TYPE: WHAT_IF]
  Content: new W1/W2 entries from this phase
  Provenance: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]
- wiki/concepts/privacy_framework.md [TYPE: CONCEPT]
  Content: GDPR Art.17 erasure, consent ledger, temporal decay TBD(t)=e^{-λt}
  Provenance: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]
- wiki/concepts/zk_circuit.md [TYPE: CONCEPT]
  Content: Groth16, BN254, Poseidon(8), nPublic=5, ceremony block #41723255
  Provenance: [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

---

## Provenance Rules (enforce these — do not skip)

- Every factual claim: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]
- Measured values: [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]
- Designed (not yet measured): [VAPI:Phase166:VAPI_WHAT_IF.md:DESIGNED]
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
[CONTRADICTION: source claims X | frozen value is Y | [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]]
Write to: wiki/contradictions.md

---

## Wiki Page Format

Each page must follow this structure:

```markdown
# [Page Type]: [Entity Name]

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Current State
[factual description with provenance on each claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|
| ... | ... | [VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED] | LIVE/DESIGNED/STALE |

## Related Pages
- [[entity_1]]
- [[entity_2]]
```

---

## Source Content

# VAPI WHAT_IF — For Claude Code Context

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

**Your Role**: When reading this file, you are the risk/opportunity analyst. You must think in three recursive layers: W1 (protocol risks), W2 (novel opportunities), W3 (meta-risks to the system itself). Every proposal must be grounded, exclusive to VAPI, and phase-coherent.

> **INSTRUCTION TO CLAUDE CODE**: This file is the recursive risk/opportunity ontology for VAPI.
> When reading this file, you must:
> 1. Check W1_LAYER before proposing features (avoid known failure modes)
> 2. Reference W2_LAYER for novel opportunities (build on validated ideas)
> 3. Monitor W3_LAYER for meta-risks (protect the protection system)
> 4. Add new entries with evidence and phase candidates
> 5. Never delete entries — append-only with status updates

---

## Layer Structure

VAPI WHAT_IF operates in three recursive layers:

- **W1_LAYER**: Risks to the VAPI protocol (failure modes)
- **W2_LAYER**: Opportunities for VAPI enhancement (novel features)
- **W3_LAYER**: Meta-risks (risks to the risk system itself)

**Recursion**: W3 protects W1/W2, W1/W2 advance the protocol, protocol state feeds W3 monitoring.

---

## W1_LAYER: Known Failure Modes

> **INSTRUCTION**: Before proposing any feature, check if it addresses or respects these failure modes.

### W1-001: ioSwarm Node-Pool Homogeneity (Phase 110)

**Failure Mode**: MINT_QUORUM=0.80 trivially satisfied if all 5 nodes operated by same entity, collapsing distributed consensus to 1-party signature.

**Implication**:
- Soulbound VHP tokens minted without genuine distributed authorization
- Swarm fingerprint (SHA-256 of node_verdicts) cryptographically valid but economically meaningless
- Fail-CLOSED direction preserved, but distributed guarantee voided
- Indistinguishable from legitimate quorum on-chain

**Detection**:
- All 5 node staker_addresses identical or controlled by same entity
- Swarm fingerprint shows self-consistency, not distributed consensus
- No way to detect from on-chain data alone

**Mitigation Available**:
- ✅ VAPISwarmOperatorGate.sol: enforces minimum 3 distinct staker addresses in node pool
- ✅ Stake-weight cap: 1.5× per node prevents whale capture
- ✅ Phase 112 candidate: isSufficientlyDecentralized() as additive 5th gate on POST /agent/mint-vhp

**Status**: Code complete, deployment **BLOCKED** (wallet ~0.35 IOTX < 0.40 needed)

**Evidence**: scripts/vapi-vhp-mint-swarm-agent.json (task spec)

**First Identified**: Phase 109A (2026-03-15)

**Claude Code Guidance**: When working on ioSwarm, always check node diversity. Never enable minting without VAPISwarmOperatorGate validation.

---

### W1-002: Separation Ratio Calibration Deadline (Phase 108/129)

**Failure Mode**: Inter-person separation ratio remains <1.0 through Phase 113 if touchpad recapture hardware session indefinitely deferred.

**Implication**:
- TOURNAMENT BLOCKER persists (ratio > 1.0 is non-negotiable TGE gate)
- All 4 tournament readiness conditions unmet
- VHP minting proceeds on testnet but live tournament integration impossible
- Token launch blocked regardless of ioSwarm phase completion

**Current State**:
- Full corpus pooled: 0.417 (N=127, 3-player, 2026-03-29) — BLOCKER for free-form gameplay
- Touchpad corners (Phase 143): **1.261** (N=11, diagonal+proper LOO, 3-player, 2026-04-02) — ABOVE GATE
- Sessions captured: N=120 included (5 excluded), 3 players; P4→P3 merge confirmed (Phase 138)
- BT calibration: 0/50 sessions (separate workstream)

**Detection**:
- separation_ratio_snapshots table: touchpad_corners now logs 1.261
- 6-signal tournament readiness score: separation component now partially passing (touchpad_corners)
- Full corpus free-form still below 1.0 (0.417)

**Mitigation Available**:
- ✅ Touchpad corners already above gate (N=11 thin but real data, 3 players)
- ✅ Tournament path: capture ~19 more touchpad_corners sessions to reach N≥30
- ✅ Phase 143 proper LOO + Phase 142 diagonal auto-fallback produce honest estimate
- ⚠️ Free-form gameplay separation (0.417) still requires new probe types or players

**Status**: PARTIALLY RESOLVED — touchpad_corners ABOVE GATE (1.261, N=11 thin); free-form still BLOCKE
... [truncated — full content in VAPI-WORKFLOW.v2/VAPI_WHAT_IF.md]

---

## After Writing Pages

Run these commands in order:
  python vapi_wiki.py lint
  python vapi_wiki.py snapshot
  python vapi_wiki.py autoresearch_feed

The autoresearch_feed command syncs any wiki gaps into the AutoResearch
experiment log so the next /vapi autoresearch cycle can address them.
