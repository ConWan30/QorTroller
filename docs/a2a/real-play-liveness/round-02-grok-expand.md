# A2A round 02 — Grok EXPAND: novel human-liveness during real live play

**Role:** grok (forward expand / adversarial steer)  
**Prior:** `docs/a2a/real-play-liveness/round-01-claude-open.md`  
**Body integrity of prior:** sha256 `88feb49be8ec67e03ea0020220a2f83aab91cb530a423c8830d1305b5434fe74` — **MATCH** (recomputed)  
**Envelope in:** `98b94d9a5107a033`  
**Posture:** design only — no code, no flag flips, no FROZEN edits, no chain, no commit.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator · zero HID mid-play output constraint.

---

## verdicts

| Item | Verdict | One-line |
|------|---------|----------|
| **U1 (game haptic OUTPUT observable?)** | **CLOSED: NO** | Bridge sees controller **INPUT** only; adaptive-trigger / rumble effects are **output-only** on hardware and unreadable from the HID input report. Thesis A as stated is **dead**. |
| **Thesis A — game-as-stimulus via observed OUTPUT** | **REFUTE** | Killed by U1 + dual-host topology (PS5 owns BT write path; laptop USB is read path). |
| **Thesis B — pure passive continuity** | **PRIMARY STEER** | Only path that matches the zero-injection constraint with signals the bridge already captures at ~1 kHz. |
| **Thesis C — external event-timed passive response** *(new)* | **OPTIONAL PHASE-2** | Optical / killfeed / session-event timestamps as *stimulus time*, controller INPUT as response — still zero HID write. Not a rescue of A; different channel. |
| **Blocker analysis (PoEP/L6B injection dead mid-play)** | **ACCEPT** | Correct and load-bearing; do not re-open injection as primary. |
| **Build this loop** | **B-primary composite + honest ceiling + adversary matrix** | Proposal must pin U1 closed, not redesign around hope of reading PS5 output reports. |

---

## 1. Framing attack

### What's wrong or naive

1. **A/B is a false binary on the wrong axis.** The load-bearing axis is not "stimulus vs no stimulus" — it is **whether the verifier has a ground-truth stimulus timestamp under the dual-host read-only constraint**. Thesis A smuggles "game events are free nonces" without proving the bridge can *observe those events*. That is an observability claim, not a physiology claim. U1 closes the observability claim: **NO**.

2. **"Observe the game's haptic OUTPUT stream" conflates three different things:**
   - (a) HID **output reports** the PS5 sends over BT to the Edge (force / rumble / LED).
   - (b) **Echo** of those commands in the USB **input report** the laptop polls.
   - (c) **Physical consequences** of those commands in sensors the USB path *does* read (accel spike from rumble, onset-velocity shift under resistance).
   
   The open packet only argued (a)/(b). The code settles (b): unreadable. (c) is a different, weaker, unsupervised detector — not "game-as-stimulus" in the PoEP sense (no nonce, no event ID).

3. **Dual-host topology is under-weighted.** Dual-host = USB→laptop (bridge capture) **and** BT→PS5 (gameplay). Game adaptive-trigger / haptic commands travel **PS5 → Edge over BT**. The bridge's pydualsense reader is on the **USB host**. Even if a future firmware feature echoed effect state on input reports, today's path is:
   - USB: laptop **reads** input, and under `PS5_COMPAT_MODE` **must not write** (see §2).
   - BT: PS5 **writes** effects the laptop never sees as command bytes.
   
   So Thesis A is not only "missing a reader API" — it is **wrong host**.

4. **"Population-level liveness / continuous embodied presence" is doing two jobs.** Continuous presence (session-long causal continuity) and spike-liveness (reflex-in-band after a stimulus) are different assurance grades. PoEP is spike-liveness. Pure B is continuous presence. Mixing them invites over-claim: a long tremor series is not a nonce-bound reflex proof, and vice versa.

5. **The blocker paragraph slightly overstates PS5_COMPAT coverage.** `ps5_compat_mode` **does** suppress LED/haptic feedback writes in `_apply_feedback` (`bridge/vapi_bridge/dualshock_integration.py` ~3754–3767). L6B injection is a *separate* write path (`L6TriggerDriver._sync_write` → `triggerL/R.setMode/setForce`) that is **not** covered by that suppress — it is gated by `L6B_ENABLED` / campaign flags instead, and is known to cause dual-host disconnects when fired (`bridge/.env` L6B notes ~490–497). Net conclusion stands: **any mid-play HID output is operationally dead**. The fix is not "make L6B respect PS5_COMPAT"; the fix is **zero write during play**.

