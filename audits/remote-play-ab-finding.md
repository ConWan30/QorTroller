# Remote Play A/B finding — Remote Play resolves dual-connection biometric blindness

**Date:** 2026-06-26 · **Probe:** `scripts/remote_play_ab_probe.py` · **Data:** `audits/remote-play-ab-latest.json`

## Question
Dual-connection capture (USB→laptop + BT→PS5, play on TV) is biometrically blind: the USB HID frames carry
no live input while the PS5 is the active host (prior finding). Does playing *through* PS Remote Play (PS5
streamed to the laptop) (1) keep capture NOMINAL — not CONTESTED — and (2) make L4/IMU come alive?

## Result (75 s window each, live play)

| Metric | A: dual-connection | B: Remote Play |
|---|---|---|
| capture_state | NOMINAL 14/14 | NOMINAL 14/14 |
| host_state | EXCLUSIVE_USB 14/14 | EXCLUSIVE_USB 14/14 |
| poll-rate mean | 2129 Hz | 1908 Hz |
| poll-rate CV | 0.140 | **0.044** |
| contested | False | False |
| **L4/L5/L6 ok fraction** | 0.265 | **1.000** |
| **controller-lobe CLEAN fraction** | 0.353 | **1.000** |
| humanity_prob mean | 0.40 | 0.52 |
| controller_signal dist | ANOMALY 22 / CLEAN 12 | **CLEAN 40 / 0** |

## Conclusion — both birds
1. **Capture stays NOMINAL.** Remote Play did NOT cause CONTESTED; it was *more* stable (CV 0.140 → 0.044).
   The CLAUDE.md "Remote Play USB/audio traffic → CONTESTED" risk did not materialize in this setup.
2. **L4 comes fully alive.** L4/L5/L6 ok 27% → **100%**; controller-lobe 65% ANOMALY → **100% CLEAN**.
   Playing through Remote Play makes the controller the laptop's USB active host, so the HID carries live
   input — the dual-connection blindness is resolved.

## Implication
Remote Play is the **live-biometric-capture path** for the PS5-exclusive NCAA CFB 26: full L4/L5/L6 + clean
controller-lobe WHILE playing. It also makes the BT-contention angle concrete — Remote Play is a *known
benign streaming source* (the `streaming_source_active` input to `assess_contention`), so any contention it
introduces leans BENIGN, not adversarial. humanity_prob rose (0.40 → 0.52) but is still below the 0.60
passport gate — that is the live p_L4 mapping (conservative; `l4_humanity_reanchor_enabled` is the separate
tuning lever), not a capture problem. NEXT: bridge hot-loop wiring for the QorTroller Retina Game Capture
(dense per-frame HID + coupled-retina) now has a live, biometrically-rich Remote Play stream to fuse.
