---
type: synthesis
id: s-ads-fov-coupling-channel
title: ADS/L2 → FOV-zoom coupling — a sustained third channel (the WGC-when-aiming signal between shots)
created: 2026-06-28T14:07:00Z
modified: 2026-06-28T14:07:00Z
phase: VSD-LOOP
status: draft
confidence: possible
effort: 50
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

THE GAP THIS FILLS. B1 (flash) and B2 (kill marker) are DISCRETE-event channels — they only emit when you
fire / get a hit, so presence coverage is spiky and the firing-activity gate abstains the rest of the time.
The operator's question about "WGC capturing when aiming" points at the missing piece: **aiming-down-sights
is a SUSTAINED, optically-deterministic screen transition that is its own coupling channel** and covers the
between-shots interval the discrete channels miss.

THE PHYSICS. In Warzone-class FPS, pressing L2 (ADS) deterministically drives an on-screen transition the
renderer cannot decline: field-of-view narrows (the whole frame scales up about the center), a scope/iron-sight
overlay fades in, aim-sway damps, and many guns add a vignette. All of these are large, center-weighted,
content-independent luminance/scale events — far easier to detect than a muzzle flash. The couple is:
predictor = L2 trigger position (hold-shaped, not a spike); measured = a center-region SCALE/zoom estimator
(the existing phaseCorrelate machinery already produces a global scale term alongside the pan; or a simpler
center-vs-annulus luminance-ratio that jumps on FOV change). COUPLING = causal-lag Pearson, identical
machinery to the trigger→HUD oracle, plus the mandatory time-shuffled null.

WHY IT IS ARCHITECTURALLY VALUABLE (not just another channel):
1. SUSTAINED, not spiky. ADS is held for seconds; it yields a high-sample-density correlation window even
   when you are not firing, so the cross-channel latency invariant ([[s-cross-channel-latency-invariant]]) has
   a continuously-present channel to anchor lag-agreement against — closing the coverage gaps between B1/B2
   bursts that [[s-presence-oracle-liveness-scope]] flagged.
2. HARD TO FAKE ALONG. ADS is a binary state with a clean optical signature; a spectate-along attacker would
   have to ADS in lockstep with the spectated player's FOV changes, which (unlike firing into ambient combat)
   are not frequent enough to catch by chance — the active-spectate hot-negative that beat B2 does not
   transfer to a sustained-state channel.
3. RECOIL-READY. ADS is the precondition for aimed fire, so an ADS-coupled window is exactly where
   recoil-compensation counter-coupling ([[s-recoil-compensation-coupling]]) is measurable — the two channels
   reinforce in the same time window.

DESIGN SKETCH. New extractor `center_zoom_transient(frame)` (center-box mean / annulus mean, or reuse the
phaseCorrelate scale output); new oracle reuses `TriggerHudCouplingOracle` with the L2 axis as predictor and a
WIDER hold-shaped lag window (FOV transition render is a ramp, not an impulse). Default-off, advisory, env-gated
like the B1/B2 channels.

OPEN GATE (`possible` — design-only, unmeasured). No capture has been run; the zoom-estimator's separability,
the right lag window for a ramp (vs B1's impulse), and whether per-gun FOV multipliers need normalization are
all open. First pass: log `center_zoom_transient` alongside the existing `trigger-hud burst:` lines during an
ADS-heavy session and check the L2↔zoom causal coupling vs its shuffled null, exactly as the B2 calibration
pass did. No FROZEN-v1 / 228B PoAC / chain / IOTX touched; advisory presence layer only.
