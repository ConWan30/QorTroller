# CCO × PoEP Fusion v4 — Universal Presence Framework

**Document ID:** CCO-POEP-FUSION-v4  
**Version:** 4.0  
**Date:** 2026-06-19  
**Status:** Draft — verification-discipline artifact. Not an implementation spec.  
**Supersedes:** Conceptual v3 (Controller Capability Oracle strategic reframe). v2 repo-grounded corrections (Track A/B, CA fragility, corpus depth) are carried forward inside this frame.  
**Companions:**
- [`DEVICE_ID_CANON_v1.md`](DEVICE_ID_CANON_v1.md) — identity axis (`keccak256(65-byte SEC1 P-256 pubkey)`)
- [`sensor_stack_v2_1_architectural_revision.md`](sensor_stack_v2_1_architectural_revision.md) — adaptive trigger as P-T3 ceiling, not protocol floor
- [`bt_calibration_v1_1_architectural_revision.md`](bt_calibration_v1_1_architectural_revision.md) — BR/EDR transport discipline (DualSense ≠ BLE)
- `l9_presence/POEP_SCOPE.md` — PoEP mechanism, activation gates, FROZEN posture
- `l9_presence/POEP_P4_SCOPE.md` — governed activation ceremony requirements

---

## Evidence grading (mandatory for all claims)

| Grade | Meaning |
|-------|---------|
| **VERIFIED** | Confirmed in repo at cited path; behavior matches claim. |
| **BUILT** | Code or contract exists; not live in production / default-OFF. |
| **DESIGN** | Architecturally sound; not specified or wired in code. |
| **GATED** | Specified; blocked on hardware, governance, ceremony, or external dependency. |
| **[UNVALIDATED]** | Framework allows the claim; per-class empirical proof unbuilt. |

**Discipline:** No claim in this document is graded stronger than the repo demonstrates. Where v3/v4 source prose used "VERIFIED" for repurposing on-chain tiers, this document downgrades per **F-V3-001**.

---

## Executive summary

QorTroller v4 is a **two-axis attestation protocol**:

1. **Identity axis** — *who is this controller?* (software-identified, host-key cryptographic, or silicon-rooted)
2. **Presence axis** — *is a live human operating it right now?* (P-T0 reflex floor through P-T3 tournament-grade PoEP)

The **Controller Capability Oracle (CCO)** from v3 is the plug-in **input stage**: it identifies the controller, profiles its claimed signal surface, selects a challenge type, and assigns a **conservative presence ceiling**. **Proof of Embodied Presence (PoEP)** from `l9_presence/` is the **verification engine**: liveness, device-auth, freshness, and a born-PQ SHA-256 commitment.

**What the repo already has:** partial CCO Layer 1 (`controller/profiles/`, `device_registry.py`, CHIA), full PoEP candidate implementation (default-OFF), identity canon, Path A MFG registry + `VAPIProtocolLensV2`, and `VAPIPoEPRegistry` for gamer-sovereign commitment storage.

**What the repo does not have:** a unified CCO module, PoEP device-auth parameterization beyond adaptive trigger, on-chain presence-tier composability, or live activation of PoEP/L6B.

---

## 0. Strategic reframe (v3 core inversion)

| Era | Premise |
|-----|---------|
| v1/v2 | Presence derived from **specific** DualSense Edge components |
| v3 (CCO) | **Presence** is fixed; **detection method** adapts to whatever signal the controller exposes |
| v4 (fusion) | CCO resolves identity **and** capability; PoEP generalizes device-auth; both axes compose on `device_id` |

**Grade:** DESIGN (strategic frame). Partial **BUILT** precursors exist; fusion wiring is **DESIGN**.

**Load-bearing boundary (v3 §2 — preserved verbatim):**

> Intelligence can autonomously identify and profile a controller from self-description. Intelligence **cannot** autonomously validate that high-assurance presence detection works on an uncharacterized controller class without ground truth.

---

## 1. The Controller Capability Oracle (CCO)

