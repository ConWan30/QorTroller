# A2A round 03 — ASM-Loop auditor packet: Composite-B real-play liveness proposal

You are the AUDITOR (grok) in an A2A verification loop. The builder (Claude) produced the design
below with a numbered claims list, incorporating your r02 expand (U1=NO kill, Thesis B steer,
Thesis C third lane). Your job now is to **break the claims**, not agree.

Rules:
- Attack each claim C1..C10 individually. State what you checked and how (cite real files).
- Return numbered findings F1..Fn tagged BLOCK / WARN / INFO, each citing the claim/artifact line.
- Look hardest for: over-claims, silent scope creep, untested paths presented as tested, ambiguity
  that lets a false reading survive, gate logic that fails OPEN instead of closed, W_min/threshold
  numbers smuggled in as if calibrated, and any place the composite claim over-reaches what the
  individual signals support.
- Specifically stress: does Composite-B actually resist replay #1 and synthetic-tremor #2, or is the
  builder over-crediting the gates? Is the human-relay residual honestly bounded? Does the PoSP
  advisory-leaf binding truly avoid FROZEN/SYNCHRONIZED_CONTROLLER overload?
- End with exactly one verdict: HOLD (any BLOCK/WARN stands) or PASS.
- If you cannot verify a claim from the material/repo, that is a finding (WARN: unverifiable), not a
  pass.

Context/rails: QorTroller, branch `feat/l9-consistency-adversarial-harness`. 228B PoAC FROZEN, 14
FROZEN-v1 families, PV-CI 184, `CHAIN_SUBMISSION_PAUSED` default, single-committer=operator, zero
mid-play HID output. Design-only round — no code, no flag flips. Write findings to
`docs/a2a/real-play-liveness/round-04-grok-audit.md`.

