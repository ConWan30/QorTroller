# MLGA v1: Mythos Live Gameplay Audit — Architectural Proposal

**Version:** 1.0
**Date:** 2026-05-15
**Status:** Draft. Engineering implementation begins after this document exits draft state.
**Authoring basis:** Operator directive 2026-05-15 — "brainstorm this novel conveying aspect into a real use case that could benefit VAPI Architectural foundation and infrastructure going forward. Or even be incorporated as a way to unblock any hardware sessions thats currently in place."
**Canonical anchors referenced:**
- `wiki/methodology/bt_calibration_v1_1_architectural_revision.md` (BT transport ground truth)
- `wiki/methodology/sensor_stack_v2_1_architectural_revision.md` (DualSense Edge sensor stack)
- `wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf`
- `wiki/assessments/DualSense Edge Sensor-Stack Characterization for VAPI Track-1 Anti-Cheat Feature Architecture.pdf`
- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md` (VAD discipline)
- `lessons.md` — `BT-CALIB-LESSON-001` (transport verification rule)

## Section 0 — Executive Summary

The DualSense Edge dual-connection topology — USB-C to the bridge laptop AND Bluetooth Classic BR/EDR to the PS5 — produces a structurally unique capture surface: the bridge sees the 1000 Hz HID stream **for free during live PS5 gameplay**, without requiring PS5 cooperation, without staging dedicated capture sessions, without disrupting the player's actual game.

This proposal designs **Mythos Live Gameplay Audit (MLGA)**: a real-time, audit-disciplined capture-and-dataproof pipeline that piggybacks on natural gameplay to:

1. **Unblock three currently-stalled hardware-capture campaigns** without requiring weeks of dedicated capture sessions:
   - Phase 243-SS2 Stage-A: adaptive trigger force-curve (target N=10 players × 100 pulls × 3 contexts)
   - Phase 242-BT Stage 2: σ_RSSI held-vs-placed (target N≥5 sessions × ≥30s per condition per player)
   - Phase 229+ AIT corpus growth (current N=37; growth helps separation_ratio stability)
2. **Persist each gameplay session as a cryptographic dataproof** anchored to existing PATTERN-017 + GIC chain primitives (no new commitment family; reuses the 8th capability-tag slot per the POSEIDON-BN254-AS reframe precedent).
3. **Audit live capture in real time via a 9th Mythos variant** — `mythos_live_gameplay_audit` — that surfaces HID stream drift, APOP classifier health, sensor saturation, and live state markers.

The novelty is **not** new transport, new feature, or new commitment family. The novelty is **methodological**: turning ambient gameplay into auditable calibration captures via the existing protocol's safety surfaces (PV-CI invariants, FSCA contradiction rules, Mythos finding-log, GIC chain).

MLGA v1 claims: passive session-bound capture + audit + dataproof. MLGA v1 does NOT claim: replacement of dedicated Stage-A measurement campaigns where lab-controlled conditions matter (the v1.1 BT calibration anchor explicitly requires controlled low-WiFi-interference σ_RSSI baseline; MLGA augments that corpus, doesn't replace it).

## Section 1 — Transport Verification Block (BT-CALIB-LESSON-001 application)

Per the application rule established by BT-CALIB-LESSON-001, any architectural proposal naming protocol-layer features for a controller transport must include a transport-verification block citing sources from at least three independent classes (upstream OS driver, reverse-engineering project, field confirmation) before exiting draft state.

### Channel A — USB-HID-over-USB (laptop side)

Three independent verification sources confirm DualSense Edge USB-HID transport at 1000 Hz polling:

1. **Upstream OS driver:** Linux `drivers/hid/hid-playstation.c` (Roderick Colenbrander, mainlined Linux 5.12, April 2021) registers DualSense Edge via `HID_USB_DEVICE(USB_VENDOR_ID_SONY, USB_DEVICE_ID_SONY_PS5_CONTROLLER_2)`. USB transport binds to USB interface 3 for biometric/IMU reports.
2. **Reverse-engineering project:** pydualsense (Python wrapper around hidapi) confirms 1000 Hz polling rate on USB-C with HID report 0x31 (full-feature input report including IMU + adaptive trigger force + touchpad + battery state).
3. **Field confirmation:** Phase 49 USB polling validation reported 1002 Hz observed rate with 14,000× injection margin (`CLAUDE.md` header: "USB polling: 1002 Hz. Injection margin: 14,000× (accel), 10,000× (gyro).").

USB transport: **verified**.

### Channel B — Bluetooth Classic BR/EDR with HIDP (PS5 side)

Verification block already established in `lessons.md` entry `BT-CALIB-LESSON-001`. Re-confirmed for this proposal:

1. **Upstream OS driver:** Linux `hid-playstation.c` uses `HID_BLUETOOTH_DEVICE(...)` macro for BR/EDR HIDP transport.
2. **Reverse-engineering project:** Bluepad32 + BlueRetro (Hackaday.io project 170365) both confirm "PS5 DualSense is still BR/EDR (BT classic)."
3. **Field confirmation:** FreeBSD Forums thread 80786 — pairing succeeds on BR/EDR adapter, fails on BLE-only.

BT transport: **verified BR/EDR with HIDP** (not BLE/HOGP). MLGA does NOT name any BLE-derived primitive (no advertising interval, no GATT events, no connection_interval_jitter). All wireless-side features derive from the BR/EDR primitive set (Tpoll, AFH, HCI Read_RSSI, L2CAP/baseband ARQN/SEQN).

### Channel C — Dual-connection simultaneity

The dual-connection topology requires that the controller publishes input over BOTH channels simultaneously. Confirmed by:

1. **Upstream OS driver:** `hid-playstation.c` runs as a single device-state handler regardless of transport; input reports flow through both channels concurrently when both are connected.
2. **Sony official documentation:** DualSense Edge UI confirms "wireless to console / wired to PC" simultaneous mode is supported (per PS5 system menu controller settings).
3. **Field confirmation:** Phase O0 baseline tests verified that with USB-C plugged into the bridge laptop AND BT paired to PS5, the laptop hidapi sees the full 1000 Hz stream while NCAA CFB 26 receives inputs via BT.

Dual-connection: **verified**.

**The dual-connection invariant for MLGA v1:** Player gameplay against the PS5 is observable at the bridge laptop's HID interface at 1000 Hz, with no PS5 cooperation required, no staged capture session required, and no game disruption.

## Section 2 — Feature Derivation Against the Verified Transports

Per BT-CALIB-LESSON-001 application rule: features derived from wire formats, not use cases. The features MLGA v1 derives are all already-existing protocol-layer primitives — MLGA collects + audits them rather than inventing new ones.

### Channel A features (USB-HID; already operational)

The bridge already extracts these at 1000 Hz via `BiometricFeatureExtractor` in `dualshock_integration.py`. MLGA observes them passively:

| Feature | Source | Existing phase | MLGA action |
|---|---|---|---|
| `trigger_onset_velocity_l2`, `_r2` | HID adaptive-trigger force readout | Phase 49 (FFT window expanded 513→1025) | Capture for Phase 243-SS2 Stage-A export |
| `accel_tremor_peak_hz` | accel-magnitude FFT (4-15 Hz, parabolic interp) | Phase 205 / Phase 213 (4096-pt zero-padded) | Capture for Phase 229 AIT corpus export |
| `micro_tremor_accel_variance`, `tremor_band_power` | IMU during still-hold | Phase 17 | Audit IMU coverage during gameplay |
| `stick_autocorr_lag1`, `_lag5` | right_stick_x ring | Phase 17 | Audit stick activity classification |
| `touch_position_variance` | touchpad capacitive 12-bit X/Y | Phase 17 | Audit touchpad coverage |
| `press_timing_jitter_variance` | IBI deques (Cross/L2/R2/Triangle) | Phase 57 | Audit timing health |
| `trigger_active` | binary onset gate | Phase 235-GAD | Drives APOP classification + GIC chain |

### Channel B features (BT BR/EDR; v1.1 anchor-derived; PROVISIONAL)

The bridge laptop has a USB BT dongle (the v1 LAN-tower witness hardware per `bt_calibration_v1_1_architectural_revision.md` §4). When that dongle is present + BlueZ-attached + the DualSense Edge is BT-paired to PS5 in line-of-sight, MLGA can opportunistically observe the BR/EDR link state:

| Feature | Source | v1.1 status | MLGA action |
|---|---|---|---|
| `rssi_variance_normalized` | HCI Read_RSSI per ACL link | PRIMARY discriminator | Capture for Phase 242-BT Stage 2 σ_held-vs-placed export |
| `tpoll_variance` | poll-interval at witness HCI socket | CO-SIGNAL (empirical unknown) | Capture; surface to operator for Stage 2 |
| `afh_normalized_retransmission_rate` | L2CAP/baseband counters | CO-SIGNAL (interference-dominated) | Capture; surface to operator for Stage 2 |

**Critical scope discipline:** Channel B is PROVISIONAL on the BT dongle being present + configured on the bridge laptop. When absent, MLGA still operates fully on Channel A and emits a finding noting Channel B unavailable. Channel A is the load-bearing capture surface; Channel B is opportunistic.

### Channel C feature (audit-layer; new)

`gameplay_session_dataproof` — the MLGA capability commitment binding all observations from a single gameplay session into one cryptographic record:

```
MLGA_SESSION_DATAPROOF = SHA-256(
    b"VAPI-MLGA-SESSION-v1"             ‖   13-byte domain tag
    session_start_ts_ns_be(8)           ‖
    session_end_ts_ns_be(8)             ‖
    n_poac_records_be(8)                ‖
    n_trigger_pulls_r2_be(4)            ‖
    n_trigger_pulls_l2_be(4)            ‖
    apop_classification_summary_b32     ‖   SHA-256 of canonical-JSON sorted APOP state counts
    bt_observability_byte               ‖   0x00=no BT / 0x01=BT seen / 0x02=BT held-placed identified
    gic_advances_in_session_be(4)
)
```

= 78-byte preimage → 32-byte output. NOT an 11th PATTERN-017 commitment family (count stays 10 + 1 PHYSICAL_DATA_ATTESTATION per the Mythos-Crypto empirical correction); MLGA is a **capability tag** per the POSEIDON-BN254-AS reframe precedent.

## Section 3 — Threat Anchor: Calibration Bottleneck, NOT Cheat Detection

The v1.1 BT calibration anchor narrowed its threat surface from "spatial co-presence attestation" (broad prior art) to "cloud-gaming-bot stealth pattern" (specific documented attack class). MLGA does an analogous narrowing — but its threat surface is **not** a cheat class. MLGA's threat anchor is **the calibration bottleneck itself**.

The three concrete VAPI-internal "threats" MLGA addresses:

1. **Stage-A capture-session scheduling overhead.** Phase 243-SS2 requires N=10 players × 100 trigger pulls × 3 game contexts. At dedicated-capture pace (~30 min per player per context), this is 15 hours of staged capture. Cannot be expedited by engineering.
2. **σ_held-vs-placed empirical-unknown gap.** Phase 242-BT v1.1 §5 lists this as Empirical Unknown #1; the entire Stage 2 measurement campaign exists to resolve it. Requires controlled RF environment + ≥5 sessions per condition per player.
3. **AIT corpus growth stall.** Phase 229 corpus at N=37 (P1=13/P2=10/P3=14); separation_ratio=1.199 cleared the AIT defensibility gate but stability under N growth is desirable. Currently no organic growth path.

MLGA's threat-model claim is: these three "threats" are **systemically expensive** because dedicated capture sessions consume operator-runtime that scales poorly. The dual-connection topology routes around this by re-using ambient gameplay as the capture surface.

**MLGA does NOT claim** to detect any cheat class, replace any existing L0–L8 layer, or substitute for the lab-controlled measurements where lab control matters (e.g., Phase 242-BT Stage 2's controlled low-WiFi-interference σ_RSSI baseline). MLGA **augments** the corpora; it does not certify them.

## Section 4 — Novelty Claim Split: Capture-Pipeline Layer vs. Audit Layer

Following the v1.1 BT calibration's discipline of splitting novelty claims to prevent equivocation:

### Capture-Pipeline Layer (engineering convenience; not a security property)

The dual-connection topology + 1000 Hz HID capture during live gameplay is **engineering convenience**, not protocol novelty. Other systems could replicate this with the same hardware setup. The capture pipeline alone does not constitute a defensible novelty claim.

### Audit Layer (Mythos discipline + cryptographic dataproof; novel)

What IS novel is the integration with VAPI's existing audit + dataproof discipline:

1. **Mythos-Live-Gameplay variant** runs in real time during gameplay. Findings persist to `mythos_finding_log` with the same `frozen_region` discipline that protects PV-CI invariants and Cedar bundle Merkles. Drift in the capture stream surfaces as Mythos findings within one cadence window (60s default).
2. **MLGA_SESSION_DATAPROOF commitment** binds each session's observations into a single 32-byte commitment that is FROZEN-v1 schema-pinned (INV-MLGA-DATAPROOF-PREIMAGE-001) and chainable across sessions via GIC pattern reuse. Each dataproof is independently verifiable by anyone with the canonical-JSON algorithm + SHA-256 + the session's recorded inputs.
3. **3-layer cross-verification with PV-CI:** the Mythos-Crypto variant verifies MLGA's domain tag is registered in `_KNOWN_CAPABILITY_TAGS`; the Mythos-Frozen variant verifies INV-MLGA-* invariants pass; the Mythos PR gate enforces both on every PR. Bundle a session's capture without the dataproof commitment → Mythos rejects it.

This 3-layer discipline distinguishes MLGA from naive "log every gameplay session" approaches. The dataproof is **cryptographically verifiable** post-session and **drift-detected** in real-time.

## Section 5 — Empirical Unknowns: Pre-Stage 1 Measurement Required

Per the v1.1 BT calibration anchor's discipline, MLGA v1 must resolve these empirical unknowns before exiting draft state:

1. **Gameplay duration distribution per NCAA CFB 26 session.** Is the median session 30 min, 2 hours? This determines reasonable MLGA cadence (60s? 300s? per-session?). Hypothesized: ≥45 min median for competitive play.

2. **Per-session R2 pull rate during live NCAA CFB 26 gameplay.** R2 is the canonical sprint trigger (game-aware profiling per Phase 51). If players average <50 R2 pulls per session, Phase 243-SS2 Stage-A target N=100 per player × 3 contexts requires 6 sessions per player minimum. If ≥200, 2 sessions per player covers it.

3. **Sensor saturation rate during gameplay.** What fraction of frames see touchpad activity vs. dormant? IMU activity vs. dormant? Saturation matters for L4 feature stability — features that are dormant >80% of frames during gameplay degenerate to noise.

4. **BT dongle availability rate on the bridge laptop.** Channel B is opportunistic. Among operator workstations running the bridge, what fraction have a BlueZ-attached USB BT dongle? Hypothesized: low (the dongle is the v1 LAN-witness hardware, only present on dedicated witness rigs).

5. **PS5 PS-button menu rate during gameplay.** APOP classifier surface — frequency of MENU_DETECTED vs. ACTIVE_MATCH_PLAY transitions. If menus dominate <5% of session time, MLGA capture is gameplay-rich.

6. **GIC chain advancement rate during MLGA-active sessions.** GIC requires PCC=NOMINAL + EXCLUSIVE_USB + gameplay_context=ACTIVE_GAMEPLAY + non-divergent verdict. How many GIC links per hour of NCAA CFB 26? Hypothesized: 10-30 (currently chain-broken at GIC_100; restart via `/operator/gic-reset` would reset baseline).

7. **MLGA cadence overhead.** Cost of running mythos_live_gameplay_audit at 60s cadence during active gameplay — bridge CPU + sqlite write contention. Must be empirically measured before MLGA is enabled by default.

Resolution path: ship MLGA v1 with `mlga_enabled=False` default. Operator runs a 2-hour smoke session with `mlga_enabled=True` to gather these 7 measurements. The output of that smoke session is an empirical-anchor document that supplements this proposal and enables MLGA Stage 2 (actual unblock-corpus production).

## Section 6 — Stage Gates and Timeline

Mirror the BT-CALIB v1.1 stage discipline at compressed scale (MLGA is engineering-only + wallet-free; no on-chain operations; no hardware procurement; uses existing controller + existing bridge):

**Stage 1 (this proposal): Architecture verification.** This document is the Stage 1 deliverable. Establishes the transport-verification block, feature derivation, threat anchor, empirical unknowns, and constraint envelope. Stage 1 exits when this document moves from draft to FROZEN status (operator review + PV-CI ceremony pinning the 7 MLGA invariants).

**Stage 2 (Engineering implementation): ship Mythos-Live-Gameplay variant + capture pipeline + 3 unblock-export scripts.** Single-session engineering work; ~5 commits. Output: code that an operator with controller plugged in can run.

**Stage 3 (Empirical smoke): operator runs 1-2 hour NCAA CFB 26 session with `mlga_enabled=True`.** Resolves the 7 empirical unknowns in §5. Output: empirical-anchor document committed at `wiki/methodology/mlga_empirical_anchor_v1.md`.

**Stage 4 (Corpus growth + unblock): MLGA runs across N gameplay sessions producing real dataproofs for Phase 243-SS2 Stage-A, Phase 242-BT Stage 2, Phase 229 AIT.** Each session contributes to the relevant blocked corpus per its export script. Operator-runtime calendar work; weeks to months calendar.

**Stage 5 (Post-corpus verification): cross-check MLGA-captured data against lab-controlled measurements where they exist.** Establishes the calibration relationship between ambient-gameplay-captured data and lab-controlled data. Required before MLGA-captured corpus can satisfy Phase 243-SS2 Stage-A or Phase 242-BT Stage 2 gates definitively.

## Section 7 — Constraint Envelope

MLGA v1 claims:
- Real-time live capture + audit during dual-connected DualSense Edge gameplay
- Cryptographic dataproof per session (32-byte commitment via FROZEN preimage)
- Mythos variant in `per_session` cadence tier with frozen_region discipline preserved
- Unblock-export scripts mapping captured data to 3 currently-blocked phase corpora

MLGA v1 does NOT claim:
- Replacement of dedicated Stage-A capture sessions where lab-controlled conditions matter
- Detection of any cheat class (existing L0–L8 layers cover this)
- Cross-session controller identity (deferred per CROSS-LESSON-001)
- Production-meaningful improvement to the BT calibration σ_held-vs-placed gap without controlled RF environment (the lab-controlled Stage 2 measurement is still required; MLGA augments the corpus, doesn't certify it)
- Mainnet activity (MLGA is wallet-free; uses local SQLite only)

The hard rule preservation:
- `CHAIN_SUBMISSION_PAUSED=true` MUST hold during MLGA operation. MLGA does no chain ops.
- No FROZEN-region edits. INV-MLGA-* invariants ship via governance ceremony.
- Mythos PR gate enforces this: any commit that touches MLGA constants without ceremony reason `invariant_change` is blocked.

## Section 8 — References

Existing canonical anchors (must be read before MLGA design work):

- `wiki/methodology/bt_calibration_v1_1_architectural_revision.md`
- `wiki/methodology/sensor_stack_v2_1_architectural_revision.md`
- `wiki/assessments/VAPI Bluetooth Calibration_ Architectural Prerequisites and Threat Model Analysis.pdf`
- `wiki/assessments/DualSense Edge Sensor-Stack Characterization for VAPI Track-1 Anti-Cheat Feature Architecture.pdf`
- `wiki/methodology/VBDIP-0001-vad-framework-introduction.md`
- `wiki/methodology/operator_initiative_completion_manifest.md` (parallel architecture pattern)
- `lessons.md` entry `BT-CALIB-LESSON-001`
- `lessons.md` entry `CROSS-LESSON-001` (same-controller-population separability)
- `lessons.md` entry (new) `MLGA-LESSON-001` (dual-connection topology as calibration corpus surface; **this proposal authors**)

Existing protocol code MLGA composes:

- `bridge/vapi_bridge/dualshock_integration.py` — 1000 Hz HID capture pipeline (BiometricFeatureExtractor + Phase 49 FFT + Phase 205 accel tremor + Phase 213 4096-pt zero-pad)
- `bridge/vapi_bridge/capture_continuity.py` — Phase 234.7 PCC monitor
- `bridge/vapi_bridge/active_play_occupancy.py` — Phase 241-APOP classifier
- `bridge/vapi_bridge/grind_chain.py` — Phase 235-A GIC chain (FROZEN-v1 PATTERN-017 primitive)
- `bridge/vapi_bridge/mythos_variants.py` — 8 existing variants; MLGA adds 9th
- `bridge/vapi_bridge/mythos_cadence_engine.py` — 7 existing cadence tiers; MLGA adds `per_session` (8th)
- `scripts/vapi_invariant_gate.py` — PV-CI ceremony surface (101 → 108 after MLGA ceremony)

**Authoring discipline:** This proposal is operator-runtime-authored at the methodology layer. Stage 2 engineering work begins after this document exits draft state via operator review. Stage 3 empirical smoke is the unblock signal for Stage 4 corpus growth.
