---
type: synthesis
id: s-presence-lean-mode-build-plan
title: Lean Presence Mode — the lag is the BRIDGE (~38% CPU: agents+5.4GB DB+grind+provenance), NOT capture and NOT Remote Play (bridge-down=PERFECT, operator-confirmed). Meticulous build plan for a PRESENCE_LEAN_MODE that runs only DualShock+retina+coupling+duty-cycle, gating off the heavy stack + fresh small DB. Supersedes cycle-46 process-isolation premise (refuted live).
created: 2026-06-27T12:30:00Z
modified: 2026-06-27T12:30:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 360
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

EMPIRICAL FINDINGS (live debugging session 2026-06-27, measured not assumed — supersedes the cycle-46
process-isolation premise, which assumed GIL contention):
- **THE DECISIVE A/B: bridge-down = PERFECT gameplay (operator-confirmed).** So the lag is 100% the bridge —
  NOT Remote Play, NOT the laptop GPU. The laptop runs Remote Play perfectly on its own. There is NO intrinsic
  ceiling; if the presence capture is light enough, gameplay stays perfect.
- **The bridge adds ~38% system CPU** (Get-Counter: 73% bridge-on / 35% bridge-off, 8 logical cores). That
  load is the AGENT FLEET (~30 agents) + the 5.4GB DB (every query slow) + grind + per-record provenance
  (DA/W3bstream/PDA) — the ambient-floor stack. It is NOT the capture (capture was in burst mode / mostly off
  during the measurement). This CPU competes with Remote Play's decoder -> continuous lag.
- GPU is motion-driven (videodecode ~68-84% during active BR even bridge-OFF) but that alone does NOT lag the
  game (bridge-down=perfect) — the laptop handles it. So the GPU observer-effect from capture is secondary to
  the bridge's CPU drag.
- **cycle-46 process-isolation REFUTED:** a standalone subprocess got only ~13fps WHILE the bridge ran (not 32)
  -> the contention is cross-process CPU, not the Python GIL -> a subprocess doesn't help. The fix is to make
  the bridge LIGHT, not to move the capture out of it.
- Other banked wins this session (keep): McAfee-VPN was throttling the Remote Play stream (raw 16->29fps when
  killed); **COUPLED_CLEAN proven (coupling 0.348 @ 13.6fps)** stream-unlocked -> the oracle works over Remote
  Play; WGC `stop()` was a silent no-op BUG (WindowsCapture has no stop(); only the CaptureControl from
  start_free_threaded() does) -> FIXED; duty-cycle PresenceBurstController built+tested (capture in bursts,
  stop between -> GPU freed); the WGC `minimum_update_interval` rate-cap is INEFFECTIVE for lag (the capture
  SESSION's existence is the cost, not its delivery rate); burst coupling is weaker than continuous (cold-start
  re-baseline: 6s->~0.05, 15s->~0.15 vs continuous 0.35) -> needs the cycle-45 calibration for a burst-mode
  FAR-safe threshold (the ~0.15 is still ~6x the null, real coupling below the uncalibrated 0.20).

GOAL: `PRESENCE_LEAN_MODE` — a bridge that runs ONLY what presence-over-Remote-Play needs (DualShock HID +
retina/coupling + duty-cycle capture), gating off the ~38% CPU driver, so gameplay stays ~perfect AND a
presence proof is produced. Full protocol (agents/grind/attestation/chain) is a SEPARATE heavy session
(or post-play), never on the live-play hot path.

METICULOUS BUILD PLAN:
  S0 (verify-first) — read `main.py::run()` in full and map the spawn order: confirmed so far the DualShock
     transport spawns at ~1183-1240 (KEEP), the MINIMAL_TASK_MODE park returns at 1169/1181 BEFORE dualshock
     (so MINIMAL_TASK_MODE is UNUSABLE — it kills dualshock), and the ~30-agent fleet + grind + reconcilers +
     monitors spawn AFTER 1240. Enumerate the exact line span of that post-dualshock heavy block — that span
     is what the lean flag gates.
  S1 — config: add `presence_lean_mode: bool` (env `PRESENCE_LEAN_MODE`, default False) to config.py.
  S2 (load-bearing) — main.py: wrap the post-dualshock AGENT-FLEET spawn block in `if not
     self.cfg.presence_lean_mode:`. KEEP outside the gate: DualShock transport, loop_health_monitor, uvicorn,
     and the retina/presence-burst wiring (which lives in the dualshock integration). Result: lean mode boots
     uvicorn + dualshock + retina + presence-burst ONLY.
  S3 — provenance off on the hot path: in lean mode force RETINA_DA_UPLOAD / W3BSTREAM_ENFORCE / PDA and the
     NQPV co-capture persist OFF (per-record I/O). Cleanest: lean-mode overrides these cfg getters at
     construction (a `_lean_override` in config or guards at the call sites). Keep retina PERCEPTION + GAME
     CAPTURE + coupling on (the light part).
  S4 — fresh small DB: in lean mode point the store at `~/.vapi/presence_lean.db` (fresh, tiny) instead of the
     5.4GB bridge.db, so DB ops are fast. Resolve via db_path_resolver.py / the store path config. (The lean
     session's records are presence-scoped; the heavy DB is for the full protocol.)
  S5 — grind off: lean mode forces grind_mode=False (skip GIC/grind processing + its DB writes).
  S6 (verify) — restart lean; measure system CPU via Get-Counter (TARGET: down from 73% toward ~40-45% =
     ~35% Remote-Play baseline + single-digit lean bridge); confirm dualshock+retina alive (/bridge/capture-
     health + RGC diag); operator judges feel (TARGET: ~perfect, matching bridge-down). Then fire a duty-cycle/
     on-demand burst -> COUPLED_CLEAN (at the cycle-45-calibrated burst threshold).
  S7 — tests: lean mode skips the agent spawn (assert the task set excludes the fleet) + keeps dualshock;
     config flag default-off; provenance-off in lean. + the already-green PresenceBurstController (6) + stop-fix
     regression (6).

HONESTY RAILS: lean mode is the LIVE-PLAY presence-capture path; it deliberately does NOT run the full
protocol (agents/grind/attestation) — the cryptographic attestation (PoAC/chain/ZKBA) runs in a separate
non-lean session or post-play, NEVER on the hot path. Burst coupling stays advisory until the cycle-45
calibration sets the FAR-safe burst threshold. No FROZEN-v1 / 228B PoAC / chain / IOTX. The 4 controller-side
pillars (L4/L5/L6 + L9 controller-lobe) run lean-and-lag-free; the screen/coupling pillar runs via the
duty-cycle. Related: [[s-retina-remote-play-process-isolation]] (refuted premise),
[[s-coupling-threshold-calibration]], [[project_retina_phase0_live_starvation_finding]],
[[recursive_verification_first_pattern]].
