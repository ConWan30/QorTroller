---
type: synthesis
id: s-usb-bt-tether-pulse-generator-design
title: Novel "Synchronized Module Tether Pulses" (SMTP) — Code locations, design for tether pulse generator, and integration points for dual USB+BT grind stability
created: 2026-06-26T13:40:00Z
modified: 2026-06-26T13:40:00Z
phase: VSD-LOOP cycle 24
status: draft
confidence: likely
effort: 120
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["s-usb-bt-dual-stability-module-notification", "phase_235_pcc_dual_connection_clarification.md", "dualshock_integration.py:2600", "capture_continuity.py"]
---

## VSD Cycle 24 Context (this note)

This note was produced as part of advancing VSD cycle 24 to address the operator request for a *novel* preventative mechanism beyond passive ps5_compat_mode suppression.

It provides:
- Exact code locations for the dual-connection / feedback / grind surfaces.
- A small, implementable design sketch for the "Tether Pulse Generator".
- Suggested integration points and minimal diff shape.
- Path to turning this into a small tracked feature (e.g. Phase 24X or tracked in next synthesis).

Harness/PV-CI status at emission time: PV-CI PASS (182). Harness shows expected VSD-2 manifest findings for newly authored notes (full orchestrator signing step required for clean ledger append).

---

## 1. Specific Code Locations (current as of 2026-06-26)

### A. ps5_compat_mode check + output suppression (core existing mitigation)

**File**: bridge/vapi_bridge/dualshock_integration.py

- **_apply_feedback** (central gate):
  ```python
  # ~2600-2614
  def _apply_feedback(self, inference: int):
      ...
      if getattr(self._cfg, "ps5_compat_mode", False):
          return
      # then does set_led / haptic
  ```

- Warning log when timeouts occur (suggests the flag):
  ~1969-1972

- Trigger effect path (also needs gating):
  ~2598: set_trigger_effect hardware forward

- L6/haptic delivery sites that reuse the driver:
  ~2304: if ... and self._l6_driver is not None

### B. Config surface

**File**: bridge/vapi_bridge/config.py

- `ps5_compat_mode`:
  ```python
  # ~1540
  ps5_compat_mode: bool = field(
      default_factory=lambda: _env("PS5_COMPAT_MODE", "false").lower() == "true"
  )
  """Phase 131B — ... When True: ALL HID output writes ... suppressed"""
  ```

- Grind related (for auto-activation logic):
  ```python
  # ~2325
  grind_mode: bool = ...
  grind_target: int = ...
  grind_session_id: str = ...
  # plus pcc_* fields for grind_ready
  ```

- Live presence haptic awareness of the flag (~3258).

### C. PCC / grind_ready + host state (where dual mode is declared "ready")

**File**: bridge/vapi_bridge/capture_continuity.py

- Definition:
  ```python
  # ~26
  grind_ready = (capture_state == NOMINAL) AND
                (host_state in {EXCLUSIVE_USB, UNKNOWN}) AND
                (sustained at NOMINAL for >= pcc_stable_window_s seconds)
  ```

- Class + methods:
  - CaptureHealthMonitor.__init__ and _recompute (~56+)
  - _is_grind_ready_locked (~376)
  - is_grind_ready() (~192)
  - HostState inference (_infer_host_state)

- Integration point for "tether enabled" flag will live here or a small companion.

### D. L6 / haptic delivery surface (the actual output mechanism we will extend)

**File**: bridge/controller/l6_trigger_driver.py  (imported as bridge.controller...)

- Main classes:
  - L6TriggerDriver
  - ChallengeSequencer
  - Uses pydualsense: ds.triggerL / ds.triggerR .setMode() / .setForce(index, value)

**Usage in bridge**:
- Initialized in dualshock_integration.py ~485:
  ```python
  from bridge.controller.l6_trigger_driver import L6TriggerDriver, L6_CAPTURE_MODE
  self._l6_driver = L6TriggerDriver(...)
  ```
- Reused for controlled delivery ~2304.

### E. Grind preflight / startup surfaces

**File**: bridge/vapi_bridge/main.py

- Startup logging + GRIND_SESSION_ID guard (~827-837)
- PCC monitor wiring (~965):
  ```python
  self._pcc_monitor = CaptureHealthMonitor(cfg=self.cfg)
  ```
- Prerequisite evaluation (~1148-1154): evaluate_prerequisites, TransportSnapshot

**Related**:
- operator_api/agent_misc.py : /agent/usb-stability-status and grind endpoints.
- store/calibration.py and _core.py : usb_reconnect_log + ps5_compat_mode_active columns.
- live_presence_signaling_agent.py : already ps5_compat aware.

**Docs** (must be updated):
- docs/phase_235_grind_start_procedure.md
- docs/phase_235_pcc_dual_connection_clarification.md

