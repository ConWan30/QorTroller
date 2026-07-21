# A2A round 07 — ASM-Loop RESIDUAL-ACCEPTED PASS request: Composite-B v2.2

You are the AUDITOR (grok). Prior: your r06 RE-VERIFY = HOLD, structure closed (F1 BLOCK + all
mandatory WARNs CLOSED), two residuals: F19 (layers 1-2 don't defeat 1× dump re-injection) and F20
(PARTIAL vs UNVERIFIABLE wording).

The builder + operator have adopted the honest conclusion your F19 forced, as the DESIGN CEILING
(not a defect to keep chasing):
- A pure passive HID stream is inherently replayable (zero injection ⇒ no challenge to respond to).
- Therefore **optical co-presence (Thesis C) is MANDATORY for the replay-resistant
  `CONTINUOUS_PRESENT` verdict.** Without optical, the honest max is `PARTIAL_PRESENT` — human-shaped
  + live-device-clock-rate, explicitly `replay_resistant=false`, advisory.
- F20 tiering pinned: layer-1 absent → UNVERIFIABLE; layer-1 present + optical absent → max PARTIAL;
  all layers → CONTINUOUS.

**Your task:** this is a residual-accepted PASS check, not a new build. Confirm:
1. F19 is now stated honestly (no remaining over-claim that layers 1-2 defeat dump replay; optical
   correctly load-bearing for CONTINUOUS).
2. F20 wording resolved (rail-thin vs rail-absent tiering unambiguous).
3. No NEW structural break introduced by the optical-mandatory tiering.
4. With F19 + F20 residuals EXPLICITLY ACCEPTED as the design ceiling (pure-passive = advisory/
   replayable; optical-required = replay-resistant), is the design a **residual-accepted PASS**?

Verdict options: **PASS** (residual-accepted, residuals listed) or **HOLD** (a real structural flaw
remains — name it). Write to `docs/a2a/real-play-liveness/round-08-grok-verdict.md` FIRST, then fill.

Rails: design-only, no code, no flag flips, 228B PoAC, FROZEN-v1, PV-CI 184,
CHAIN_SUBMISSION_PAUSED default, single-committer=operator.

[PROPOSAL v2.2 + CLAIMS FOLLOWS]

---

# Composite-B: zero-injection continuous human-presence during real live play — CANDIDATE, design-only

Status: **CANDIDATE / DESIGN-ONLY.** No code, no flag flips (L6B/poep_enabled stay false), no
hardware change, no chain write, no FROZEN-v1 addition. Round: **r05 revision** (ASM-Loop). Builder:
Claude. Prior audit: grok r04 (`round-04-grok-audit.md`) — verdict HOLD, F1 BLOCK + 10 WARN, all
adopted (none disputed). r03 baseline preserved in `round-03-claude-proposal.md` for audit trail.

**r04 disposition in one line:** grok correctly found the replay resistance was over-claimed — a
faithful recording of a real human *preserves* tremor (G3) and IMU↔button coupling (G4), because
those measure physiology *inside* the stream, not liveness-now. This revision adds a real
**anti-replay rail (§2.5)** and stops crediting G3+G4 with killing replay. It also tightens the
verdict enum (F2), device-clock scope (F4), PoSP binding (F5), G2/G4 thresholds (F6/F17), G5
anti-bot claim (F7), W_min wording (F10), and the GIC non-mutation rule (F13).

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

A living human on a real controller emits a bundle of **involuntary, causally-coupled** signals the
bridge already streams at ~1 kHz over USB **without writing anything**. The novelty is not a new
sensor — it's the **composite claim + anti-replay rail + adversary gates + minimum window +
fail-closed posture**, binding primitives that already exist (do not rebuild).

**Honesty pin (F3):** the G* rows below are **gates to be built over existing leaf features/signals**
— the leaf features exist and are cited; the composite *gate functions* do not exist yet. This is
design composition, not a shipped gate package.

| Gate | Leaf signal (exists) | Source | What it actually establishes |
|---|---|---|---|
| **G1 Capture integrity** | PCC `capture_state=NOMINAL` + host ∈ {EXCLUSIVE_USB, UNKNOWN} ≥ min_stable_s | `capture_continuity.py` | The USB sensor pipe is real and stable (liveness w/o capture is theater) |
| **G2 Gameplay gate** | GAD `ACTIVE_GAMEPLAY` **fractional** ≥ f_min over W (F17: fraction, NOT binary `taf>0`; MENU_DETECTED contributes 0; NULL invents no credit) | Phase 235-GAD | Real active play occurred across the window, not one stray press |
| **G3 Involuntary continuity** | micro-tremor variance + tremor_peak_hz (8-12 Hz) + band power | `tinyml_biometric_fusion.py` | A physiological tremor signature is present — **does NOT establish live-now** (see §2.5) |
| **G4 Causal binding** | L2B (IMU↔button latency) usable-fraction ≥ thr when presses exist; L2C only when game stick active | `l2b_*`, `l2c_*` | Body↔input coupling exists **within** the stream — **does NOT establish live-now** (§2.5) |
| **G5 Rhythm non-quantization** | L5 does not flag macro timer-quantization across W | temporal rhythm oracle | Kills **timer-quantized macros only** (F7 — NOT a general ML-bot detector) |
| **G6 L6-Passive co-signal (optional)** | R2 onset EMA series exists + not constant-period (profile-gated, **read-only**) | `dualshock_integration.py:2327` | Trigger cadence isn't machine-perfect |

**The load-bearing correction (grok F1):** G3 and G4 measure physiology *inside* the stream. A
faithful recording of a real human preserves both. **Continuity gates alone cannot distinguish live
play from a paced replay of a real capture.** Liveness-now comes from the anti-replay rail (§2.5),
not from G3/G4. The gates establish *human-shaped*; the rail establishes *live-now*; both are
required.

**Verdicts (machine, advisory only) — F2 pinned, F20 tiered by optical:**
- `CONTINUOUS_PRESENT` — requires **all three:** human-shape gates pass ≥ W_min, device-clock rate
  lock passes (§2.5 layer 1), **AND optical co-presence passes (§2.5 layer 3 / Thesis C).** This is
  the only replay-resistant verdict. Machine fields: `is_pass=false` (advisory, not a tournament
  pass), `advisory=true`, `maps_to_tournament_hard_code=false`, `replay_resistant=true`.
- `PARTIAL_PRESENT` — human-shape gates + device-clock rate lock pass, but **optical is absent** (or
  a gate is thin). Explicitly **replayable** — `replay_resistant=false`. **Pinned non-pass:**
  `is_pass=false`, `streak_eligible=false`, `display_tier=amber`, MUST NOT render green, MUST NOT
  alias to CONTINUOUS or SYNCHRONIZED. This is the honest ceiling for pure-passive (no-optical) play.
- `UNVERIFIABLE` — capture degraded, menu-only, window < floor, **or device-clock ticks absent**
  (§2.5 layer 1 / §4) → **fail-closed**. Insufficient evidence is never PASS.

**F20 clarification (rail-thin vs rail-absent):** "rail" = the layered §2.5 mechanism.
- Layer-1 **absent** (no device ticks) → `UNVERIFIABLE` (can't even establish device-clock rate).
- Layer-1 present, layer-3 (optical) **absent** → max `PARTIAL_PRESENT` (replayable), never CONTINUOUS.
- All layers present → `CONTINUOUS_PRESENT`.

**Gate-missing policy (F6):** G4 absent (sparse presses / CFB26 L2C neutral) → cannot reach
`CONTINUOUS_PRESENT`; max `PARTIAL_PRESENT`.

**Hard rule:** v0 verdicts **never** map to tournament CERTIFY/BLOCK hard codes. Advisory leaf only.

## 2.5 Anti-replay rail (the F1 fix — this is what establishes live-now)

The gates prove *a human shape*; this rail is what addresses *live-now vs replayed*. It is **layered,
and only the optical layer (3) makes the strong verdict replay-resistant** — layers 1-2 alone do not
defeat a faithful 1× HID dump re-injection (see F19 below). Three layers, all **measurement-gated
CANDIDATE** (thresholds are hypotheses, not calibrated):

1. **Device-clock↔wall-clock rate lock.** The DualSense on-device `sensor_ts_ticks` advance at
   ~3 MHz (`_DEVICE_TS_TICKS_PER_MS=3000`, `:201`). For a genuinely live stream, `d(device_ts)/
   d(wall_clock)` stays within `[1±ε]` of the true tick rate over the window. A file replay paced by
   software drifts or must forge device ticks that track *real* wall-time at true rate — hard to do
   faithfully while also preserving G3/G4. **Fail-closed:** if `sensor_ts_ticks` is 0/absent for the
   window, the rail returns `UNVERIFIABLE` — **no `t_mono` fallback** for the liveness claim (F4).
2. **Session-freshness binding.** Bind the window to a fresh per-session value established at session
   start (the PoSP `session_id` join key, optionally salted by a fresh temporal beacon). This kills
   **reuse of old Composite-B artifacts / stored windows** from a foreign session.
3. **Optical co-presence (Thesis C).** Cross-check that the capture-card game state advances
   consistently with the input stream in the same live session. A pure HID replay has no matching
   live optical channel.

**F19 — the honest limit of layers 1-2 (grok r06, load-bearing correction):** layers 1 and 2 do
**NOT** defeat a **faithful 1× real-time re-injection of a real human HID dump into a fresh live
session.** Layer 1 passes because the dump carries the *original* device_ts ticks at true 3 MHz rate.
Layer 2 passes because `session_id` is **bridge-minted for whatever session is live now** — it is not
inside the HID dump, so a re-injected old dump simply gets bound to the new session and clears. This
is exactly the classic dump-replay attack F1 named. **So the residual is not merely "sophisticated
live-re-encode" — even a plain 1× dump re-injection passes layers 1-2.**

**The real conclusion this loop produced:** a *pure passive* input stream is inherently replayable,
because with zero injection there is no challenge the stream must causally respond to. Therefore
**robust replay resistance requires the optical channel (layer 3 / Thesis C) to be MANDATORY for the
strong verdict — not optional.** The capture card is not Phase-2 flavor; it is the anti-replay root
(this is why QorTroller's retina/killfeed surface is load-bearing, not decorative). Restated as
honest claim tiers:

- **Without optical:** `CONTINUOUS_PRESENT` is **not reachable.** Max verdict `PARTIAL_PRESENT` —
  "human-shaped + live device-clock rate," explicitly **replayable and advisory**; it does NOT claim
  replay resistance. Stating this is the fix, not a defeat.
- **With optical (Thesis C mandatory):** `CONTINUOUS_PRESENT` — replay-resistant, because a
  re-injected HID dump cannot also drive the live capture-card video it must be consistent with.
  Residual then narrows to a coordinated HID+video re-encode (much higher bar) + U2 measurement.

## 3. Minimum window (CANDIDATE numbers, measurement-gated)

Not calibrated — **hypotheses to be measured (U3), promoted only after data** (F10):
- **H_W30** — 30 s continuous → advisory-thin (`PARTIAL_PRESENT` ceiling)
- **H_W120** — 120 s → `CONTINUOUS_PRESENT` candidate default (a hypothesis, NOT a shipped default)
- **H_Wlong** — one CFB **quarter** (the defined unit; "match-half" was ambiguous, removed) → strong
Aggregation unit: per session_adjudicator adjudication window. Below the floor → `UNVERIFIABLE`.

**GIC non-mutation (F13):** Composite-B streaks are a **parallel advisory counter only**. They MUST
NOT feed `consecutive_clean`, MUST NOT alter GIC inputs, and MUST NOT change what `fallback_verdict`
hashes. The grind integrity chain stays byte-identical; Composite-B references count-eligible windows
read-only, never writes them.

## 4. Remote-Play timing discipline (U2)

**Scope honesty (F4):** `sensor_ts_ticks` is today wired as a **PoEP/L6b spike-latency companion**
(`_rp_device_latency_ms`, `:201`/`:230`, `emulator:751`), NOT as a continuous Composite-B windowing
clock — and it is **excluded from `InputSnapshot.serialize()`**, so continuity binding must carry
device_ts out-of-band. The continuous window clock is **to-build**, reusing the existing tick source.

**Fail-closed rule:** when `sensor_ts_ticks` is 0/absent for a window, the Composite-B continuous
path returns `UNVERIFIABLE` — it does **NOT** silently fall back to `t_mono` (that fallback is what
reopens F-RIG27-8's 3-15× inflation). Device_ts preference is therefore a *requirement* of the
liveness claim, not a best-effort.

**Claim tightening (F16):** that continuity gates (G3 spectral + G4 coupling) are more RP-robust than
spike-latency is **plausible but unmeasured** — it is a hypothesis for U2, not an established fact.

## 5. Binding — CANDIDATE domain tag, advisory leaf under PoSP

**F5 resolution — PoSP does not mint commitments; this is a separate record it references.** PoSP is
REFERENCE-AND-BIND (`posp.py:1-28`, "mints NO new commitment primitive, NO domain-tag hash, NO
FROZEN-v1 family"). So Composite-B is a **separate CANDIDATE record** that PoSP references by a named
optional root, NOT a hash grown inside PoSP:

- A standalone CANDIDATE record `realplay_liveness_v0` carries the verdict + gate bitmap + machine
  fields (`is_pass=false`, `advisory=true`, `maps_to_tournament_hard_code=false`,
  `advances_poep_enabled=false`, `streak_eligible=false`).
- PoSP references it via a named optional root `realplay_liveness_root` (parallel to its existing
  `kas_session_root` / `retina_perception_root` named-parallel-roots pattern) — PoSP grows a
  *reference*, not a commitment.
- Tag `QORTROLLER-REALPLAY-LIVE-v0` stays **CANDIDATE**; **no commitment/domain-tag hash is frozen
  this loop** — any `SHA-256(domain_tag || …)` formula is deferred to a future freeze ceremony and is
  explicitly NOT part of v0 (v0 is an advisory dict record, not a committed primitive).
- Naming discipline: `CONTINUOUS_PRESENT` MUST NOT be aliased to PoSP `SYNCHRONIZED` or
  `controller_presence.SYNCHRONIZED_CONTROLLER` in code, UI, or docs — three distinct verdicts.
- Does not touch, reuse, or supersede any of the 14 FROZEN-v1 families.

## 6. Adversary matrix

Corrected per grok F1/F7 — G3/G4 do NOT kill replay; the rail (§2.5) does the live-now work.

| # | Attack | Actually killed by | Honest residual |
|---|---|---|---|
| 1 | Recorded HID-stream replay | **Optical co-presence (layer 3 / Thesis C) — MANDATORY for CONTINUOUS.** Layers 1-2 (device_ts↔wall rate + session-freshness) do NOT defeat a faithful 1× dump re-injection (F19); they only block reuse of stored artifacts. **NOT G3/G4** either. | Without optical: replay is **OPEN** → max `PARTIAL_PRESENT` (advisory, replayable, stated). With optical: residual narrows to a coordinated HID+video re-encode + U2 measurement. |
| 2 | Synthetic-tremor bot (8-12 Hz sinusoid) | G4 causal latency (when presses exist) + G2 fractional gate; G5 **only** if timing is quantized | **Good ML bots remain OPEN** — same limit as L4 bot-vs-human. G5 is NOT a general anti-bot (F7). |
| 3 | Human relay / shared pad | — | **Weak by design**: proves *a* live human, **not which** human. Explicit accepted ceiling (F9), not a defect |
| 4 | Remote-Play timing artifact (F-RIG27-8) | device_ts windowing §4 (fail-closed, no t_mono fallback) | RP-robustness of G3/G4 is **unmeasured** (U2) — plausible, not proven (F16) |
| 5 | Menu-AFK + idle tremor | G2 **fractional** f_min over W (F17 — not binary `taf>0`) + MENU_DETECTED fail-closed | none material once f_min is fractional |

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

- **Q1 W_min unit:** adjudication-window aggregation into a **separate parallel advisory counter**
  (NOT `consecutive_clean`, NOT GIC — reconciled with the F13 non-mutation rule §3; the earlier r03
  "→ consecutive_clean streaks" wording is superseded, it contradicted F13).
- **Q2 CFB26 vs 27:** active profile is **`ncaa_cfb_26`** (verified `bridge/.env`), so **L2C is
  neutral-prior today**; design is profile-agnostic so `ncaa_cfb_27` (active right stick) upgrades G4.
- **Q3 Thesis C:** included as explicit non-blocking appendix (§7).
- **Q4 naming:** sibling `realplay_liveness` advisory field under PoSP (adopted — §5).
- **Q5 U2 data:** deferred to measurement plan; first pass likely a dedicated desk session.

## 10. Numbered claims (for grok r04 adversarial audit)

- **C1.** U1 is CLOSED:NO — game haptic/adaptive-trigger output is unreadable from the HID input
  report and unreachable over the dual-host USB path; verified against `dualshock_integration.py:3709-
  3718` + emulator `:168/:816`. Thesis A is refuted, not deferred. *(r04: stood, F8 INFO.)*
- **C2.** Composite-B binds only signals/features the bridge already captures read-only at ~1 kHz; it
  adds **zero** HID output during play and needs no new sensor. The G* **gate functions are to-build**
  over those existing features (not shipped); zero-write is an invariant dependency on
  `L6B_ENABLED=false` + `PS5_COMPAT_MODE` + no campaign lift (F3/F12).
- **C3.** The claim is population liveness / embodied presence, explicitly **not** identity and
  **not** nonce-bound spike-reflex; verdicts are advisory-only, carry machine fields `advisory=true`
  / `maps_to_tournament_hard_code=false`, and never map to tournament hard codes in v0 (F14).
- **C4.** Gates fail **closed**, and the third verdict is pinned non-pass: `PARTIAL_PRESENT` has
  `is_pass=false` / `streak_eligible=false` / `display_tier=amber` and never aliases to CONTINUOUS or
  SYNCHRONIZED; G4-missing → max PARTIAL; rail-absent or ticks-absent → `UNVERIFIABLE` (F2/F6/F15).
- **C5.** W_min values are **hypotheses** (H_W30 / H_W120 / H_Wlong=one CFB quarter), promoted only
  after U3 measurement — not shipped defaults; "match-half" removed as ambiguous (F10).
- **C6.** `sensor_ts_ticks` is today a PoEP/L6b spike-latency companion (not a continuous windowing
  clock) and is excluded from `InputSnapshot.serialize()`; the continuous window clock is **to-build**
  and **fails closed to UNVERIFIABLE when ticks are absent** (no `t_mono` fallback). RP-robustness of
  G3/G4 is a hypothesis for U2, unmeasured (F4/F16).
- **C7.** The human-relay attack (#3) is a **stated, accepted residual** (proves a live human, not
  which human) — not claimed as defended. *(r04: stood, F9.)*
- **C8.** v0 is a **separate CANDIDATE record** `realplay_liveness_v0` that PoSP **references** via a
  named optional root `realplay_liveness_root` — PoSP mints no commitment (F5). No domain-tag hash is
  frozen this loop; `QORTROLLER-REALPLAY-LIVE-v0` stays CANDIDATE; `advances_poep_enabled=false`; does
  not touch the 14 FROZEN-v1 families. `CONTINUOUS_PRESENT` never aliases PoSP `SYNCHRONIZED` /
  `SYNCHRONIZED_CONTROLLER`.
- **C9.** Thesis C is optional Phase-2, uses non-HID (optical/killfeed) event clocks only, carries no
  PoEP-equivalence claim, and is gated behind B; F-MATCH OCR residue is an honest dependency. *(r04:
  stood.)*
- **C10.** Design only — no code, no flag flips, no hardware, no chain write, no FROZEN edit, no
  commit beyond `docs/a2a/real-play-liveness/` artifacts. *(r04: stood, F11.)*
- **C11 (revised r07, F19).** Live-now is NOT establishable from a pure passive HID stream alone:
  layers 1-2 of the rail (device_ts↔wall rate + session-freshness) do **not** defeat a faithful 1×
  HID dump re-injection (they only block reuse of stored artifacts), and G3/G4 pass on any real
  recording. **Robust replay resistance requires the optical channel (Thesis C) to be MANDATORY for
  `CONTINUOUS_PRESENT`.** Without optical, the honest max verdict is `PARTIAL_PRESENT` — human-shaped
  and live-device-clock-rate, but explicitly **replayable/advisory**. With optical, `CONTINUOUS_PRESENT`
  is replay-resistant (a re-injected dump can't also drive the matching live video); residual narrows
  to a coordinated HID+video re-encode, measurement-gated (U2). The capture card is the anti-replay
  root, not optional flavor.
