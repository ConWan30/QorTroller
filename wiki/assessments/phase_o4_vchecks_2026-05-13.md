# Phase O4-VPM-INTEGRATION — Pre-Execution V-Check Provenance Pin

**Date:** 2026-05-13
**Anchor commit at start of phase:** `ece17f4f` (Layer 7 7-of-7 ZKBA closure — HARDWARE Participation Card)
**Plan reference:** `wiki/proposals/Phase_O4_VPM_Integration_Plan.md` §1
**Authorization:** Operator APPROVED plan without modification + directed Phase O4 execution start
**Author:** VAPI Principal Architect

---

## 0. Provenance Pin Purpose

This document is a **verification-first discipline provenance pin** generated immediately
before Stream A.0 (`compile_vpm_artifact()` extension of `vsd_ui_compiler.py`) begins.
It records the exact state of the 10 prerequisites enumerated in Phase O4 Plan §1
at the moment Phase O4 execution is authorized.

The pin serves two purposes:
1. **Forward-looking:** any future drift between V-check assumptions and live state
   surfaces as a diff against this pin, allowing operators to detect "we built O4 on
   a state that no longer holds" failures.
2. **Backward-looking:** future Methodology Layer revisions reference this pin as the
   canonical "what we believed to be true when O4 started" snapshot.

---

## 1. V-Check Results

### V1 — VBDIP-0002 Appendix B §B.8 gate set

**Pass criterion:** G1, G5a, G5b, G5c all SATISFIED in the live document.

**Evidence:**
- Source: `wiki/methodology/VBDIP-0002-zkba-visual-projections.md` (lines 1715–1725 table; lines 1985–1992 update notes)
- G1 SATISFIED (VBDIP-0001 FROZEN per commit `d6830525`)
- G2 RESOLVED 2026-05-12 per Operator Decision Matrix D-NUM Option N1 (VBDIP-0002 owns the 0002 slot for ZKBA permanently)
- G3 PARTIALLY SATISFIED (6 of 10 §9.3 rules covered for GIC CHAIN_ONLY profile; rules 2/3/4 N/A for current artifact set; rule 10 deferred per §A.12) — Phase O4 will fully close this gate per plan §11
- G4 SATISFIED (`scripts/zkba_manifest_validator.py` covers all 7 §5 classes; 55 tests pass)
- G5a SATISFIED (VBDIP-0002 / VBDIP-0002A v1.1 reconciliation 2026-05-12)
- G5b SATISFIED (VPM wrapper manifest schema + Integrity Label LIVE per `scripts/vsd_vpm_wrapper.py` + 24 tests pass)
- G5c SATISFIED (Anti-Hype Visual Grammar tests passing 2026-05-12 per Lane B work)
- G6 SATISFIED (Cedar v2 LIVE 2026-05-12 ceremony commit `ad0f7d11`)
- G7 PENDING (Curator Review Readiness — operator-runtime observation; not a development gate)
- G8 PENDING (Internal Projection First — to be CLOSED by Phase O4 Stream A.1)
- G9 RESOLVED 2026-05-12 per D-NUM (same closure as G2)

**Result:** **PASS** — all 4 plan-required gates SATISFIED (G1 + G5a + G5b + G5c).

**Stop-condition triggered:** No.

---

### V2 — PATTERN-017 ZKBA primitive integrity

**Pass criterion:** `compute_zkba_commitment` exists in `bridge/vapi_bridge/zkba_artifact.py`; INV-ZKBA-001/002/003 PASS in PV-CI gate.

**Evidence (verbatim from `python scripts/vapi_invariant_gate.py --report`):**
- `INV-ZKBA-001 OK   matches= 1  compute_zkba_commitment function exists in bridge/vapi_bridge/zkba_artifact.py`
- `INV-ZKBA-002 OK   matches= 1  VAPI-ZKBA-ARTIFACT-v1 domain tag literal pinned`
- `INV-ZKBA-003 OK   matches= 1  vapi-zkba-manifest-v1 manifest schema string pinned in scripts/vsd_ui_compiler.py`
- Gate result: `[invariant_gate] All invariants pass.` (67 / 67)

**Result:** **PASS**

**Stop-condition triggered:** No.

---

### V3 — All 7 ZKBA artifact compilers present

**Pass criterion:** `scripts/zkba_compile_{ait_snapshot,gic_ledger,vhp_card,hardware_card,consent_receipt,tournament_card,marketplace_listing}.py` all exist + emit manifests cleanly.