### 1.1 Layer 1 — Identification and capability profiling

**Question answered:** *What is this controller, and what does it claim to expose?*

| Capability | Grade | Repo evidence |
|------------|-------|---------------|
| VID/PID → controller profile | **BUILT** | `controller/profiles/__init__.py` — `detect_profile(vendor_id, product_id)`; six registered profiles (Edge, DualSense, Scuf, Battle Beaver, Hori fight stick, Xbox Elite S2) |
| Declarative capability flags | **BUILT** | `controller/device_profile.py` — `has_adaptive_triggers`, IMU, touchpad, `phci_tier`, `pitl_layers`, `sensor_commitment_size_bytes` |
| Plug-in auto-detect priority chain | **BUILT** | `bridge/vapi_bridge/device_registry.py` — env override → VID/PID detect → Edge default |
| Extended PITL / tournament tier mapping | **BUILT** | `bridge/vapi_bridge/controller_hardware_intelligence_agent.py` — `CANONICAL_PROFILES`, `TournamentTier` (ATTESTED/STANDARD/FALLBACK); runs when `CONTROLLER_INTELLIGENCE_ENABLED=true` (default **true**) |
| Runtime HID report-descriptor parse | **DESIGN** | No `report_descriptor` parser in bridge or controller tree; capabilities come from **curated** manifests, not enumeration bytes |
| Agentic long-tail classifier | **DESIGN** | No descriptor-reasoning agent wired to bridge |
| Unified CCO module / single API | **DESIGN** | Logic scattered across Phase 19 + 136 + 155; no `CapabilityOracle` type |
| CCO → PoEP challenge selection | **DESIGN** | `device_auth_score()` hardcoded to `adaptive_response_detected` (`l9_presence/poep_calibration.py`) |

**Correction vs v3 prose:** Layer 1 is **not** greenfield. It is ~60–70% **BUILT** as `DeviceProfile` + registry + CHIA. Remaining work is **oracle unification** and **dynamic** descriptor handling for unknown controllers.

### 1.2 Layer 2 — Presence-method selection and tier ceiling

**Question answered:** *Given this profile, what verification method and presence ceiling are honest?*

| Capability | Grade | Repo evidence |
|------------|-------|---------------|
| Map profile → presence tier (P-T0…P-T3) | **DESIGN** | No code assigns v4 presence tiers |
| Map profile → PoEP challenge type | **DESIGN** | PoEP uses Edge force-challenge only |
| Per-class FAR/FRR for T1+ | **[UNVALIDATED]** | AIT N=37 / 3 players on Edge-class only (`CLAUDE.md`, Phase 231 fixtures); insufficient for production FAR/FRR |
| Conservative ceiling enforcement | **DESIGN** | Discipline exists in docs (Sensor Stack Stage A, PoEP P4); not enforced in CCO code |

---

## 2. Proof of Embodied Presence (PoEP)

### 2.1 Three-layer mechanism

| Layer | Proves | Grade | Repo evidence |
|-------|--------|-------|---------------|
| **Liveness** | Live human acting now | **BUILT** | `l9_presence/poep_calibration.py` — `liveness_score()`; population reflex band |
| **Device-auth** | Real certified device, not emulator/translator | **BUILT** (Edge-only) | `poep_calibration.py::device_auth_score()` — `adaptive_response_detected`; `l9_presence/poep_force.py` |
| **Freshness** | Response bound to nonce | **BUILT** | `l9_presence/poep.py` — `nonce_schedule()`, commitment includes `nonce` |

**Commitment (VERIFIED):**

```
PoEP = SHA-256(b"QORTROLLER-POEP-v0" || device_id || nonce || response_features || ts_ns)
```

- Domain tag: `l9_presence/poep.py` (`_DOMAIN = b"QORTROLLER-POEP-v0"`)
- **Not** a PATTERN-017 FROZEN-v1 family member — **GATED** governance ceremony required to register (`POEP_P4_SCOPE.md`, `scripts/vapi_invariant_gate.py` pins other families only)

