# VAPI Wiki Ingest Brief
Source: VAPI_MEMORY.md | Phase 177 | 2026-04-09T04:25:27.847045+00:00
Provenance: [VAPI:Phase177:VAPI_MEMORY.md:MEASURED]

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
  "separation_ratio": "0.474",
  "bridge_tests": "1942",
  "sdk_tests": "301",
  "agents": "12",
  "phase": "166"
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

- wiki/phases/phase_177.md [TYPE: PHASE]
  [VAPI:Phase177:VAPI_MEMORY.md:MEASURED]
- wiki/concepts/separation_ratio.md [TYPE: CONCEPT]
  [VAPI:Phase177:VAPI_MEMORY.md:MEASURED]
- wiki/entities/agent_fleet.md [TYPE: ENTITY]
  [VAPI:Phase177:VAPI_MEMORY.md:MEASURED]
- wiki/entities/l4_thresholds.md [TYPE: ENTITY]
  [VAPI:Phase177:VAPI_INVARIANTS.md:FROZEN]
- wiki/what_if/ entries [TYPE: WHAT_IF]
  [VAPI:Phase177:VAPI_MEMORY.md:MEASURED]

## Provenance Rules
Every factual claim: [VAPI:Phase177:VAPI_MEMORY.md:MEASURED]
Frozen constants: [VAPI:Phase177:VAPI_INVARIANTS.md:FROZEN]
Designed (not measured): [VAPI:Phase177:VAPI_MEMORY.md:DESIGNED]
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

[VAPI:Phase177:VAPI_MEMORY.md:MEASURED]

## Current State
[description — cite provenance on every factual claim]

## Key Values
| Field | Value | Provenance | Status |
|-------|-------|-----------|--------|

## Related Pages
- [[entity_1]]
```

## Source Content
# VAPI MEMORY — For Claude Code Context

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

**Your Role**: When reading this file, you are the institutional memory of VAPI. You must remember what worked, what failed, and why. Never repeat failed experiments. Always build on validated patterns. Add your own learnings after each session.

> **INSTRUCTION TO CLAUDE CODE**: This file is the compounding learning log of VAPI development.
> When reading this file, you must:
> 1. Read recent entries (last 5-10) before proposing changes
> 2. Avoid repeating failed experiments (marked FAILED below)
> 3. Build on successful patterns (marked PATTERN)
> 4. Add new entries after significant discoveries or failures
> 5. Append-only — never delete historical entries

---

## 1. Session Outcomes (Chronological, Newest First)

### 2026-04-07: Phases 166-168 COMPLETE — Wiki Engine v3 + Bootstrap CI Integration

**Phase 166** (mixed_biometric_probe + configurable defensibility gate):
- `mixed_biometric_probe` added to STRUCTURED_PROBE_TYPES + _TERMINAL_CAL_ONLY_TYPES.
- `min_separation_ratio:float=0.70` config replaces hardcoded 1.0 gate (hardware variance ceiling).
- Bridge 1942->1950 +8; SDK 301->305 +4; Hardhat 468.

**Phase 167** (Wiki Engine Integration Validation + 4 hardening mitigations):
- 7 integration points validated: status/check/brief/agent_feed/sync_what_if/snapshot/phase_close.
- 4 fixes: schema probe `_probe_db_schema()`; CLAUDE.md-first phase detection; OS file lock `_locked_append()`; EPISTEMIC regex extended to catch 0.60-0.64 range.
- Bridge 1950 unchanged; SDK 305 unchanged.

**Phase 168** (Bootstrap CI in separation_ratio_snapshots):
- `separation_ratio_snapshots` +3 columns: ci_lower/ci_upper/n_bootstrap (idempotent ALTER TABLE).
- `analyze_interperson_separation.py`: bootstrap CI computed BEFORE write_snapshot so CI persists in DB row.
- `operator_api.py`: GET /agent/separation-defensibility-status +ci_lower/ci_upper/n_bootstrap.
- `vapi_wiki_engine.py`: agent_feed fixed (was querying non-existent `stratified_estimate` column, now `bt_strat_ratio`); CI annotation in wiki page when n_bootstrap>0.
- `SeparationRatioResult` +3 slots; `VAPISeparationStatus.get_status()` populates CI from API.
- 8 bridge + 4 SDK tests. Bridge 1950->1958 +8; SDK 305->309 +4; Hardhat 468 unchanged.

**Counts**: Bridge 1958 | SDK 309 | Hardhat 468 | Tools 122 | Agents 22

---

### 2026-04-05: Phase 165 COMPLETE — WIF-024 Post-Erasure Separation Ratio Recompute

**Phase 165 implementation** (WIF-024 closure):
- `anonymize_device_records()` gains `post_erasure_recompute:bool=False` parameter. When True: snapshots current separation ratio into `post_erasure_ratio_log` before erasure, sets `recompute_needed=1`, `ratio_after=NULL` (pending re-analysis via `analyze_interperson_separation.py`).
- `post_erasure_ratio_log` table: device_id/n_anonymized/ratio_before/ratio_after/recompute_needed/triggered_by/consent_type/recompute_ts/created_at.
- GET /agent/separation-defensibility-status: +`post_erasure_recomputed_at` field.
- GET /agent/post-erasure-recompute-status (7 keys): consent_ledger_enabled/total_recomputes/pending_recomputes/latest_recompute_ts/latest_ratio_before/recompute_nee
... [truncated — see VAPI-WORKFLOW.v2/VAPI_MEMORY.md for full content]

## After Writing
python vapi_wiki_engine.py snapshot --anchor
python vapi_wiki_engine.py sync_what_if
python vapi_wiki_engine.py autoresearch_feed