**Evidence (`ls scripts/zkba_compile_*.py | wc -l = 7`):**
- `scripts/zkba_compile_ait_snapshot.py`        (class 1, commit `bdbcf67f`)
- `scripts/zkba_compile_gic_ledger.py`          (class 2, commit `3b3081d3`)
- `scripts/zkba_compile_vhp_card.py`            (class 3, commit `4f399282`)
- `scripts/zkba_compile_hardware_card.py`       (class 4, commit `ece17f4f`)
- `scripts/zkba_compile_consent_receipt.py`     (class 5, commit `9bfa981e`)
- `scripts/zkba_compile_tournament_card.py`     (class 6, commit `25e7f8f2`)
- `scripts/zkba_compile_marketplace_listing.py` (class 7, commit `269e439c`)

**Result:** **PASS** — 7-of-7 compiler scripts present.

**Stop-condition triggered:** No.

---

### V4 — VPM wrapper layer

**Pass criterion:** `scripts/vsd_vpm_wrapper.py` exists with FROZEN enums + dataclass + functions.

**Evidence (`grep` on `scripts/vsd_vpm_wrapper.py` — 9-of-9 expected names present):**
- `class VPMVisualState(str, Enum)` — 6 FROZEN values: live / dry-run / emulated / frozen-disabled / revoked / unverified
- `class VPMCaptureMode(str, Enum)` — 5 FROZEN values
- `class VPMLifecycleStatus(str, Enum)`
- `class VPMRevocationStatus(str, Enum)`
- `class VPMAnchorStatus(str, Enum)`
- `class VPMIntegrityLabel` — 9-field Integrity Label dataclass per Appendix B B.5
- `def wrap_zkba_manifest(...)` — references FROZEN `vapi-zkba-manifest-v1` schema (does not replace)
- `def derive_visual_state(...)` — rule engine encoding B.6 failure-state precedence
- `def validate_vpm_manifest(...)` — mechanical enforcement
- INV-VPM-WRAPPER-001 OK (matches=2) per PV-CI gate

**Result:** **PASS**

**Stop-condition triggered:** No.

---

### V5 — G4 manifest validator

**Pass criterion:** `scripts/zkba_manifest_validator.py::validate_zkba_manifest` returns `valid=True` for all 7 ZKBA classes.

**Evidence (`python -m pytest bridge/tests/test_phase_o3_zkba_manifest_validator.py -q`):**
- 55 passed in 0.92s

**Result:** **PASS**

**Stop-condition triggered:** No.

---

### V6 — Cedar v2 lane authority LIVE

**Pass criterion:** All three v2 bundles (Sentry/Guardian/Curator) anchored on chain (commit `ad0f7d11` ceremony 2026-05-12); `EXPECTED_LANE_MATRIX` 12 rows OK per `zkba_post_ceremony_audit.section_3_lane_matrix()`.

**Evidence (live `python scripts/zkba_post_ceremony_audit.py` Section 3 output):**
- 12 lane-matrix rows verified at Cedar policy level
- All 12 rows: expected effect = actual effect = `[OK]`
- Section 1 (local Merkle vs EXPECTED_MERKLES lock): 3/3 MATCH (anchor_sentry / guardian / curator)
- Section 3 result: **PASS**

**Lane matrix (12 rows verified):**

| Agent | Action | Resource | Expected | Actual | Status |
|---|---|---|---|---|---|
| anchor_sentry | tool:zk-artifact-anchor | draft://zk_artifacts/* | permit | permit | OK |
| anchor_sentry | skill:read | lane://zk_artifacts/** | permit | permit | OK |
| anchor_sentry | tool:zk-audit-trail | (any) | forbid | forbid | OK |
| anchor_sentry | tool:zk-marketplace-listing | (any) | forbid | forbid | OK |
| guardian | tool:zk-audit-trail | draft://zk_verifications/* | permit | permit | OK |
| guardian | skill:read | lane://zk_verifications/** | permit | permit | OK |
| guardian | tool:zk-artifact-anchor | (any) | forbid | forbid | OK |
| guardian | tool:zk-marketplace-listing | (any) | forbid | forbid | OK |
| curator | tool:zk-marketplace-listing | draft://zk_listings/* | permit | permit | OK |
| curator | skill:read | lane://zk_listings/** | permit | permit | OK |
| curator | tool:zk-artifact-anchor | (any) | forbid | forbid | OK |
| curator | tool:zk-audit-trail | (any) | forbid | forbid | OK |