### 2.2 Activation and governance status

| Item | Grade | Repo evidence |
|------|-------|---------------|
| PoEP capture + calibration code | **BUILT** | `l9_presence/poep.py`, `poep_calibration.py`, `poep_force.py`, tests |
| `poep_enabled` default False | **VERIFIED** | Not a `Config` field; `getattr(cfg, "poep_enabled", False)` in `operator_api/_app.py` |
| `L6_CHALLENGES_ENABLED` default False | **VERIFIED** | `bridge/vapi_bridge/config.py` |
| `L6B_ENABLED` default False | **VERIFIED** | `config.py`; hard rule N≥50 in `POEP_SCOPE.md` / `poep_calibration.py::_MIN_N = 50` |
| Live PoEP verdict | **GATED** | P4 seven-gate checklist (`POEP_P4_SCOPE.md`): N≥50, ≥5 players, two-key flags, governance, GIC_100, consent, chain pause |
| On-chain PoEP storage | **BUILT** (deploy-hold) | `contracts/contracts/VAPIPoEPRegistry.sol` — gamer-sovereign `poepCommitment`; bridge read-only per sovereignty rule |
| P4b device-auth advisory | **DESIGN** | `poep_verify()` still ANDs liveness ∧ device-auth for `PRESENT`; advisory posture is scope prose only |

### 2.3 PoEP seam for CCO fusion (v4)

**VERIFIED:** `device_auth_score()` is coupled to adaptive-trigger physics:

```python
# l9_presence/poep_calibration.py — pass iff adaptive_response_detected
detected = bool((device_auth or {}).get("adaptive_response_detected"))
```

**DESIGN:** CCO-parameterized `ChallengeVerifier` plugins (rumble+IMU, stick-timing, etc.) returning `UNCHARACTERIZED` until per-class measurement.

---

## 3. Identity axis (v4)

Companion: [`DEVICE_ID_CANON_v1.md`](DEVICE_ID_CANON_v1.md).

| Tier | Definition | Grade | Repo evidence |
|------|------------|-------|---------------|
| **I-0** | Software-identified; no secure element; VID/PID handle only | **DESIGN** (as v4 tier) | Commodity pads have profiles in `controller/profiles/` but no silicon sovereignty claim |
| **Path B** | Host-held key; `device_id = keccak256(65B SEC1 pubkey)` | **BUILT** | `codec.py::compute_device_id`, `HostKeyBackend`, MFG registry `signing_path=2`; demo device `581a836c…` |
| **I-1** | Silicon-rooted; same `device_id` formula from SE-exported pubkey | **GATED** | `SecureElementBackend` raises `NotImplementedError`; Path A Arc 2 hardware; HWFL-1 G1.1–G1.3 |

**Finding (identity grid precision):** v4 I-0 / I-1 does not map 1:1 to repo Path A/Path B. **Path B has cryptographic `device_id` without silicon sovereignty.** Document Path B explicitly on the grid to avoid overclaiming V.A.P.I. agency-holder status for every `keccak256(pubkey)` device.

| On-chain identity surface | Grade | Repo evidence |
|---------------------------|-------|---------------|
| `isFullyEligible(bytes32)` | **BUILT** | `VAPIProtocolLensV2.sol` — nominal ∧ eligible ∧ passport |
| `isFullyEligible_PathA(bytes32)` | **BUILT** | Lens v2 + MFG `isPathA` ∧ `isActive` — **binary**, no presence args |
| `getDeviceTier(bytes32)` | **BUILT** | MFG `proofTier` FULL/STANDARD/BASIC — **manufacturing** tier, not presence P-T0–T3 |

---

## 4. Presence axis (v3 tiers, v4 labels)