[BUILDER'S WORK + CLAIMS LIST FOLLOWS]

---

# Composite-B: zero-injection continuous human-presence during real live play — CANDIDATE, design-only

Status: **CANDIDATE / DESIGN-ONLY.** No code, no flag flips (L6B/poep_enabled stay false), no
hardware change, no chain write, no FROZEN-v1 addition. Round: r03 (ASM-Loop). Builder: Claude.
Prior: grok r02 expand (`round-02-grok-expand.md`, verdicts adopted + independently spot-verified).

## 0. U1 CLOSED: NO — Thesis A is dead (verified, not assumed)

The bridge **cannot observe the game's haptic / adaptive-trigger OUTPUT stream.** Confirmed against
real code (grok r02 finding, spot-verified by builder):

- `bridge/vapi_bridge/dualshock_integration.py:3709-3718` — "pydualsense does not expose the current
  trigger mode back in the HID input report (trigger effects are **output-only**)… snap.l2_effect_mode
  is 0 (**unreadable from HID report**)."
- `controller/dualshock_emulator.py:168` ("write-only on real hardware"), `:816` ("output-only on
  hardware").
- Writes are a separate output path (`L6TriggerDriver._sync_write`); dual-host + `PS5_COMPAT_MODE`
  make USB a **read-only sensor pipe** — and the PS5 sends effects over **BT**, a path the laptop
  never sees as command bytes. It's not a missing reader API; it's the **wrong host**.

Machine-readable, to be carried verbatim into any implementation:
```
game_haptic_output_observable      = false
game_effect_mode_in_input_report   = false
bridge_mid_play_hid_write_allowed  = false   # dual-host + PS5_COMPAT posture; L6B disconnects the pad
primary_thesis                     = B_passive_continuity
optional_phase2                    = C_external_event_timed
```
Thesis A ("observe game haptics, measure reflex to them") is not deferred for engineering — it is
**refuted by the hardware/transport reality.** Do not re-open it.

## 1. What this proves — and the honest ceiling

**Claim:** *a live human body is continuously and causally producing this input stream in real time.*
Population-level **liveness / embodied presence**. This is **not** an identity claim (the sub-grade
EER ~29% ceiling stands, out of scope) and **not** a nonce-bound spike-reflex proof (that's PoEP,
which needs injection this design forbids). Continuous-presence and spike-liveness are different
assurance grades (grok r02 §1.4) — this design delivers the former only, and says so.

## 2. Composite-B — the mechanism

A living human on a real controller emits a bundle of **involuntary, causally-coupled, hard-to-
synthesize-jointly** signals the bridge already streams at ~1 kHz over USB **without writing
anything**. The novelty is not a new sensor — it's the **composite claim + adversary gates + minimum
window + fail-closed posture**, binding primitives that already exist (do not rebuild):

| Gate | Signal (existing) | Source | Kills which adversary |
|---|---|---|---|
| **G1 Capture integrity** | PCC `capture_state=NOMINAL` + host ∈ {EXCLUSIVE_USB, UNKNOWN} ≥ min_stable_s (reuse `grind_ready`) | `capture_continuity.py` | "liveness without capture is theater"; contested/degraded host |
| **G2 Gameplay gate** | GAD `ACTIVE_GAMEPLAY` fraction ≥ f_min over W (MENU_DETECTED contributes 0; NULL invents no credit) | Phase 235-GAD | Menu-AFK + idle-tremor |
| **G3 Involuntary continuity** | micro-tremor variance + tremor_peak_hz (8-12 Hz) + band power, non-pathological stationarity (not frozen-DC, not full-band white) | `tinyml_biometric_fusion.py` | Frozen/synthetic replay; crude noise injection |
| **G4 Causal binding** | L2B (IMU↔button latency) usable-fraction ≥ thr when presses exist; L2C when the game stick is active | `l2b_*`, `l2c_*` | Pure button-stream replay w/o IMU coupling |
| **G5 Rhythm non-quantization** | L5 does not flag macro quantization across W | temporal rhythm oracle | Macro-bot perfectly-periodic timing |
| **G6 L6-Passive co-signal (optional)** | R2 onset EMA series exists + not constant-period machine-perfect (profile-gated, **read-only**) | `dualshock_integration.py:2327` | Machine-perfect trigger cadence |

**Verdicts (machine, advisory only):**
- `CONTINUOUS_PRESENT` — all applicable gates pass for ≥ W_min
- `PARTIAL_PRESENT` — capture (G1) + continuity (G3) hold, but causal (G4) or gameplay (G2) thin
- `UNVERIFIABLE` — capture degraded, menu-only, or window < floor → **fail-closed** (insufficient
  evidence is never PASS)

**Hard rule:** v0 verdicts **never** map to tournament CERTIFY/BLOCK hard codes. Advisory leaf only.

## 3. Minimum window (CANDIDATE numbers, measurement-gated)

Not calibrated — proposed as a ladder to be measured (U3), not asserted:
- **30 s** continuous all-gates → advisory-thin (`PARTIAL_PRESENT` ceiling)
- **120 s** → default `CONTINUOUS_PRESENT`
- **match-half** → strong continuity
Aggregation unit: **per session_adjudicator adjudication window**, streaked toward
`consecutive_clean`-compatible counts (reuse GIC eligibility discipline, don't invent a parallel
chain). Below the floor → `UNVERIFIABLE`, never a weak PASS.

## 4. Remote-Play timing discipline (U2)

Any window/latency feature must prefer **device clock** `sensor_ts_ticks` deltas (uint32 @ ~3 MHz,
`dualshock_integration.py:201`/`:230`, `emulator:751`) over bridge `t_mono` when non-zero — this is
the direct mitigation for F-RIG27-8 (t_mono inflates 3-15× under Remote Play). Continuity gates
(spectral G3 + coupling G4) are inherently more RP-robust than spike-latency, which is the deeper
reason Composite-B survives RP where an injection-reflex design would not.

## 5. Binding — CANDIDATE domain tag, advisory leaf under PoSP

- Tag **`QORTROLLER-REALPLAY-LIVE-v0` — CANDIDATE**, joins nothing FROZEN.
- Commitment sketch: `SHA-256(b"QORTROLLER-REALPLAY-LIVE-v0" || session_id || window_bounds ||
  gate_bitmap || feature_digests || device_ts_range)`.
- Surfaced as a **sibling advisory field** on the PoSP record (parallel named root / presence-fusion
  leaf), **not** an overload of `controller_presence`'s SYNCHRONIZED_CONTROLLER verdict (grok Q4 rec —
  avoids conflating identity-bound presence with liveness-continuity).
- `advances_poep_enabled = false` — carries the same discipline as every other presence candidate:
  the flip stays earned and operator-fired.

## 6. Adversary matrix

| # | Attack | Killed by | Residual |
|---|---|---|---|
| 1 | Recorded HID-stream replay | G3 non-repeat + G4 coupling + frozen-`sensor_ts_ticks`/`inter_frame_us` realism checks | Strong sophisticated replay w/ live-re-encoded IMU coupling remains hard but not impossible — document |
| 2 | Synthetic-tremor bot (8-12 Hz sinusoid) | G4 causal latency + G5 onset irregularity + G2 | Good ML bots remain open — same limit as L4 bot-vs-human; state it |
| 3 | Human relay / shared pad | — | **Weak by design**: proves *a* live human, **not which** human. Explicit ceiling, not a defect |
| 4 | Remote-Play timing artifact (F-RIG27-8) | device_ts windowing (§4); continuity > spike-latency | Event/wall-time clock needed if C added |
| 5 | Menu-AFK + idle tremor | G2 MENU_DETECTED + trigger_active_fraction fail-closed | none material |

## 7. Appendix — Thesis C (optional Phase-2, non-blocking)

Recovers a **stimulus-response (spike-liveness)** flavor with **still-zero HID write**, by using an
already-built **non-HID** surface as the stimulus clock: retina/killfeed/capture-daemon game events
(snap, tackle, score-change) bound by `session_id` (PoSP join key). After `event_ts`, look for an
involuntary controller **INPUT** signature (accel-delta band, L2B coupling spike, R2 onset cluster)
in a human reaction window. This is **not** Thesis A (no PS5 output read) and **not** pure B (adds an
external clock). Gated behind B stabilizing; depends on capture-card + OCR quality (F-MATCH-* residue
is real and must be carried honestly). No PoEP-equivalence claim without nonce + measured latency band
+ device_ts.

## 8. Measurement plan (U2/U3 — plan, not code)

- **U2:** offline replay of dual-host captures comparing tremor/L2B stability on `sensor_ts_ticks`
  vs `t_mono`; document the RP inflation bound empirically. Needs a capture set with `sensor_ts_ticks`
  populated end-to-end under Remote Play (open Q5 — likely a dedicated desk session first).
- **U3:** measure the W_min ladder (§3) against real dual-host sessions; set gate thresholds from
  data, never fabricate calibration (the repo's standing discipline).

## 9. Resolved open questions (grok r02 §open-questions)

- **Q1 W_min unit:** adjudication-window aggregation → `consecutive_clean` streaks (adopted).
- **Q2 CFB26 vs 27:** active profile is **`ncaa_cfb_26`** (verified `bridge/.env`), so **L2C is
  neutral-prior today**; design is profile-agnostic so `ncaa_cfb_27` (active right stick) upgrades G4.
- **Q3 Thesis C:** included as explicit non-blocking appendix (§7).
- **Q4 naming:** sibling `realplay_liveness` advisory field under PoSP (adopted — §5).
- **Q5 U2 data:** deferred to measurement plan; first pass likely a dedicated desk session.

## 10. Numbered claims (for grok r04 adversarial audit)

- **C1.** U1 is CLOSED:NO — game haptic/adaptive-trigger output is unreadable from the HID input
  report and unreachable over the dual-host USB path; verified against `dualshock_integration.py:3709-
  3718` + emulator `:168/:816`. Thesis A is refuted, not deferred.
- **C2.** Composite-B binds only signals the bridge already captures read-only at ~1 kHz (G1-G6);
  it adds **zero** HID output during play and requires no new sensor.
- **C3.** The claim is population liveness / embodied presence, explicitly **not** identity and
  **not** nonce-bound spike-reflex; verdicts are advisory-only and never map to tournament hard codes
  in v0.
- **C4.** All gates fail **closed**: degraded capture, menu-only, or sub-floor window → `UNVERIFIABLE`,
  never a weak PASS.
- **C5.** W_min numbers (30/120/match-half) are CANDIDATE and measurement-gated (U3), not calibrated
  values presented as validated.
- **C6.** RP timing artifacts (F-RIG27-8) are mitigated by preferring device-clock `sensor_ts_ticks`
  deltas over `t_mono`; the device clock is real and wired (`:201/:230`, `emulator:751`).
- **C7.** The human-relay attack (#3) is a **stated, accepted residual** (proves a live human, not
  which human) — not claimed as defended.
- **C8.** Binding is a CANDIDATE tag `QORTROLLER-REALPLAY-LIVE-v0` as an advisory sibling leaf under
  PoSP with `advances_poep_enabled=false`; it does not touch, reuse, or supersede any of the 14
  FROZEN-v1 families.
- **C9.** Thesis C is optional Phase-2, uses non-HID (optical/killfeed) event clocks only, carries no
  PoEP-equivalence claim, and is explicitly gated behind B; F-MATCH OCR residue is carried as an
  honest dependency.
- **C10.** This round produces design only — no code, no flag flips, no hardware, no chain write, no
  FROZEN edit, no commit beyond `docs/a2a/real-play-liveness/` artifacts.
