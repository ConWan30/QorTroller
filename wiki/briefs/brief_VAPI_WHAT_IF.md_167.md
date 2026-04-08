# VAPI Wiki Ingest Brief
Source: VAPI_WHAT_IF.md | Phase 167 | 2026-04-08T01:45:17.988852+00:00
Provenance: [VAPI:Phase167:VAPI_WHAT_IF.md:MEASURED]

## INSTRUCTION TO CLAUDE CODE
You are reading this brief to generate wiki pages. No API is called.
You are the intelligence layer. This engine handles file I/O only.

For each page listed below:
1. Read the source content at the bottom
2. Write the page to the path shown
3. Before writing: python vapi_wiki_engine.py check "<key sentences>"
4. After writing all pages: python vapi_wiki_engine.py snapshot --anchor

## Pre-Scan
Invariant violations in source: 1
  [WARN] EPISTEMIC: Threshold 0.65 (Phase 147). Cannot regress.

Metrics extracted:
{
  "separation_ratio": "0.417",
  "bridge_tests": "1910",
  "sdk_tests": "285",
  "agents": "15",
  "phase": "110"
}

Domains:
{
  "phase_state": true,
  "separation_ratio": true,
  "agents": true,
  "l4_calibration": true,
  "what_if": true,
  "privacy": true,
  "zk_circuit": true,
  "sweep": true
}

## Pages To Create

- wiki/phases/phase_167.md [TYPE: PHASE]
  [VAPI:Phase167:VAPI_WHAT_IF.md:MEASURED]
- wiki/concepts/separation_ratio.md [TYPE: CONCEPT]
  [VAPI:Phase167:VAPI_WHAT_IF.md:MEASURED]
- wiki/entities/agent_fleet.md [TYPE: ENTITY]
  [VAPI:Phase167:VAPI_WHAT_IF.md:MEASURED]
- wiki/entities/l4_thresholds.md [TYPE: ENTITY]
  [VAPI:Phase167:VAPI_INVARIANTS.md:FROZEN]
- wiki/what_if/ entries [TYPE: WHAT_IF]
  [VAPI:Phase167:VAPI_WHAT_IF.md:MEASURED]

## Provenance Rules
Every factual claim: [VAPI:Phase167:VAPI_WHAT_IF.md:MEASURED]
Frozen constants: [VAPI:Phase167:VAPI_INVARIANTS.md:FROZEN]
Designed (not measured): [VAPI:Phase167:VAPI_WHAT_IF.md:DESIGNED]
No provenance: tag [NEEDS_PROVENANCE]

## Frozen Values (never modify in wiki)
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
  "separation_gate": "0.70",
  "adjudication_registry": "0x44CF981f46a52ADE56476Ce894255954a7776fb4"
}

## Page Format
```markdown
# [TYPE]: [Entity Name]

[VAPI:Phase167:VAPI_WHAT_IF.md:MEASURED]

## Current State
[description — cite provenance on every factual claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|

## Related Pages
- [[entity_1]]
```

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
- Full corpus pooled: 0.417 (N=12
... [truncated — see VAPI_WHAT_IF.md for full content]

## After Writing
python vapi_wiki_engine.py snapshot --anchor
python vapi_wiki_engine.py sync_what_if
python vapi_wiki_engine.py autoresearch_feed