| Tier | Signal basis | Day-one autonomous? | Grade |
|------|--------------|---------------------|-------|
| **P-T0** | Reflex-band challenge-response | v3 claims YES (self-validating) | **BUILT infra, GATED policy** — see F-V3-002 |
| **P-T1** | Reflex + coarse stick/timing entropy | Only if characterized | **[UNVALIDATED]** |
| **P-T2** | Tremor + IMU micro-variance on P-T0 | Only if characterized | **[UNVALIDATED]** except partial Edge L4 corpus |
| **P-T3** | Full PoEP incl. force-response | Edge-class only; N=37/3-player insufficient | **BUILT** (Edge path); **[UNVALIDATED]** production FAR/FRR |

**Repo alignment for P-T3 ceiling:** Sensor Stack v2.1 — adaptive trigger = PRIMARY DISCRIMINATOR for L4; under v3/v4 it is the **highest presence tier**, not a protocol prerequisite.

### 4.1 Two-axis grid (composable claim target)

```
                    IDENTITY AXIS
              I-0          Path B           I-1
         (VID only)   (host keccak id)  (silicon)
              │              │              │
    ┌─────────┴──────────────┴──────────────┴─────────┐
P-T3│ NOT ACHIEVABLE   │ NOT TOURNAMENT   │ TOURNAMENT   │
    │ (no anchor)      │ GRADE*           │ GRADE        │
    ├──────────────────┼──────────────────┼──────────────┤
P-T2│ PRESENCE ONLY    │ PARTIAL STACK    │ FULL STACK   │
    ├──────────────────┼──────────────────┼──────────────┤
P-T1│ PRESENCE ONLY    │ ID + PRESENCE    │ ID + PRESENCE│
    ├──────────────────┼──────────────────┼──────────────┤
P-T0│ UNIVERSAL FLOOR  │ SOVEREIGN FLOOR  │ SOVEREIGN    │
    │                  │ (known device)   │ FLOOR        │
    └──────────────────┴──────────────────┴──────────────┘

* Path B at P-T3: identity exists but silicon sovereignty claim does not — honest
  ceiling is below I-1 × P-T3 tournament narrative.
```

**Grade for composable on-chain cell expression:** **DESIGN** — grid is architectural; on-chain API does not yet accept `(presenceTier, poepCommitment)`.

---

## 5. Verification findings (carried into this document)

### F-V3-001 — On-chain tier repurposing overstated

**Severity:** Documentation drift  
**Status:** VERIFIED mismatch  

v3 §4 stated `isFullyEligible_PathA()` + tier-multiplier infrastructure are **VERIFIED** for repurposing as presence T0–T3.

**Repo fact:** Multiple unrelated tier enums exist; none are presence T0–T3:

| Repo construct | Actual semantics |
|----------------|------------------|
| `getDeviceTier()` / MFG `proofTier` | Manufacturing class (FULL/STANDARD/BASIC) |
| `PHCITier` on `DeviceProfile` | PITL certification depth |
| `TournamentTier` in CHIA | PITL stack eligibility |
| `tier_multiplier_milli` | Marketplace listing economics |
| `isFullyEligible` / `_PathA` | Binary bool — no `presenceTier` parameter |

**Honest grade for on-chain presence tiers:** **DESIGN** (Lens v3, registry composition, or off-chain verifier + bool gate).

### F-V3-002 — T0 "day one without corpus" vs repo implementation fork

**Severity:** Architectural  
**Status:** **CLOSED** — Option C recorded in [`CCO_T0_POLICY_v1.md`](CCO_T0_POLICY_v1.md) (2026-06-19)  

v3 claims P-T0 reflex-band is self-validating per session and grantable without corpus.

**Repo has three reflex paths:**

| Path | Per-session logic? | Corpus / N≥50 gate? | Grade |
|------|-------------------|---------------------|-------|
| **Bridge L6B** (`bridge/controller/l6b_reflex_analyzer.py`) | **YES** — 80–280 ms involuntary accel reflex; `HUMAN`/`BOT`/`INCONCLUSIVE` | Operator hard rule: `L6B_ENABLED=false` until N≥50 calibration | **BUILT** analyzer; **GATED** activation |
| **PoEP de-risk** (`l9_presence/poep_derisk.py`) | **YES** — voluntary band 120–450 ms | Standalone hardware script; not production gate | **BUILT** de-risk only |
| **PoEP P2 liveness** (`poep_calibration.py`) | **NO** — population band from enrollment | `_MIN_N = 50` before `liveness_pass` | **BUILT** with population model |

