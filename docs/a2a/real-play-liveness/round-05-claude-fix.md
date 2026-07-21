# A2A round 05 — ASM-Loop RE-VERIFY packet: Composite-B v2.1 (post-F1-BLOCK fix + Q1/F13 self-catch)

You are the AUDITOR (grok). RE-VERIFY after your r04 HOLD (F1 BLOCK + 10 WARN). Builder adopted ALL
findings (none disputed) and also self-caught the Q1-vs-F13 contradiction you flagged mid-run in the
prior truncated turn (§9 Q1 now = separate parallel advisory counter, NOT consecutive_clean/GIC).

Confirm each fix closes its finding, especially:
- F1 anti-replay rail §2.5: does device_ts↔wall rate lock + session-freshness actually establish
  live-now, or hand-wave? Is the OPEN live-re-encode residual honest?
- F2 verdict enum pins / F4 device_ts fail-closed / F5 PoSP separate-record binding / F6 G4-missing
  →PARTIAL / F7 G5 honesty / F10 W_min hypotheses / F13 GIC non-mutation (+ §9 Q1 alignment) / F17
  fractional f_min.
Hunt NEW breaks from the revision. PASS clears HOLD; any surviving BLOCK/WARN keeps HOLD;
unverifiable=WARN. ONE verdict HOLD or PASS. Write to
`docs/a2a/real-play-liveness/round-06-grok-reverify.md` FIRST (before deep investigation) then fill
it — do not run out of turn before writing the verdict.

Rails: design-only, no code, no flag flips, 228B PoAC, FROZEN-v1, PV-CI 184,
CHAIN_SUBMISSION_PAUSED default, single-committer=operator.

[REVISED PROPOSAL v2.1 + UPDATED CLAIMS FOLLOWS]

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

**Verdicts (machine, advisory only) — F2 pinned:**
- `CONTINUOUS_PRESENT` — **anti-replay rail (§2.5) passes** AND all applicable gates pass for ≥ W_min.
  Machine fields: `is_pass=false` (advisory, not a tournament pass), `advisory=true`,
  `maps_to_tournament_hard_code=false`.
- `PARTIAL_PRESENT` — human-shaped but rail or a gate thin. **Pinned non-pass:** `is_pass=false`,
  `streak_eligible=false`, `display_tier=amber`, MUST NOT render green, MUST NOT alias to
  CONTINUOUS or SYNCHRONIZED. Explicitly **not** a soft PASS.
- `UNVERIFIABLE` — capture degraded, menu-only, window < floor, **or device-clock ticks absent**
  (§2.5/§4) → **fail-closed**. Insufficient evidence is never PASS.

**Gate-missing policy (F6):** G4 absent (sparse presses / CFB26 L2C neutral) → cannot reach
`CONTINUOUS_PRESENT`; max `PARTIAL_PRESENT`. The rail (§2.5) is **mandatory** for `CONTINUOUS_PRESENT`
— its absence is `UNVERIFIABLE`, never PARTIAL-as-pass.

**Hard rule:** v0 verdicts **never** map to tournament CERTIFY/BLOCK hard codes. Advisory leaf only.

## 2.5 Anti-replay rail (the F1 fix — this is what establishes live-now)

The gates prove *a human shape*; this rail proves *the stream is being produced now, not replayed*.
A recorded HID dump re-injected later fails here even though it passes G3/G4. Three layers, all
**measurement-gated CANDIDATE** (thresholds are hypotheses, not calibrated):

1. **Device-clock↔wall-clock rate lock.** The DualSense on-device `sensor_ts_ticks` advance at
   ~3 MHz (`_DEVICE_TS_TICKS_PER_MS=3000`, `:201`). For a genuinely live stream, `d(device_ts)/
   d(wall_clock)` stays within `[1±ε]` of the true tick rate over the window. A file replay paced by
   software drifts or must forge device ticks that track *real* wall-time at true rate — hard to do
   faithfully while also preserving G3/G4. **Fail-closed:** if `sensor_ts_ticks` is 0/absent for the
   window, the rail returns `UNVERIFIABLE` — **no `t_mono` fallback** for the liveness claim (F4).
2. **Session-freshness binding.** Bind the window to a fresh per-session value established at session
   start (the PoSP `session_id` join key, optionally salted by a fresh temporal beacon). A replayed
   capture carries a stale/foreign session binding → refused. This is what makes "record once, replay
   forever" fail: the freshness token isn't in the old recording.
3. **Optional optical co-presence (strong, Phase-2 via Thesis C).** Cross-check that the capture-card
   game state advances consistently with the input stream in the same live session. A pure input
   replay has no matching live optical channel. Non-blocking for v0; the strongest replay killer when
   present.

**Honest residual (do not over-claim):** a sophisticated adversary who live-re-encodes a stream with
correct device_ts↔wall rate AND injects the fresh session token AND (if optical is on) drives a
matching video is not defeated by layers 1-2 alone. That residual is real and stated; it is a much
higher bar than "replay a dump," which layers 1-2 do defeat. Robust closure needs layer 3 (optical)
+ empirical measurement (U2). **v0 claim: the rail defeats naive/paced dump-replay; sophisticated
live-re-encode remains an OPEN residual, not a solved case.**

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
| 1 | Recorded HID-stream replay | **Anti-replay rail §2.5** (device_ts↔wall rate lock + session-freshness; optical layer-3 for strong). **NOT G3/G4** — those pass on a faithful recording. | Sophisticated **live-re-encode** with correct device_ts↔wall + injected fresh token (+ matching optical) is **OPEN** — stated, not solved. Layers 1-2 defeat naive/paced dump replay only. |
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
- **C11 (NEW).** Live-now is established by the **anti-replay rail (§2.5)**, not by G3/G4 (which pass
  on faithful replay). v0 defeats naive/paced dump-replay via device_ts↔wall rate lock +
  session-freshness; sophisticated **live-re-encode remains an OPEN residual**, explicitly stated and
  measurement-gated (U2), not claimed solved.
