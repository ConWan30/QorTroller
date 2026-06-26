---
type: synthesis
id: s-presence-oracle-liveness-scope
title: Presence-oracle liveness scope (the NQPV certification unlock) — PoEP (calibration-gated, N>=50 L6B at 1000Hz) + coupled-retina screen witness (hardware-gated, camera rig); both thread into the co-capture meta already wired in cycle-33(b); mostly GATED, not an immediate build
created: 2026-06-26T20:05:00Z
modified: 2026-06-26T20:05:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 130
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes the SOLE remaining NQPV certification unlock surfaced across cycles 31-36
([[project_dualconnection_capture_blind_finding]]): making the two PRESENCE oracles live. The study
harness proved the fusion separates humans from adversaries ONLY when these are live (l4l5l6+cco alone
FAIL — replay carries human physics). Honest upfront: this is largely a CALIBRATION + HARDWARE roadmap,
not an immediate agent build — the heavy gates (N>=50 L6B campaign, camera rig) are out of agent reach.
The agent-buildable parts are the WIRING (oracle -> co-capture meta) + readiness checks + default-off
activation logic. Both oracles already have a consumption point: cocapture_fields_from_pitl_meta reads
meta["poep_present"] + meta["retina_coupled_verdict"] (the cycle-33(b) forward-compat plumbing) — so the
moment each oracle WRITES its value live, the co-capture rows carry it and the offline adapter + harness
re-run UNCHANGED into the regime that separates.

TRACK 1 — PoEP liveness (calibration-gated). State: l9_presence/poep.py + poep_calibration.py BUILT
through P2 (population reflex-band model + per-device adaptive-trigger force signature + the N>=50 gate);
poep_enabled=False; liveness_score returns "calibration_incomplete" until N>=50; activation = "P4".
Liveness is POPULATION-level (a live human's reaction falls in the empirical reflex band; bot/replay/
anticipation does not) — so it needs N>=50 in-band reactions ACROSS the population (poep_l9/*.poep.json,
currently ~0), NOT a per-person identity corpus; the 5-player validation from the L9 arc is the seed.
CROSS-LINK to the just-closed capture-regime work: PoEP measures the 80-280ms adaptive-trigger reflex
latency, so the L6B campaign MUST capture at 1000 Hz (the capture_session.py / l6b_calibration_capture.py
high-rate path) — the same 120Hz-throttle that degraded the L4 spectral features would blur the reflex
band. AGENT-BUILDABLE NOW: (a) L6B/PoEP capture-campaign tooling at 1000Hz (verify l6b_calibration_
capture.py rate + the challenge-response capture); (b) P4 activation logic (liveness_score -> verdict,
gated on N>=50 AND poep_enabled, two-key); (c) the poep_present -> meta["poep_present"] thread in the
live session loop (default-off; the co-capture consumer already exists); (d) a poep-readiness check
(N vs 50). GATED (operator/hardware): the actual N>=50 challenge-response campaign + the two-key
poep_enabled flip (P4). HARD RULE: L6B_ENABLED stays false; no liveness verdict until N>=50.

TRACK 2 — coupled-retina screen witness (hardware-gated). State: retina_screen_lobe.parse_hud +
screen_retina_fusion.fuse_screen_retina (L9FusionVerdict LIVE_COHERENT / COUPLED_CLEAN / ...) +
retina_causal_coherence BUILT, but consumed only OFFLINE in oracle_panel over SessionArtifact streams —
NOT in the live session loop. Live inputs fuse_screen_retina needs: coupling_score / negative_control /
decoupled_energy from cv_motion (a CAMERA tracking the stick vs on-screen motion) + coherence from HUD
OCR (parse_hud). GATE: a live camera observing BOTH the screen and the controller (the capture rig; PRs
#50/#51 held). NCAA CAVEAT (banked): NCAA's auto-camera makes the coupling residual axis a false-positive
source -> the residual axis is DROPPED and the usable NCAA verdict is COUPLED_CLEAN (presence) not
LIVE_COHERENT (presence+causal); a manual-camera game could reach LIVE_COHERENT. AGENT-BUILDABLE NOW:
(a) thread the live camera -> cv_motion -> fuse_screen_retina -> meta["retina_coupled_verdict"] into the
session loop behind a default-off flag (lift the offline oracle_panel screen-fusion into a live producer);
(b) graceful degrade to ABSTAIN (None) when no camera. GATED (hardware): the physical camera rig + the
held capture-rig PRs.

CONVERGENCE + the full certification dependency chain (honest — presence oracles are NECESSARY, not
SUFFICIENT): (1) PoEP live (N>=50 1000Hz campaign -> P4 flip) -> meta["poep_present"]; (2) coupled-retina
live (camera rig -> live screen-fusion) -> meta["retina_coupled_verdict"]; (3) re-run the study (offline
adapter + harness) in the now-FULL regime -> measure human-TAR/adversary-FAR + the mandatory anti-GCAP
rail; (4) STILL need real ADVERSARY captures (synthetic today) for an empirical FAR (FULL tier); (5)
STILL need BREADTH (N>=50 humans, currently 1) for a population/tournament claim. Only when (3)+(4)+(5)
pass does the operator promote (flip nqpv_enabled + adopt the validated live p_L4 re-anchor). So this
scope unblocks the REGIME that can separate; certification additionally needs real adversaries + breadth.

SEQUENCING RECOMMENDATION: PoEP Track 1 first (its agent-buildable wiring + the 1000Hz L6B campaign reuse
the just-validated capture path; no new hardware beyond the controller), then coupled-retina Track 2
(needs the camera rig). Each track is its own focused build cycle when the operator opens its gate.

HONESTY RAILS: NQPV stays advisory/default-off; both oracle threads ship default-off + abstain-when-
absent; no FROZEN-v1 / 228B PoAC / chain / IOTX; the L6B N>=50 + poep_enabled two-key + the camera rig
are operator/hardware decisions this scope does NOT pre-empt. Related: [[s-nqpv-corpus-adapter-scope]],
[[s-nqpv-capture-regime-resolution-scope]], [[project_dualconnection_capture_blind_finding]],
[[l9-presence-arc]], [[project_l9_retina_fusion_capture_rig]].