---

## 2. Draft Design: Tether Pulse Generator (small, self-contained)

**Goal**: When in dual-grind + EXCLUSIVE_USB, emit minimal "module tether" actuations on the adaptive triggers that keep the controller firmware's wireless module state anchored to "attached to PS5", without:
- Being perceptible to the player.
- Polluting the BT game input path.
- Causing extra USB instability.

### Proposed component

New file or addition: `bridge/vapi_bridge/tether_pulse_generator.py` (or inside dualshock_integration as a helper class).

```python
# draft
from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class TetherConfig:
    enabled: bool = False
    amplitude_max: int = 12          # 0-255 LSB on trigger force
    duration_ms: int = 35
    duty_cycle_s: float = 1.2        # min time between pulses
    use_player_rhythm: bool = True   # sync to recent trigger/stick events

class TetherPulseGenerator:
    def __init__(self, cfg: TetherConfig, l6_driver=None, ds_reader=None):
        self.cfg = cfg
        self._l6 = l6_driver
        self._ds = ds_reader.ds if ds_reader else None
        self._last_pulse = 0.0
        self._recent_rhythm = deque(maxlen=8)  # timestamps or force samples

    def update_biomarker(self, trigger_force: float, ts: float):
        """Called from the hot biometric path (after feature extraction)."""
        if self.cfg.use_player_rhythm:
            self._recent_rhythm.append((ts, trigger_force))

    def maybe_send_tether(self, now: float) -> bool:
        if not self.cfg.enabled or not self._ds:
            return False
        if now - self._last_pulse < self.cfg.duty_cycle_s:
            return False

        amp = self._compute_adaptive_amplitude()
        if amp <= 0:
            return False

        # Prefer L6 driver if available (it already uses to_thread + safe restore)
        if self._l6:
            # reuse or call a new lightweight "micro_profile"
            self._l6.send_micro_tether(  # new method we would add
                side="R", amp=amp, dur_ms=self.cfg.duration_ms
            )
        else:
            # fallback direct (riskier, same path as current _apply_feedback)
            try:
                self._ds.triggerR.setForce(0, amp)  # or appropriate index
            except Exception:
                return False

        self._last_pulse = now
        return True

    def _compute_adaptive_amplitude(self) -> int:
        if not self._recent_rhythm:
            return 0
        # simple: small fraction of recent average force, clamped
        avg = sum(f for _, f in self._recent_rhythm) / len(self._recent_rhythm)
        amp = max(2, min(self.cfg.amplitude_max, int(avg * 0.06)))
        return amp
```

### Integration points (minimal)

1. In `config.py`:
   ```python
   dual_grind_tether_enabled: bool = field(
       default_factory=lambda: _env_bool("DUAL_GRIND_TETHER_ENABLED", "true")
   )
   dual_grind_tether_amplitude_max: int = ...
   ```

2. In `capture_continuity.py` (or a new small monitor):
   - When `grind_ready` and host_state == EXCLUSIVE_USB and a "bt_expected" flag:
     - Expose `tether_should_be_active`.

3. In `dualshock_integration.py`:
   - In the per-frame / per-interval loop (after bio feature extraction):
     ```python
     if self._tether_gen:
         self._tether_gen.update_biomarker(current_trigger_r, time.time())
         self._tether_gen.maybe_send_tether(time.time())
     ```
   - Init the generator when grind_mode and tether config is on.
   - Respect ps5_compat_mode (tether is the *controlled exception* to pure suppression).

4. In L6 driver (`bridge/controller/l6_trigger_driver.py`):
   - Add `send_micro_tether(self, side: str, amp: int, dur_ms: int)` that:
     - Temporarily sets a low force on the appropriate trigger.
     - Uses the existing to_thread pattern.
     - Immediately restores baseline (profile 0 or previous).

5. In grind preflight / main.py startup:
   - If grind_mode and tether_enabled: log "Module tether active for PS5 BT stability".

6. Health surface:
   - Add to CaptureHealthResult / GET /bridge/capture-health: `tether_active`, `last_tether_ts`, `tether_pulses_sent`.

### Safety rails (must have)

- Amplitude hard-capped (default 12/255 ~4.7%).
- Minimum interval between pulses.
- Only when recent player activity detected (rhythm not zero).
- Never during L6 active challenge windows.
- Easy kill switch via config/env (defaults safe).
- Count and expose pulses sent for audit (ties into existing usb_reconnect_log pattern).

### Validation

- Grind session with dual connection + tether on vs off.
- Operator confirms no "module not attached" messages on PS5 for 30+ min clean play.
- USB poll rate remains NOMINAL + low CV.
- Player subjective: no noticeable extra resistance.
- Add a simple unit test in bridge/tests for the amplitude calculation + duty cycle.