**Operator decision (recorded 2026-06-19): Option C — split verdict types**

| Option | Description | Status |
|--------|-------------|--------|
| **(A) L6B per-session T0** | CCO P-T0 routes to `L6bReflexAnalyzer` | Not selected |
| **(B) PoEP population fork** | Keep PoEP `liveness_score()` for all tiers | Not selected |
| **(C) Split verdict types** | **L6B → `REFLEX_OBSERVED` (P-T0)**; **PoEP bundle → `PRESENT` (P-T2/T3)** | **SELECTED** — see `CCO_T0_POLICY_v1.md` |

Phase A oracle contract scoped in [`CCO_PHASE_A_ORACLE_CONTRACT_v1.md`](CCO_PHASE_A_ORACLE_CONTRACT_v1.md); bridge code **held** until silicon status or demand-side pilot.

### F-V4-003 — Path B on identity grid

**Severity:** Conceptual precision  
**Status:** VERIFIED  

Path B devices have `keccak256(pubkey)` identity (**BUILT**) but are not silicon-sovereign (**I-1 GATED**). Grid and partner language must not collapse them.

---

## 6. CCO maturity matrix (repo-verified)

| Capability | v3 prose | Repo-verified grade | Notes |
|------------|----------|---------------------|-------|
| HID/USB VID/PID identification | BUILDABLE NOW | **BUILT** | `controller/profiles/` |
| Capability database | BUILDABLE NOW | **BUILT** | Six profiles + CHIA `CANONICAL_PROFILES` |
| Runtime HID descriptor enumeration | BUILDABLE NOW | **DESIGN** | Curated manifests only |
| Agentic long-tail classifier | BUILDABLE NOW | **DESIGN** | Zero production code |
| CCO unified oracle API | — | **DESIGN** | Phase A deliverable |
| P-T0 reflex floor, day one | BUILDABLE (L6B) | **BUILT infra, GATED activation** | F-V3-002 **CLOSED** Option C |
| P-T1–P-T3 per controller class | RESEARCH | **[UNVALIDATED]** | Edge partial only |
| PoEP three-layer engine | — | **BUILT** | Edge device-auth only |
| PoEP device-auth generalization | — | **DESIGN** | CCO-parameterized verifiers |
| Identity canon `keccak256(pubkey)` | — | **VERIFIED** | `DEVICE_ID_CANON_v1.md`, `codec.py` |
| Silicon Path A identity | — | **GATED** | `SecureElementBackend` stub |
| On-chain presence tier expression | VERIFIED repurpose | **DESIGN** | F-V3-001 |
| `VAPIPoEPRegistry` commitment storage | — | **BUILT** | Separate from Lens eligibility |
| DePIN characterization flywheel | GATED | **BUILT** module, **GATED** run | `bcc_enabled=False` in `l9_presence/witness_agent.py` |
| PoEP FROZEN-v1 registration | — | **GATED** | Governance ceremony per P4b |

---

## 7. Fusion architecture (target state — DESIGN)

```
PLUG-IN EVENT
      │
      ▼
┌─────────────────────────────────────────────────────┐
│ CCO Layer 1 — BUILT partial / DESIGN unified         │
│ VID/PID + DeviceProfile/CHIA → capability_vector    │
│ Identity: I-0 | Path B | I-1 (from MFG/signing_path)│
│ Presence ceiling: P-T0 … P-T3 (conservative)        │
│ Challenge type: Edge force | rumble+IMU | …         │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ PoEP Engine — BUILT (Edge); DESIGN (generalized)    │
│ Liveness   ← Option C: L6B T0 / PoEP T2–T3 (CLOSED)  │
│ Device-auth ← CCO challenge_type                     │
│ Freshness  ← nonce (VERIFIED)                       │
│ Commitment ← QORTROLLER-POEP-v0 (candidate)          │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│ Composable claim — DESIGN on-chain today             │
│ Target: (deviceId, presenceTier, poepCommitment)    │
│ Today: isFullyEligible* binary + VAPIPoEPRegistry   │
└─────────────────────────────────────────────────────┘
```

