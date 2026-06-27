---
type: synthesis
id: s-nqpv-capture-regime-resolution-scope
title: NQPV capture-regime resolution scope — a REAL human-positive L4/IMU corpus needs a DIRECT-USB session (laptop = active host), not dual-connection NCAA-on-PS5; plus the dependent p_L4 anchor re-derivation. Honest: this fixes blind capture, NOT the presence-oracle unlock.
created: 2026-06-26T18:10:00Z
modified: 2026-06-26T18:10:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 80
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes the resolution of the two standing items from the live capture investigation
([[project_dualconnection_capture_blind_finding]]): (1) the dual-connection biometric blindness that
makes today's co-capture rows degenerate, and (2) the dependent p_L4 formula/threshold scale mismatch.
This is the operator/hardware gate; the note records the path + the honest ceiling. No code change here.

THE BLOCKER (measured, not theorized): during dual-connection (USB→laptop + BT→PS5 both live) the USB
HID frames carry NO live input/motion — accel_entropy=0/100, the operator move+trigger test produced
zero signal, l4_distance exploded to 159–220, and the BT-drop natural experiment collapsed it to 4.3.
The Edge reports real input only to its ACTIVE host (PS5). So a REAL human-positive L4/IMU corpus
CANNOT be built from NCAA-on-PS5 play.

THE RESOLUTION (the path that already worked once): capture in a DIRECT-USB regime where the LAPTOP is
the controller's active host — exactly how the historical sessions/hw_* N=74 corpus was built (real
accel entropy 3–8.6 bits). Concretely a DEDICATED NQPV calibration-capture session: controller plugged
into the laptop ONLY (no BT→PS5 bond), operator performs the calibration probe (still-hold tremor /
trigger pulls / stick) OR plays a PC-side game, so IMU + trigger telemetry flows over USB → real L4
features → real humanity_prob → real co-capture rows (cco + l4l5l6 GENUINELY live, not frozen).

STRUCTURAL SEPARATION (the load-bearing reframe): the GIC grind (dual-connection, NCAA-on-PS5,
consecutive_clean — does NOT need humanity>0.5) and the NQPV biometric corpus (direct-USB, real L4
features) are DIFFERENT capture activities on the same hardware. Conflating them is what produced the
degenerate rows. NCAA being PS5-exclusive is fine — the biometric corpus simply doesn't come from NCAA.

THE HONEST CEILING (do not overclaim the fix): even with direct-USB REAL features, the PRESENCE oracles
(PoEP + coupled-retina screen witness) still ABSTAIN (PoEP behind its L6B N>=50 gate; screen lobe
hardware-gated). So direct-USB lands in the COCAPTURE regime with REAL data — which the cycle-31/32
harness ALREADY PROVED still FAILs to separate (replay carries real HW + real physics). So this
capture-regime fix solves the BLIND-CAPTURE problem, NOT the certification unlock. Its real value: (a) a
genuine non-degenerate human corpus to validate the pipeline end-to-end; (b) the substrate to re-derive
+ validate the p_L4 fix against real data; (c) readiness for the moment a presence oracle goes live.

DEPENDENT ITEM — p_L4 anchor re-derivation: `_p_l4 = exp(-(d-2.0))` (dualshock_integration.py:1792)
gives pL4=0.0067 at the L4 NOMINAL threshold (7.009) — mis-scaled, so even perfect features cap humanity
low. Re-anchor so distance≈threshold maps to ~0.5, re-derived AGAINST the real direct-USB corpus (NOT
guessed). HARD RULE: per-player L4 thresholds can only tighten, never loosen; this is the humanity
fusion mapping (documented in CLAUDE.md), so it is a careful re-derivation, not a blind edit — its own
follow-on VSD cycle once a real corpus exists. Moot until the corpus is non-degenerate (can't fit a
mapping over absent data).

RECOMMENDATION (operator decision): run a short DIRECT-USB calibration-capture session (NQPV_COCAPTURE_
ENABLED already on) to seed a real human corpus; defer the p_L4 re-derivation to a follow-on cycle keyed
to that corpus; keep presence-oracle liveness (PoEP gate / camera rig) as the separate certification
track. HONESTY RAILS: measurement-first; NQPV stays advisory/default-off; no FROZEN-v1/228B PoAC/chain/
IOTX; the auto-reconnect safety net (61b12640) already covers reader-break recovery. Related:
[[s-nqpv-study-corpus-harness-built]], [[s-nqpv-persistence-presence-liveness-scope]],
[[project_dualconnection_capture_blind_finding]], [[l9-presence-arc]].