6. **Identity ceiling callout is correct** (EER ~29% out of scope) — keep it. Do not let continuous-presence wording drift into "this player is the enrolled human."

### Third lane (neither A nor B as written)

**Thesis C — external event-timed passive response (optical / semantic stimulus clock).**  
Use an **already-built** non-HID surface as the stimulus timestamp:
- Retina / killfeed / capture-daemon game events (snap, tackle, score change) bound by `session_id` (PoSP join key).
- After event_ts, look for involuntary controller INPUT signatures (accel delta band, L2B coupling spike, R2 onset clustering) in a human reaction window — **response only from INPUT**, stimulus time from the optical/semantic channel.

This is **not** Thesis A (no PS5 output-report read). It is **not** pure B (adds an external clock). It is Phase-2 optional because it depends on capture card + OCR quality (F-MATCH-* residue still real). Do **not** block the primary design on C.

**Thesis A′ (reject as primary):** unsupervised "rumble-like accel bursts" as proxy for game haptics — confusable with impact motion, no event ID, adversarial-easy to inject.

---

## 2. U1 finding — game haptic OUTPUT is **not** observable to the bridge

### Decision

**NO.** The bridge cannot observe the PS5→controller haptic / adaptive-trigger **command stream**. It only polls **controller INPUT** (sticks, triggers ADC, buttons, IMU, touchpad, battery, device sensor timestamp). Adaptive trigger **effect mode is write-only on real hardware** and is **not present in the HID input report**.

### Code evidence (authoritative)

**A. DualShock transport documents output-only modes on hardware**

`bridge/vapi_bridge/dualshock_integration.py` `_update_trigger_effect_modes` (approx. 3704–3719):

```text
In hardware mode: pydualsense does not expose the current trigger mode back in
the HID input report (trigger effects are output-only). We keep self._l2_effect_mode
and self._r2_effect_mode as authoritative state; they are updated by
set_trigger_effect() when the bridge deliberately sets an effect.
...
# Hardware mode: snap.l2_effect_mode is 0 (unreadable from HID report).
```

That is an explicit production comment: **mode bits are process-local state of what *this* process last wrote**, not a live echo of PS5 BT effects.

**B. Emulator / snapshot schema agrees**

`controller/dualshock_emulator.py`:
- L169: `# Adaptive trigger resistance mode (tracked state; write-only on real hardware)`
- L816–819: `# Phase 11: Adaptive trigger mode — output-only on hardware; read back with safe fallback.`  
  Read path is `getattr(ds.triggerL/R, 'mode', 0)` — last-set by **this** pydualsense instance, not PS5.

**C. Writes are a separate path (L6 / L6B / set_trigger_effect)**

- `bridge/controller/l6_trigger_driver.py` `L6TriggerDriver._sync_write` (L170–186): `triggerL/R.setMode` + `setForce` — **output only**; "pydualsense auto-commits on next **output report**."
- `dualshock_integration.set_trigger_effect` (L3721–3751): updates internal `_l2/_r2_effect_mode` then optionally forwards to hardware — never a "read game effect" API.

**D. PS5 coexistence forces read-only feedback**

`dualshock_integration._apply_feedback` (L3754–3767): when `ps5_compat_mode=True`, **all** LED/haptic HID output is suppressed ("bridge fully read-only — PoAC capture unaffected"). Confirms the operational posture of dual-host: **USB is a passive sensor pipe**.

**E. Biometric note: mode-change feature is structurally zero in NCAA CFB**

`controller/tinyml_biometric_fusion.py` L431–435:  
`trigger_resistance_change_rate` — "In NCAA Football 26, adaptive trigger modes are static throughout play … always 0.0". Even if modes were readable, CFB is a **static-resistance** game for this feature. That further kills "mode-transition as free game stimulus" for this corpus.

**F. What *is* readable (INPUT inventory that matters for B)**

From `InputSnapshot` / poll path (`controller/dualshock_emulator.py` + `dualshock_integration._poll_frames`):
- Sticks, L2/R2 **analog** levels, buttons, gyro/accel, touchpad, battery, `inter_frame_us`, `bt_seq_byte`, **`sensor_ts_ticks`** (device clock @ ~3 MHz from `states[28:32]` — F-RIG27-8 companion; **not** an effect-mode channel).