---

## 8. DePIN characterization flywheel (v3 §5)

**Grade:** **BUILT** harvester architecture; **GATED** operation (`bcc_enabled=False`).

As controllers appear on the network, the flywheel accumulates **per-class characterizations and proofs**, not raw biometrics (φ-sanitization; BCC in `l9_presence/`). Open-source overlay (joypad-os / Track B) is supply-side; CCO is profiling; measurement earns T1+.

**Honesty:** Flywheel is **designed**, not **running**.

---

## 9. Track discipline and carried-forward caveats

| Caveat | Grade |
|--------|-------|
| **Track A** (Edge + bridge @ ~1002 Hz, AIT ratio 1.199, testnet) independent of CCO fusion | **VERIFIED** |
| **Track B** (overlay, dev-kit, CCO×PoEP) future capability | **DESIGN** |
| MFG CA single-copy LIVE-FRAGILE (F-DECON-3.2); OA-4 HSM migration | **VERIFIED** |
| Demand side: no live operator requires `isFullyEligible()` | **VERIFIED** (operational) |
| Corpus depth: 3-player / ~37-session AIT insufficient for production FAR/FRR on one class | **VERIFIED** |
| PoEP not live: `poep_enabled` / `L6_CHALLENGES_ENABLED` default False; P4 gates | **VERIFIED** |
| 228-byte PoAC FROZEN — PoEP parallel only | **VERIFIED** |
| BR/EDR vs BLE: DualSense transport is BR/EDR (`bt_calibration_v1_1`); ESP32 dev-kit is BLE | **VERIFIED** |

---

## 10. Execution path (verification-first)

Each phase requires **V-checks** before implementation and **P-checks** after. No phase implies live PoEP or lifts `CHAIN_SUBMISSION_PAUSED` unless explicitly gated.

### Phase A — Unify CCO (bridge-only, no biometric activation)

**Goal:** Single `CapabilityReport` from existing profile stack.

**Reuse:** `detect_profile()`, CHIA enrichment, MFG `signing_path` when available.

**Contract (scoped 2026-06-19):** [`CCO_PHASE_A_ORACLE_CONTRACT_v1.md`](CCO_PHASE_A_ORACLE_CONTRACT_v1.md) — full `CapabilityReport` field set + six-profile V-check table.

**Deliverable (DESIGN → BUILT, code held):** `CapabilityOracle.resolve(vid, pid) → CapabilityReport`.

**V-check:** Six registered profiles + unknown VID — see oracle contract §V-check.

**Does not:** Issue `PRESENT` or `REFLEX_OBSERVED` verdicts; activate PoEP or L6B; claim T1+ for uncharacterized classes.

**Hold:** No bridge module until silicon status confirmed or demand-side pilot materializes.

### Phase B — T0 policy decision (operator gate)

**Status:** **COMPLETE** (2026-06-19)

**Deliverable:** [`CCO_T0_POLICY_v1.md`](CCO_T0_POLICY_v1.md) — Option C (L6B for P-T0, PoEP for P-T2/T3 bundle).

**Unblocks:** Phase A contract; Phase C PoEP wiring still blocked on Phase A code + characterization.

### Phase C — PoEP device-auth parameterization (`l9_presence` only)

**Goal:** `ChallengeVerifier` protocol; Edge verifier = regression parity with current `adaptive_response_detected`.

**Deliverable:** Stubs for non-Edge verifiers returning `UNCHARACTERIZED` (never `PRESENT` at T1+).

**V-check:** All `test_poep_calibration.py` pass unchanged for Edge fixtures.

