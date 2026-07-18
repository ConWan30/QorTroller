# Rig-4 wrap — CFB 27 / PoEP (2026-07-18)

**Outcome:** No `SYNCHRONIZED_CONTROLLER` (both launches).
**Launch 1** (13:20–13:47 CT): no nonce-bound fires — Claude hit a session limit before Shell B.
**Launch 2** (16:26+ CT): **9 real-hardware fires** — F-RIG27-8 device clock confirmed **dead on silicon under RP**;
honest `IDENTITY_ONLY` (see Launch 2 below).

## What landed earlier today (pre-rig / mid-session)
- F-RIG27-8 device-clock latency **committed** `c7ba84b7` (A2A PASS after r03 dead-wire FIX).
- SYNC-GO preflight CLI **committed** `782df5a9` (`--wait-active-s 45` exit 3, `--amplitude` clamp 80).
- F-RIG27-6 fire-timeout already in tree (20s/25s); F-RIG27-7 LEAN pattern known from rig-3.

## Launch 1 (Claude LEAN + campaign, then Claude limit)
| Signal | Result |
|--------|--------|
| Bridge | UP ~13:20–13:47+ CT on :8080; `presence_lean.db` |
| Campaign ring | L6b analyzer init for RING CAPTURE ONLY; `l6b_enabled` stayed False |
| Capture (while playing) | NOMINAL / EXCLUSIVE_USB / bridge_main_reader; poll ~1.8–2.5 kHz; trigger frac up to ~0.6 |
| PoEP fires | **dispatch=0 resolve=0** — Claude hit session limit before Shell B fire |
| `clock=device` / `clock=t_mono` | **0** (nothing to measure without fires) |
| SYNCHRONIZED_CONTROLLER | **Not reached** (strict watch: no real verdict) |
| Starvation | 19 events, max excess **6.83s** (mild vs rig-3's 42/61s) |
| Retina | Kept re-arming via `auto_edge_connect` despite PRESENCE_LEAN_MODE (~60+ arms) |
| Spend / flags | Kill-switch held; no flag flips observed in log |

Monitors (stopped on operator "done with rig"): `audits/rig4-monitor-status.jsonl`,
`audits/rig4-handoff-claude-limit-2026-07-18.md`.

---

## Launch 2 (16:26+ CT) — 9 real fires · F-RIG27-8 silicon confirmation + reflex-signal finding

**Spend:** 0 IOTX · **Flag flips:** none (`L6B_ENABLED`/`poep_enabled`/`L6_CHALLENGES_ENABLED` stay False;
`CHAIN_SUBMISSION_PAUSED` held) · `bridge/.env` **untouched** (process-scoped env only).

### Setup
- **Topology (operator-confirmed):** `USB→PC + PS Remote Play` — pad's active host is THIS PC; RP carries
  input to the PS5. `EXCLUSIVE_USB`, `live_activity_source=bridge_main_reader`, `poll≈2300 Hz` (rig-3 topology).
- **Bridge env (process-scoped):** `PRESENCE_LEAN_MODE=true POEP_CAMPAIGN_MODE=true POEP_LIVE_FIRE_ENABLED=1
  POEP_FIRE_TIMEOUT_S=20 GAME_PROFILE_ID=ncaa_cfb_27` + retina/DA/replay/NQPV disables. Startup confirmed
  `POEP-CAMPAIGN: L6b analyzer initialized for RING CAPTURE ONLY`.
- **Device:** registered Edge `581a836c98b3a1b6…` (ioID tokenId 498, `id_verified=true`).
- **Fire path:** `POST /operator/operator/poep/fire` (doubled-prefix), `{nonce, amplitude:80}`, ring mode
  `rigid r2_force=80`. Endpoint arms + awaits (fail-closed 504 on timeout).

### The live attach (SYNC-GO)
`poep_session_identity_attach.py --live --wait-active-s 45 --amplitude 80 --challenges 2`
- Cold attempt → correctly **exit 3** (operator in menu). Warm attempt → preflight **READY** at
  `live_trigger_active_fraction=0.05` during active play.
- Artifact `audits/poep_session_identity_attach_861f1bae2f5db734.json`: verdict **`IDENTITY_ONLY`**,
  `identity_bound=true` (ioID 498), `live_seal_valid=true`, `mode=live`, `effective_live=true`,
  **`live_hardware=true`**, `gameplay_active_fraction=1.0`, **`n_go_issued=1`** (min 2),
  **`n_go_verify_pass=0`** (min 2) → `go_ok=false`. Honest progress vs the prior cold attach (`n_go=0`).

### The 9 real-hardware fires (all `real_hardware=true`, all `dev_lat=-1.0`)
| # | reaction style | t_mono lat (ms) | peak (LSB) | post_n | dev_lat |
|---|---|---|---|---|---|
| 1 | attach GO (during play) | 4279 | 2395 | 378 | **-1.0** |
| 2 | primed (natural) | 4692 | 2753 | 412 | **-1.0** |
| 3 | sharp flick + freeze | **-1.0 (no peak)** | 376 | 447 | **-1.0** |
| 4 | sharp flick + freeze | **-1.0 (no peak)** | 62 | 420 | **-1.0** |
| 5 | sharp flick + freeze | **-1.0 (no peak)** | 459 | 351 | **-1.0** |
| 6 | (larger move) | 3918 | 892 | 398 | **-1.0** |
| 7 | big whole-controller jerk | 2286 | 2224 | 387 | **-1.0** |
| 8 | big whole-controller jerk | 1423 | 4354 | 374 | **-1.0** |
| 9 | big whole-controller jerk | **1199** | 3541 | 368 | **-1.0** |

### Finding (three compounding issues; wiring ruled out)
Device-clock wiring **confirmed intact end-to-end** by static read (`poll()→sensor_ts_ticks (_states[28:32])
→_build_l6b_report.device_ts →_l6b_pre/post_buffer →analyzer.crossing_device_ts →_rp_device_latency_ms`), so
`dev_lat=-1.0` is a **data/silicon** result, not a plumbing bug.

1. **F-RIG27-8 device clock is DEAD on silicon under RP** — `dev_lat=-1.0` on **all 9** fires, including #7–#9
   where a clean t_mono peak *was* found at 1.2–2.3 s. Strong hypothesis: `sensor_ts_ticks` reads **0** in the
   RP/session-loop frame path (offset 28 not carrying the DualSense sensor counter under Remote Play). Not yet
   split from the span>500ms branch — no fire landed t_mono <500ms, and even #9 (1199ms) would reject on span —
   so the raw-tick log (NEXT-i) is required to settle dead-wire vs span-reject.
2. **t_mono latency tracks reaction quality but floors ~1.2 s.** 4.7 s (natural) → **1.2 s** (big fast jerk),
   monotonically improving #7→#9. So t_mono is not a fixed huge inflation — it responds to the real reaction —
   but its floor here is ~4–5× above the 80–280 ms band ceiling.
3. **The clean trigger reflex is invisible to the IMU accel analyzer.** A sharp R2 flick barely moves the
   controller — peaks **62–459 LSB**, below the reflex threshold → `lat=-1.0` (no reflex). Only large whole-hand
   movements (2200–4400 LSB) register, later/larger than the trigger reflex itself. The analyzer keys on IMU
   accel; the actual R2 reaction lives on the **R2 analog channel**.

**Consequence:** `SYNCHRONIZED_CONTROLLER` is **not reachable** under RP with the current reflex mechanism.
Only the device clock could reveal whether the *true* reaction is sub-280 ms (band-reachable) or genuinely
~1.2 s (trigger-reflex-under-RP unviable) — and the device clock is dead. Fixing it is the #1 unblocker.

### Next increments (ferry to grok, charter (a); fresh build session)
- **(i) F-RIG27-8b — raw-tick instrumentation (log-only, non-gating):** add `crossing_device_ts` +
  `poep_probe_device_ts` to the `POEP-HID-RING: resolve` log line → one rig fire splits dead-wire vs
  span-reject. Cheapest, do first.
- **(ii) Trigger-channel reflex (bigger lever):** detect the reaction on the **R2 analog channel** (trigger
  value drop/re-press after the tug) rather than IMU accel — the clean reflex #3–#5 showed is invisible to accel.
- **(iii) Accel reflex threshold review:** the 62–459 LSB clean-flick regime shows the threshold currently
  excludes real trigger reflexes.

### Honest claim ceiling
9 real-hardware fires, real active play (`gameplay_active_fraction=1.0`), real reflex peaks — but **no reflex
landed in the 80–280 ms band**, so `n_go_verify_pass=0` and the verdict is `IDENTITY_ONLY`. No SYNCHRONIZED
claim. `poep_enabled`/`L6B_ENABLED`/`L6_CHALLENGES_ENABLED` stay False; corpus/band/verdict untouched; zero
spend; `bridge/.env` untouched. Rig-3 pipeline-E2E win stands; this is the silicon confirmation that
F-RIG27-8's device clock does **not** yet rescue latency on the real Edge under RP.
