---
type: synthesis
id: s-usb-bt-dual-stability-module-notification
title: Sustaining exclusive USB capture to laptop while preserving stable BT gameplay link to PS5; preventive measures against "module not attached" notifications
created: 2026-06-26T13:05:00Z
modified: 2026-06-26T13:05:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 90
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: ["phase_235_pcc_dual_connection_clarification.md", "capture_continuity.py", "bridge_agent.py:get_usb_stability_status", "config.py:ps5_compat_mode"]
---

USER QUERY (VSD cycle 24): What should be done to sustain exclusive USB connection from DualShock Edge to laptop (for high-rate PCC/biometric capture) while the controller maintains BT connection to PS5 for actual gameplay? How can QorTroller create a preventative mechanism so that "PS5 module not attached" (or equivalent wireless module state) notifications do not break the controller's ability to send input to the PS5 while it is simultaneously connected to the QorTroller bridge over USB?

## Current Ground Truth (Phase 234.7 / 235)

- Dual USB-to-laptop + BT-to-PS5 is the **only supported grind topology** (Phase 235 clarification). CaptureHealthMonitor infers EXCLUSIVE_USB purely from USB poll-rate mean >=900 Hz and CV < 0.20. It is deliberately blind to BT.
- `ps5_compat_mode` (PS5_COMPAT_MODE env, default false) already exists (Phase 131B) exactly to solve write-induced problems: any HID output (LED, haptic, adaptive trigger) over USB causes micro-drops on the USB channel that the PS5 interprets as reconnects, surfacing notifications.
- When ps5_compat_mode=True the bridge suppresses output reports; USB remains read-heavy for biometrics. `get_usb_stability_status` and usb_reconnect_log track this.
- grind_ready gate: NOMINAL + (EXCLUSIVE_USB or UNKNOWN) + sustained window.

The "module not attached" notification the operator is hitting is distinct from (or a superset of) the reconnects caused by writes. It indicates the controller's internal wireless/BT module state is being reported to the PS5 as detached or the PS5 stack believes the controller has switched primary host, even when writes are suppressed.

## W1 (failure mode)

If the controller firmware (or the Sony BT stack on PS5) treats "USB data host present" as "wireless module detached / controller attached to PC", then simply opening a stable high-rate USB HID channel for capture is sufficient to trigger the module-not-attached state. This breaks gameplay input on the PS5 side even with zero output writes from the bridge. Current ps5_compat_mode only protects against *write*-induced drops; it does not defend the module-presence invariant.

Consequence for grind: session_counting_paused or CONTESTED, or worse — the player cannot actually play the game on PS5 while the capture link is active, defeating the entire consecutive_clean collection purpose.

## W2 (QorTroller-native opportunity)

QorTroller can own the "capture tap" model: the laptop is a passive high-fidelity observer on the USB channel while the PS5 remains the authoritative game host on BT. By making the USB presence invisible or non-authoritative to the controller's wireless module state (at the levels we can control), we turn the dual-connection from "fragile hack" into a first-class, operator-fire-and-forget grind primitive. This directly advances the 100 consecutive_clean target and staged graduation.

## Proposed Preventative Measures (actionable)

1. **Auto-activate and enforce read-only capture mode during grind** (highest leverage, code change)
   - In main.py or grind startup, when grind_mode=True: force cfg.ps5_compat_mode=True for the session (or introduce stronger `capture_only_mode`).
   - Gate every possible output path (haptic, LED, adaptive trigger profiles, player LEDs) behind `not (grind_mode and ps5_bt_expected)`.
   - Expose in /bridge/capture-health: `ps5_bt_protected: true`, `hid_writes_suppressed: true`.
   - On grind start, log loudly: "PS5 BT gameplay protection active — USB is capture-only read tap."

2. **Preventive host arbitration / device open strategy**
   - In dualshock_integration / transports: when opening the HID device for grind, prefer read/ feature-report only access patterns if the underlying hidapi / windows HID allows it.
   - Avoid claiming output/report ID paths that cause the controller to re-enumerate its "attached host" or power the wireless module differently.
   - Add a clean "enter_capture_tap()" / "exit_capture_tap()" that closes/reopens the device with explicit flags if needed.

3. **OS-level and pairing procedure hardening (docs + optional auto-check)**
   - Update phase_235_grind_start_procedure.md and dual-connection clarification:
     - Pair and verify BT to PS5 + launch NCAA CFB 26 *first*.
     - Only then plug USB data cable to laptop.
     - In Windows Device Manager (or via PowerShell): ensure "Allow the computer to turn off this device" is **unchecked** for the DualShock Edge.
     - Use rear USB 3.x port on motherboard or a powered hub known not to cause re-enum.
   - Optional bridge startup check (best-effort): use Windows SetupAPI or powercfg to detect and warn if the device power management is set to allow suspend.

4. **Detection of module-notification impact**
   - Extend CaptureHealthMonitor or add CoexistenceHealth: watch for secondary signals that the BT link is suffering (e.g. sudden gaps in certain button timing that would be present on PS5 input, or explicit report fields if any indicate wireless state).
   - If USB is EXCLUSIVE_USB but operator or heuristics detect "game not receiving expected input", surface "BT module risk — verify PS5 shows controller connected without 'module not attached'".
   - Log to a new usb_bt_coexistence_log table (similar to usb_reconnect_log).

5. **Future / firmware lever (Path A / joypad-os)**
   - In controller firmware, maintain wireless module power and BT link state independently of USB enumeration. Treat USB as a pure sensor-tap interface.
   - Expose a "preserve_wireless" mode or report that the host can set on USB attach to tell the controller "do not demote BT module".

6. **User / operator tooling**
   - Add a dedicated `POST /bridge/enter-ps5-coexistence` (or auto on grind) that:
     - Sets ps5_compat_mode
     - Optionally restarts the transport cleanly
     - Returns current host_state + protection flags
   - Surface in the Gamer View dashboard the dual-state clearly: "USB capture (EXCLUSIVE) | BT gameplay protected".

## Immediate next steps (low risk)

- Make PS5_COMPAT_MODE=true the default when GRIND_MODE=true in config loading or grind preflight (Phase 235-GPC).
- Gate haptic/LED writes in the relevant driver/profile code with the flag.
- Add one regression test that with ps5_compat_mode the transport performs zero output reports during a simulated grind window.
- Update the grind procedure doc with the exact pairing-then-plug sequence and the Device Manager power setting.

This keeps the canonical high-rate USB capture path while making the BT gameplay link as robust as the controller firmware permits. The "exclusive USB to laptop for capture" requirement is preserved because PCC and biometric features (especially accel FFT, high-rate timing) need the ~1000 Hz channel.

## Invariant alignment

Does not touch 228B PoAC, FROZEN primitives, or on-chain. Purely improves reliability of the existing dual-connection capture path used for consecutive_clean collection. Aligns with PCC fail-closed philosophy and gamer sovereignty (gameplay remains on the player's PS5).

---
This synthesis note is routine (loop-authorable). A decision note would be required only if we chose to change defaults that affect non-grind users.