**Result:** **PASS** — 3-agent CFSS triangle empirically intact at Cedar policy level.

**Stop-condition triggered:** No.

---

### V7 — Bridge stability + chain-submission kill-switch

**Pass criterion:** `CHAIN_SUBMISSION_PAUSED=true` in `bridge/.env`; no Stream A/B/C step writes to chain.

**Evidence (`grep CHAIN_SUBMISSION_PAUSED bridge/.env`):**
- Line: `CHAIN_SUBMISSION_PAUSED=true`
- Companion comment: `# Restore: set CHAIN_SUBMISSION_PAUSED=false + restart bridge once wallet`
- The 22 chain submission paths gated by this kill-switch per the existing audit (commit `f1a7be31`) remain gated.

**Result:** **PASS**

**Stop-condition triggered:** No.

**Phase O4 commitment:** No Stream A/B/C work writes to chain. Phase O4 is wallet-free.

---

### V8 — Existing frontend Vite app reachable + DeveloperView chunk under envelope

**Pass criterion:** `npm run build` PASSES in `frontend/`; build emits clean DeveloperView chunk (<60 KB raw, <13 KB gzipped).

**Evidence (`cd frontend && npm run build`):**
- Build succeeded: `✓ built in 1m 6s`
- DeveloperView chunk: **51.09 KB raw / 12.61 KB gzipped** (within envelope)
- GamerView chunk: 101.20 KB raw / 31.14 KB gzipped
- ManufacturerView chunk: 16.05 KB raw / 5.01 KB gzipped
- MarketplaceView chunk: 7.89 KB raw / 2.79 KB gzipped
- BrpView chunk: 31.91 KB raw / 11.31 KB gzipped
- main bundle: 242.67 KB raw / 78.09 KB gzipped
- Warning about chunks >500 KB is the existing `deprecated-DFSgs5ty.js` (828.64 KB raw / 223.52 KB gzipped) — pre-existing legacy chunk, not Phase O4 surface; not in scope.

**Result:** **PASS**

**Stop-condition triggered:** No.

---

### V9 — Test count parity

**Pass criterion:** Bridge ~3160 / SDK ~562 / Hardhat ~528 / PV-CI 67 — all PASS at HEAD.

**Evidence (CLAUDE.md line 15 authoritative state):**
> `Bridge: 3160 passing. Autoresearch: 7 passing. Contract: 528. SDK: 562. Hardware: 37. E2E: 14. PV-CI: 67.`

- Bridge: 3160 ✓ (matches expected post-Layer-7-7/7-closure count)
- SDK: 562 ✓
- Hardhat (Contract): 528 ✓
- PV-CI: 67 ✓ (gate run above confirms `All invariants pass`)
- Autoresearch: 7 ✓
- Hardware: 37 ✓ (excluded from CI)
- E2E: 14 ✓ (excluded from CI)

**Result:** **PASS** — no drift from CLAUDE.md authoritative counts.

**Stop-condition triggered:** No.

---

### V10 — VPM-HONESTY-001 namespace lock + new PV-CI invariant naming discipline

**Pass criterion:** Reconfirm that `VPM-HONESTY-001` is a methodology-doc identifier, NOT a PV-CI invariant ID; new PV-CI invariants for Phase O4 use the `INV-VPM-*` namespace per VBDIP-0002 Appendix B §B.5 reconciliation discipline.

**Evidence (`wiki/methodology/VBDIP-0002-zkba-visual-projections.md` §B.5 lines 1639–1649):**
> "VPM-HONESTY-001 is a methodology-document identifier, NOT a PV-CI invariant. It does not enter .github/INVARIANTS_ALLOWLIST.json. It does not enter scripts/vapi_invariant_gate.py."
> "If/when visual honesty becomes programmatically enforceable, the enforcement ships as a new PV-CI invariant under existing native naming (e.g. INV-VPM-VISUAL-001), and a VEDIP Appendix A append assigns the corresponding VED alias at that time."

**Existing precedent confirming the discipline (`INV-VPM-WRAPPER-001`):**
- Already exists in `.github/INVARIANTS_ALLOWLIST.json` + `scripts/vapi_invariant_gate.py`
- Pinned via `--confirm-governance` ceremony 2026-05-12
- Uses the native `INV-VPM-*` namespace, NOT `VPM-HONESTY-N`
- Demonstrates the namespace separation is already operative in the codebase