**G. Dual-host implication**

Even a perfect USB input-report echo would still only show **controller state**, not a signed "PS5 sent Rigid@force=200 at t=…". Without (event_id, intended force, send_ts) the bridge cannot run PoEP-style nonce-bound verify against game stimuli. U1 = **Thesis A dead for this architecture.**

### U1 corollary for the proposal

State in the proposal, machine-readable:

```text
game_haptic_output_observable = false
game_effect_mode_in_input_report = false
bridge_mid_play_hid_write_allowed = false   # dual-host + PS5_COMPAT posture
primary_thesis = B_passive_continuity
optional_phase2 = C_external_event_timed
```

---

## 3. Signal contribution — inventory Claude under-counted

Extend the open packet's inventory. **Do not rebuild** any of these; **bind**.

| Signal / primitive | Where | Role for real-play liveness |
|--------------------|-------|-----------------------------|
| Micro-tremor / FFT / band power / gravity postural | `controller/tinyml_biometric_fusion.py` | Core involuntary continuity (B) |
| AccelTremorFFT still-hold fallback | Phase 205/213 path in fusion + dualshock wiring | Tremor when sticks neutral (menus vs still-hold) |
| L2B IMU↔button causal latency | `controller/l2b_imu_press_correlation.py` (via bridge oracles) | Causal binding — hard for pure replay of button stream without IMU coupling |
| L2C stick↔IMU | `controller/l2c_stick_imu_correlation.py` | **CFB 27 caveat:** right stick is active in-play (profile `ncaa_cfb_27`); may leave neutral prior — do not assume CFB26 dead-zone forever |
| L4 Mahalanobis | live biometric vector | Anomaly / continuity **within** enrolled distribution — **not** identity claim |
| L5 temporal rhythm | rhythm oracle | Macro-bot timing regularity detector |
| AIT 4-feature | Phase 229 pipeline | Enrollment / separation; **not** mid-play liveness primary (structured probe) |
| **L6-Passive R2 onset EMA** | `dualshock_integration.py` ~2328–2368; `game_profile` `l6_passive_*` | **Missed in open packet.** Zero-write resistance / fatigue proxy during PS5 play — already safe under dual-host |
| **GAD `gameplay_context`** | Phase 235-GAD; `ACTIVE_GAMEPLAY` / `MENU_DETECTED` | Fail-closed gate: continuous-presence claim **must not count** pure menu windows |
| **PCC CaptureHealthMonitor** | `bridge/vapi_bridge/capture_continuity.py` | Capture integrity (NOMINAL / EXCLUSIVE_USB / grind_ready) — liveness without capture is theater |
| **PCC-SPC haptic-tolerance 3-signal** | `capture_continuity._haptic_tolerance_active` INV-PCC-004/005 | Treats haptic-induced poll dip as **still NOMINAL** when trigger_active + accel_var + tremor band bind — proves protocol already models "haptics hit the USB path as INPUT-side side effects," not as readable output commands |
| **GIC + consecutive_clean semantics** | grind chain + validator | Session-level continuity ledger; liveness claim should **reference** count-eligible windows, not invent a parallel chain |
| **`sensor_ts_ticks` / device_ts** | `InputSnapshot.sensor_ts_ticks`; L6b analyzer `crossing_device_ts` | U2 partial: device clock exists and is wired for **additive** latency companion; canonical latency still t_mono in places — any B windowing under Remote Play must prefer device_ts deltas where non-zero |
| PoEP / waveform / population_band | `l9_presence/*` | Bind **verdict shape** only; do not re-enable injection mid-play |
| PoSP SYNCHRONIZED | `l9_presence/posp.py` | Join key for multi-surface; real-play liveness should be an **advisory leaf** under PoSP, not a new FROZEN family |
| controller_presence fusion | `l9_presence/controller_presence.py` | Identity_bound × presence_candidate composition — reuse verdict vocabulary (SYNCHRONIZED_CONTROLLER etc.), keep `advances_poep_enabled=false` discipline |
| LivePresenceSignalingAgent | agent #34 | Optional operator UX vocabulary — not a proof surface |
| Frame checkpoints / replay ring | Phase 61 dualshock path | Offline adversary harness for B (replay recorded frames → detect freeze / loop) |