### Phase D — Wire CCO → PoEP (dormant)

**Goal:** Bridge passes `CapabilityReport` into PoEP session runner.

**Gates:** `poep_enabled=False` unchanged; no FROZEN-v1 edit without ceremony.

### Phase E — Identity grid documentation and session surfacing

**Goal:** Expose `{identity_class, presence_ceiling_candidate, signing_path, path_a_eligible}` on session status alongside existing Path A fields (`operator_api` already surfaces `signing_path`, `path_a_eligible` — **BUILT** partial).

**Extend (DESIGN):** `presence_ceiling_candidate` read-only field.

### Phase F — On-chain composability (deploy-hold)

**Goal:** Minimal composition before full Lens v3.

**Option F1 (smaller):** Off-chain verifier + `VAPIPoEPRegistry` view helper; Lens bool sub-check optional.

**Option F2 (v4 full):** Lens v3 with `presenceTier` enum — contract change + PV-CI ceremony.

**Gates:** Operator GO; deploy-hold; governance if new FROZEN family.

### Phase G — Empirical research program (v3 §7)

**Goal:** Characterize **three** controller classes (minimal pad / mid-tier / Edge) before "universal" partner language.

**Grade:** **[UNVALIDATED]** until complete. T0 may scale without per-class corpus **only if** Phase B selects per-session T0 and operator lifts activation gates.

---

## 11. Verification checklist (pre-implementation)

Use this checklist at the start of any CCO×PoEP implementation session:

- [ ] `DEVICE_ID_CANON_v1.md` still authoritative for `keccak256(65B SEC1)` — **VERIFIED** as of 2026-06-19
- [ ] `device_auth_score()` still hardcoded to `adaptive_response_detected` — **VERIFIED**
- [ ] `poep_enabled` / `L6_CHALLENGES_ENABLED` / `L6B_ENABLED` still default False — **VERIFIED**
- [ ] `QORTROLLER-POEP-v0` still absent from PATTERN-017 gate — **VERIFIED**
- [ ] `isFullyEligible_PathA(bytes32)` still binary — **VERIFIED**
- [x] F-V3-002 T0 policy decision recorded by operator — **CLOSED** Option C (`CCO_T0_POLICY_v1.md`)
- [ ] Track A work not conflated with Track B CCO scope — operator discipline
- [ ] No partner claim of T1+ on uncharacterized controller class — **[UNVALIDATED]** guard

---

## 12. One-paragraph partner summary (graded)

QorTroller's **Controller Capability Oracle** (partially **BUILT** via `controller/profiles/` and CHIA) identifies controllers on plug-in and assigns a **conservative presence ceiling**; it does not substitute measurement for high-assurance tiers (**DESIGN** Layer 2). **Proof of Embodied Presence** is **BUILT** in `l9_presence/` but **GATED** from live use (default-OFF, N≥50, P4 ceremony). The **fusion** (**DESIGN**) generalizes PoEP device-auth beyond the adaptive trigger and composes **identity** (`keccak256(pubkey)`, Path B **BUILT**, I-1 **GATED**) with **presence** tiers P-T0–P-T3. **On-chain presence tiers are not yet repurposable** from existing MFG/PHCI enums (**F-V3-001**). **P-T0** routes to **L6B** per-session `REFLEX_OBSERVED`; **P-T2/T3** routes to **PoEP** `PRESENT` — **Option C** (**F-V3-002 CLOSED**). The protocol's honest promise: universal **identification** and a **conservative floor**; tournament-grade and high-biometric claims are **earned by measurement**, not asserted from the HID descriptor alone.

---

## Document history

| Date | Change |
|------|--------|
| 2026-06-19 | Initial draft from v3 + v4 verification passes; F-V3-001, F-V3-002, maturity matrix; Phase A–G path; T0 fork documented as open |
| 2026-06-19 | F-V3-002 closed Option C; Phase B complete; Phase A oracle contract scoped; code hold documented |