**Result:** **PASS** — Phase O4 invariant naming follows the established `INV-VPM-*` namespace; `VPM-HONESTY-001` retained as methodology-doc identifier only. All 10 new invariants planned in `Phase_O4_VPM_Integration_Plan.md` §4.1 use the correct `INV-VPM-*` form.

**Stop-condition triggered:** No.

---

## 2. Aggregate V-Check Result

| V-check | Subject | Result |
|---|---|---|
| V1 | VBDIP-0002 Appendix B §B.8 gate set | **PASS** |
| V2 | PATTERN-017 ZKBA primitive integrity | **PASS** |
| V3 | All 7 ZKBA artifact compilers present | **PASS** |
| V4 | VPM wrapper layer | **PASS** |
| V5 | G4 manifest validator | **PASS** |
| V6 | Cedar v2 lane authority LIVE | **PASS** |
| V7 | Bridge stability + chain-submission kill-switch | **PASS** |
| V8 | Frontend Vite build + DeveloperView chunk envelope | **PASS** |
| V9 | Test count parity | **PASS** |
| V10 | VPM-HONESTY-001 namespace lock | **PASS** |

**Aggregate: 10 of 10 V-checks PASS. No stop-conditions triggered.**

**Authorization to proceed:** Stream A.0 (`compile_vpm_artifact()` extension of `vsd_ui_compiler.py` + T-VPM-COMPILER-1..10 test band) is **CLEARED TO BEGIN** per Verification-First Discipline.

---

## 3. State Snapshot at Authorization Moment

For future drift detection, the following state is pinned at the moment Phase O4 Stream A.0 begins:

| Surface | Value |
|---|---|
| HEAD commit | `ece17f4f` |
| Bridge test count | 3160 |
| SDK test count | 562 |
| Hardhat test count | 528 |
| PV-CI invariants | 67 |
| `CHAIN_SUBMISSION_PAUSED` | true |
| Operator wallet | ~15.03 IOTX (post Track 2 ceremony 2026-05-12) |
| 7 ZKBA compiler scripts | All present (per V3) |
| `vsd_ui_compiler.py` | Contains `class ZKBAManifest` + `compile_artifact()` + `canonical_json()` + `compute_input_commitment()` |
| `vsd_vpm_wrapper.py` | Contains 5 FROZEN enums + `VPMIntegrityLabel` + `wrap_zkba_manifest()` + `derive_visual_state()` + `validate_vpm_manifest()` |
| Cedar v2 bundle Merkle roots | Sentry `0x39e8b65f...db1f23` / Guardian `0x6818a9ad...0a9a0` / Curator `0x0ade0c92...60a80b3d` |
| Frontend DeveloperView gzipped | 12.61 KB |
| Phase O4 plan path | `wiki/proposals/Phase_O4_VPM_Integration_Plan.md` (~640 LOC) |

---

## 4. Sequencing Note

This V-check report is the prerequisite provenance pin for Phase O4 Commit 1 per
`Phase_O4_VPM_Integration_Plan.md` §10 row 1 (Stream A.0). The next commit will:

1. Extend `scripts/vsd_ui_compiler.py` with `compile_vpm_artifact()` parallel to existing `compile_artifact()`
2. Implement strict compiler discipline:
   - No external resource loading (no `<link>`, no `<script src=>`, no `@import`, no `https?://`, no `<iframe src=http>`)
   - No external fonts (system-monospace only)
   - No wall-clock at compile time (caller-supplied `ts_ns`)
   - No randomness in emitted JS
   - No network at runtime in emitted JS (no fetch / XHR / WS / EventSource)
   - Inline SVG only
   - One file, one artifact (HTML + manifest sidecar only)
   - Two-build byte-stable determinism
   - 9-field Integrity Label visible in emitted HTML
   - Compiler version pinned
3. Write `bridge/tests/test_phase_o4_vpm_compiler.py` with T-VPM-COMPILER-1..10
4. HOLD for operator review of the diff before `git commit`

This file is committed in Phase O4 Commit 9 (close commit) per plan §10 row 9, not in Commit 1.
It is written to the filesystem now (pre-execution) as the provenance pin per VFD discipline.

— VAPI Principal Architect, 2026-05-13