**Load-bearing miss:** L6-Passive + GAD + PCC/SPC together already form half of a **zero-injection play-continuity stack**. The novel work is the **composite claim + adversary gates + min window + fail-closed posture**, not a new sensor.

---

## 4. Steer

### Primary: **Thesis B** (pure passive continuity), composite, fail-closed advisory

**Reasoning:**
1. U1 kills A.
2. Dual-host + `PS5_COMPAT_MODE` + L6B disconnect history make zero HID write a hard operational law, not a preference.
3. The repo already streams the B ingredients at 1 kHz over USB without writing.
4. Continuous presence matches the problem statement's honest ceiling (population / embodied presence, not identity).

### Composite B formula (proposal must freeze this shape — values later)

A session window W is **live-human-continuous (advisory)** only if **all** hold:

1. **Capture integrity:** PCC `capture_state=NOMINAL` and host in `{EXCLUSIVE_USB, UNKNOWN}` for ≥ min_stable_s (reuse grind_ready discipline; do not invent a weaker bar).
2. **Gameplay gate:** GAD `ACTIVE_GAMEPLAY` fraction ≥ f_min over W (MENU_DETECTED windows do not contribute; NULL pre-GAD does not invent credit).
3. **Involuntary continuity:** tremor_peak_hz / micro_tremor / band power present with non-pathological stationarity (not frozen synthetic DC; not pure white-noise full-band).
4. **Causal binding:** L2B usable fraction above threshold when presses exist; L2C when stick game allows (CFB27 may help; CFB26 may neutral).
5. **Rhythm non-quantization:** L5 does not flag pure macro quantization across W.
6. **L6-Passive optional co-signal:** R2 onset series exists and is not constant-period machine-perfect (when profile enables it).

**Verdicts (machine):**
- `CONTINUOUS_PRESENT` — all gates pass for ≥ W_min
- `PARTIAL_PRESENT` — capture OK + tremor but causal/GAD thin
- `UNVERIFIABLE` — capture degraded, or menu-only, or window too short  
**Never** map these to CERTIFY/BLOCK tournament hard codes in v0 — **advisory only**, fail-closed (insufficient evidence → UNVERIFIABLE, not PASS).

### Secondary: Thesis C (optional Phase-2)

Only after B is specified. External event clock → passive response window. Same zero-write law. Do not claim PoEP-equivalence without nonce + measured latency band + device_ts.

### Explicit refutation

- **Do not** design a "read PS5 adaptive trigger mode from USB input report" epic — code + schema say it is not there.
- **Do not** re-enable L6B / L6 mid dual-host play as the solution (blocker is correct).
- **Do not** promote A′ unsupervised rumble-accel as primary (adversary-easy).

---

## 5. Adversary preview (top attacks)

| # | Attack | What it tries | B resistance | C resistance | A (if it were alive) |
|---|--------|---------------|--------------|--------------|----------------------|
| 1 | **Recorded stream replay** (USB HID dump → inject) | Fake a full match from a prior human capture | **Strong if multi-signal + non-loop checks:** frozen `sensor_ts_ticks` progression, inter_frame_us realism, L2B coupling, non-repeating tremor phase; pure button replay without IMU fails L2B/L2C. Weak if only tremor variance is checked. | Strong if optical surface is live and not the same recorded video | Would need matching event IDs — N/A (A dead) |
| 2 | **Synthetic-tremor bot** (8–12 Hz sinusoid + noise on accel) | Pass involuntary gate without human | **Medium:** add L2B/L5/GAD/L6-Passive; pure spectral mimicry fails causal latency + onset irregularity. Document residual: good ML bots remain open (same as L4 bot-vs-human limits). | Medium — still needs response coupling to real events | Spike-band after known stimulus harder to pre-gen without event stream |
| 3 | **Human relay / shared pad** | Real human physiology, wrong "player" or remote human | **Weak by design** — B proves *a* live human body on the pad, **not identity**. State this ceiling explicitly. | Weak same | Weak same |
| 4 | **Remote Play timing artifact (F-RIG27-8 class)** | Inflate/deflate latency windows; desync bridge t_mono | **Mitigate:** windowing and any latency-like feature must use `sensor_ts_ticks` deltas when non-zero; never sole-rely on bridge `t_mono` under RP. B continuity (spectral + coupling) is more robust than spike latency. | Event clock must be optical wall time, not RP-decoded frame time alone | Spike latency would be worst-hit — another reason A-style reflex without device_ts fails under RP |
| 5 | **Menu-AFK + idle tremor** *(add)* | Pad on desk, slight vibration, claim "playing" | **GAD MENU_DETECTED + trigger_active_fraction** fail-closed | Events won't fire | N/A |

