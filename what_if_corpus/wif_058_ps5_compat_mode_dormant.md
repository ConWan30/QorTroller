# WHAT_IF Entry -- AutoResearch Wiki Loop Inaugural Real-World Observation (2026-04-26)

**Source**: Operator field report during Phase 235 grind setup; verified by code-citation walk
**Phase**: 238 (Phase 238 = MetaLearner FSCA wiring; this WIF seeds the wiki self-learning corpus)
**Validation**: PENDING_AUTORESEARCH (this entry IS the inaugural observation; no prior cycle)

---

## WIF-058 -- PS5_COMPAT_MODE Fix Exists in Code but Dormant in Live Bridge Config

**Operator-observed symptom**: While VAPI bridge is running on the laptop and DualShock Edge
is dual-connected (USB-C to laptop + BT to PS5), the PS5 intermittently displays a
notification that the controller's "stick attachments are not correct" and prompts a BT
reconnect. The user reasonably suspected haptic motors / vibration motors / tremor capture
output writes were the trigger.

**W1 -- Failure mode (verified by code citation)**:

The exact failure mode the operator is experiencing is *already documented in the codebase*
as a known Phase 131B issue, and a fix already exists — but the fix is not active in the
live bridge configuration.

Evidence chain:

1. `bridge/vapi_bridge/dualshock_integration.py:2196-2209` — docstring on
   `_apply_feedback()` explicitly states:
   > "DualShock Edge USB writes (set_led/haptic) briefly drop the USB connection, causing
   > the simultaneously-paired PS5 to show 'controller modules are not correct' and request
   > a BT reconnect. Suppressing writes makes the bridge fully read-only — PoAC capture
   > unaffected."

2. `bridge/vapi_bridge/dualshock_integration.py:2212-2217` — `_apply_feedback()` actively
   issues HID output writes per adjudication:
   - `set_led(0, 128, 255)` for INFER_SKILLED
   - `set_led(255, 0, 0)` + `haptic(200, 200)` for cheat detection
   - `set_led(0, 255, 0)` for clean play

3. `bridge/vapi_bridge/dualshock_integration.py:2207-2209` — guard:
   ```python
   if getattr(self._cfg, "ps5_compat_mode", False):
       return
   ```
   Returns early (suppresses ALL HID writes) only when `ps5_compat_mode=True`.

4. `bridge/vapi_bridge/config.py:1059-1067` — `ps5_compat_mode` defaults to `False` and reads
   the env var `PS5_COMPAT_MODE`:
   ```python
   ps5_compat_mode: bool = field(
       default_factory=lambda: _env("PS5_COMPAT_MODE", "false").lower() == "true"
   )
   ```

5. `bridge/.env` — `PS5_COMPAT_MODE` is **not set**. `grep -n "PS5_COMPAT_MODE" bridge/.env`
   returns no match. Therefore live config has `ps5_compat_mode=False`, HID writes proceed,
   and the documented failure mode triggers.

6. `bridge/vapi_bridge/dualshock_integration.py:1684-1689` — the bridge already auto-emits
   the literal remediation as a `log.warning`:
   > "USB instability detected — %d consecutive `_apply_feedback` timeouts (iter=%d).
   > PS5 reconnect notifications likely. Set PS5_COMPAT_MODE=true to suppress HID output
   > writes."

**Crucial observation**: the operator's hypothesis ("haptic motors / tremor / vibration are
the cause") is *exactly correct* and is the root-cause attribution captured in code. The
issue is not a missing feature — it is a config flag that ships dormant by default. The
trade-off (per `config.py:1066`) is loss of LED color and haptic feedback on adjudication;
PoAC capture is read-only and unaffected.

**Why this is the inaugural autoresearch wiki loop entry**:

This is the first observation the autoresearch loop should seed against, because it is a
*pure operator-experience gap* that is invisible to all current automated layers:

- FSCA does not detect it (no contradiction rule fires; no fleet coherence violation).
- PV-CI does not detect it (no invariant violated; the code is correct).
- The grind chain does not detect it (PoAC capture is unaffected; GIC continues stamping).
- The bridge-side `usb_reconnect_log` (Phase 131B, store.py) only fires after
  `_FEEDBACK_SKIP_THRESHOLD * 2` consecutive `_apply_feedback` timeouts — this is reactive,
  not preventive, and only logs after the PS5 has already prompted reconnect several times.

The autoresearch loop's value is in surfacing dormant fixes whose activation is gated only
by operator awareness — not new code.

**W2 -- Opportunity (immediate)**:

Activate the existing fix by adding one line to `bridge/.env`:

```
PS5_COMPAT_MODE=true
```

Then restart the bridge. After restart, `_apply_feedback()` returns early
(`dualshock_integration.py:2207-2209`); no `set_led` or `haptic` write reaches the HID
output report; the USB connection no longer drops on adjudication; the PS5 stops prompting
"controller modules not correct."

Trade-off accepted (per `config.py:1066`): no LED color or haptic feedback during gameplay.
This is the design intent — the docstring at `config.py:1067` explicitly says "PoAC
biometric capture is completely unaffected — read-only, zero data impact."

**W2 -- Opportunity (downstream — Phase 239+ candidate)**:

Make `PS5_COMPAT_MODE=true` the *default* when the bridge detects dual-host arbitration
(EXCLUSIVE_USB host_state from `capture_continuity.py` AND a recent BT pairing event /
HID device-info indicating PS5 attachment).

Concrete sketch (NOT for Phase 238 — surfaces only as a candidate for downstream work):

- `capture_continuity.py:CaptureHealthMonitor._infer_host_state()` already classifies
  EXCLUSIVE_USB vs CONTESTED via poll-rate CV. It does not have direct visibility into BT
  pairing state on the controller side.
- A future heuristic: if `ps5_compat_mode=False` AND `_apply_feedback` timeouts exceed
  `_FEEDBACK_SKIP_THRESHOLD` even once, auto-flip the in-process `cfg.ps5_compat_mode` to
  True (with a single log.warning + persistence to `usb_reconnect_log` for audit). This
  converts the existing reactive log line into a self-healing default while preserving the
  trade-off disclosure.

**Status**: OPEN — operator action required (one-line `bridge/.env` edit + bridge restart).

**Why this seeds the autoresearch wiki loop usefully**:

The autoresearch cycle's `format_cycle_prompt()` (Phase 238 wiring, `vapi_autoresearch.py`)
now embeds the active FSCA contradiction list. WIF-058 is what FSCA *cannot* see — it is a
config-state gap, not a code or data contradiction. Surfacing it in the WIF corpus gives the
loop its first instance of a problem class:

> "Dormant fix in code, gated by operator-only config knob, with no automated detection
> path."

Future autoresearch cycles can compare incoming operator reports against this template and
identify other dormant fixes by the same shape (config flag default + log.warning
remediation already in code).