---

## 3. Path to Formal Phase / Feature

This can be tracked as a small targeted improvement (suggested name: "Cycle 25+ — Dual-Grind BT Module Tether" or tracked under PCC/grind).

It does **not** require:
- New FROZEN primitives
- On-chain changes
- Changes to PoAC wire
- New agent fleet members (small extension inside existing PCC + dualshock paths)

## 4. Experiment Results (Cycle 25 post-run)

- Full VSD cycle 25 executed successfully (synthesizer --cycle 25):
  - harness: PASS (0 findings)
  - pv_ci: PASS (182)
  - mythos: 0
  - ledger 25 entry includes s-usb-bt-dual-stability-module-notification + s-usb-bt-tether-pulse-generator-design
  - new corpus snapshot + live VPM label
- Prototype implemented:
  - Config flags added (DUAL_GRIND_TETHER_ENABLED etc.)
  - bridge/vapi_bridge/tether_pulse_generator.py (TetherPulseGenerator + TetherConfig)
  - Wired in dualshock_integration.py (init after L6, feed + tick after PCC update_sample using _last_bio_features as rhythm proxy)
  - send_action uses L6 path when available + direct triggerR.setForce prototype (logs always)
- Simulation (scripts/experiment_tether_pulse.py):
  - With fake ~sinusoidal R2 rhythm: emitted 3 low-amp pulses (2..9 <=12 cap) over ~3s demo.
  - Duty and amp clamping observed in behavior.
  - Conclusion from sim: "use case has potential" — controlled tethers are feasible without high duty or high force.
- No breakage to VSD (notes/harness unaffected by .py additions) or existing PCC/compat paths (gated behind new flag, default off).

## 5. Hardware Validation — Real Dual-Grind Session (Cycle 25)

**Operator report (USB laptop + BT PS5, tether flag ON, L6B disabled, ps5_compat active):**

- Duration: ~33 minutes of clean consecutive play.
- Bridge metrics: NOMINAL 33/33 samples; host state EXCLUSIVE_USB 61% + UNKNOWN 39%; **zero CONTESTED, zero disconnects, zero module events**.
- PS5 side (direct operator observation): **No "module not attached" notifications at any point**. Gameplay felt normal throughout. R2 tether forces were imperceptible.

**Verdict against original acceptance criteria:**

| Criterion                              | Result |
|----------------------------------------|--------|
| Sustained EXCLUSIVE_USB-class capture  | ✅ NOMINAL throughout; no CONTESTED |
| Zero "module not attached" notifications | ✅ None observed |
| Gameplay works                         | ✅ Normal throughout |
| Sub-perceptible                        | ✅ Imperceptible R2 |
| No bridge-side instability             | ✅ Zero reconnect/disconnect/module events |

**By the stated bar** ("flag on → stable + zero notifications"), Cycle 25's hardware run **passes**.

**Hardware A/B Validation — ON→OFF→ON (Legs A/B/C)**

Bridge-side data from a controlled toggle sequence (L6B disabled, ps5_compat active throughout):

| Leg | tether | dur  | NOMINAL | DISCONNECTED | EXCLUSIVE_USB | PS5 observation                  |
|-----|--------|------|---------|--------------|---------------|----------------------------------|
| A   | ON     | 7.9m | 93/93   | 0            | 100%          | no popups                        |
| B   | OFF    | 5.9m | 54/69   | 14 (20%)     | 77%           | module popup + disconnect        |
| C   | ON     | 9.5m | 88/89   | 1 (1%)       | 76%           | no popups (confirmed; 1 transient blip on bridge, no events) |

**Pattern**: Clean (A) → Flapping (B, only when OFF) → Clean (C). All 14 disconnects appeared exclusively in the OFF leg. The flap was in the middle leg, ruling out time-drift or progressive degradation (Leg C would be worst if that were the case).

This is strong causal evidence: the tether appears protective. Bridge metrics remained excellent in both ON legs; the PS5-side "module not attached" symptom reproduced only when the tether was off.

**Upgraded verdict**
- Tether is safe + the dual-grind setup is stable with it on: **highly-likely**
- Tether pulses are causally responsible for suppressing the module notifications: **likely** (reproduced clean-flap-clean signature with control arm)

**Remaining notes**
- Pulse firing was not logged at INFO (DEBUG off during measurement).
- Longer sessions or repeated toggles would further increase confidence.

The bridge remained stable with tether ON after Leg C.

This A/B data substantially strengthens the Cycle 25 hardware claim beyond the initial single-window observation.

**Status**: Verified findings committed and pushed (Cycle 25). Harness + PV-CI clean at time of commit. Bridge remained stable post-Leg C with tether ON.