**Best overall resistance for v0:** **B composite** against 1/2/4/5; **honest residual** on 3 (identity out of scope). C is additive later for spike-liveness flavor without HID write.

---

## 6. Build order — what Claude must nail in the next proposal (ranked)

1. **Pin U1 as CLOSED:NO in the proposal header** with citations (`dualshock_integration._update_trigger_effect_modes`, emulator write-only comments, L6 `_sync_write` output-only, `_apply_feedback` PS5 suppress). State `game_haptic_output_observable=false`. Kill Thesis A in one paragraph — do not leave it "open for engineering."

2. **Specify Composite-B gates + min window W_min + fail-closed UNVERIFIABLE** (reuse PCC grind_ready + GAD ACTIVE_GAMEPLAY + tremor + L2B + L5; L6-Passive co-signal). Give **default numbers as CANDIDATE** (e.g. W_min 60–120s continuous, or N count-eligible adjudication windows) and mark them measurement-gated — do not fake calibration.

3. **Adversary matrix in the proposal** for replay / synthetic-tremor / human-relay / RP-timing / menu-AFK with **which gate kills which**. Human-relay residual explicit.

4. **Commitment / domain-tag sketch (CANDIDATE only)** e.g. `QORTROLLER-REALPLAY-LIVE-v0` — hash over (session_id || window bounds || gate bitmap || feature digests || device_ts range). **Advisory leaf under PoSP** (`events_roots` parallel named root or presence fusion field). **No FROZEN-v1 promotion this loop.** `advances_poep_enabled=false`.

5. **Optional Thesis C appendix (non-blocking)** — optical/killfeed event_ts → passive response window; lists dependencies (retina daemon, F-MATCH residual honesty). Explicitly secondary.

6. **U2/U3 resolution plan (measurement, not code):**  
   - U2: offline replay of dual-host captures comparing tremor/L2B stability on `sensor_ts_ticks` vs t_mono; document RP inflation bound.  
   - U3: propose W_min ladder (30s advisory-thin / 120s default / match-length strong) with fail-closed below floor.

**Out of scope for r02 proposal:** any HID write path, flag flips, new Solidity, FROZEN edit, identity claims, "read PS5 effect mode" spike.

---

## build-results

| Item | Status |
|------|--------|
| Design-only charter | **HELD** — no application code, no tests added, no flag flips |
| BUILD-NOW code items | **None** (this round is OPEN/EXPAND design; envelope forbade code) |
| Artifact written | `docs/a2a/real-play-liveness/round-02-grok-expand.md` |
| Prior body sha256 verified | **MATCH** `88feb49be8ec67e0…` |
| Stage | operator stages/commits; single-committer=operator |
| PV-CI / PoAC / FROZEN | **untouched** |

---

## open-questions

For Claude's proposal / operator (not blocking the B steer):

1. **W_min policy:** Is the first ship target "per adjudication window (~session_adjudicator poll)" or "per match half"? Recommend start at adjudication-window aggregation toward consecutive_clean-compatible streaks.

2. **CFB 26 vs 27 L2C:** Confirm active profile for the first real-play validation night (`ncaa_cfb_26` vs `ncaa_cfb_27`) so L2C is either weighted or honestly neutral-prior.

3. **Thesis C enablement:** Operator want optical event-timed Phase-2 in the same proposal appendix, or strictly B-only until B gates stabilize?

4. **Naming:** Prefer binding under `controller_presence` verdict expansion vs a sibling `realplay_liveness` advisory field on PoSP — recommend sibling advisory to avoid overloading SYNCHRONIZED_CONTROLLER.

5. **U2 empirical:** Is there an existing dual-host capture set with `sensor_ts_ticks` populated end-to-end under Remote Play, or is first measurement a dedicated desk session?

---

## one-sentence handoff to Claude

**Thesis A is dead (U1=NO: effect modes output-only, USB is input-only under dual-host); build Composite-B zero-injection continuous presence from tremor+L2B+L5+GAD+PCC+L6-Passive, fail-closed advisory under PoSP, optional optical Thesis C later — no HID writes, no FROZEN.**
