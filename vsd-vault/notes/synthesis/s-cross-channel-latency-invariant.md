---
type: synthesis
id: s-cross-channel-latency-invariant
title: Cross-channel render-latency invariant — the forgery-resistant core (fake a channel's score, you cannot fake its shared lag)
created: 2026-06-28T14:06:00Z
modified: 2026-06-28T14:06:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 75
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

THE NOVEL PRIMITIVE. Sharpens [[s-multi-channel-presence-gate]] from "fuse channel scores" to a specific,
hard-to-forge consistency law: **every coupled channel in a genuine session must report the SAME input→screen
latency, because they all traverse ONE physical render+encode+network+decode pipeline.** The gate's verdict is
not `mean(scores) > threshold` — it is `coupled_channels share a lag distribution with low spread`.

WHY THIS IS STRONGER THAN ANY SCORE GATE. Each oracle already returns a `lag_ms` at its best |Pearson r| (the
trigger→HUD oracle exposes `lag_ms` directly; the geometric oracle the same). Consider the channels and the
distinct screen events they lag-bind to your live input:
- B1 muzzle flash: R2 fire → center-low luminance spike.
- B2 kill/down marker: R2 fire → red marker at reticle (a kill-conditioned subset).
- Geometric: right-stick → global screen pan (phaseCorrelate, see [[s-wgc-fps-processing-wall-resolved]]).
- Recoil ([[s-recoil-compensation-coupling]]): fire → upward camera kick → your compensating down-stick.
- ADS ([[s-ads-fov-coupling-channel]]): L2 → FOV-zoom optical transient.

These are FIVE physically-independent input→pixel paths. In a real session they share the same wire, GPU, and
stream, so their measured lags cluster (call it L ± jitter). An adversary attacking the gate must now defeat a
**joint** constraint: forging B2's score (e.g. firing along to spectated combat) produces a lag that is NOT
bound to L — the spectated screen's events run on the *streamer's* clock, not the attacker's trigger. The
attack that beat single-channel B2 (margin 0.02) cannot beat "B2's lag equals B1's lag equals the geometric
lag," because the attacker would have to make five unrelated screen phenomena all lag-lock to their own
trigger simultaneously — which requires actually being the one driving the rendering pipeline. That is the
definition of presence.

THE METRIC (design sketch, to calibrate). Per burst, collect `{lag_b1, lag_b2, lag_geo, lag_recoil, lag_ads}`
for the channels that cleared their own activity gate. Define `lag_spread = robust dispersion (IQR or MAD) of
the present lags` and require (a) ≥2 channels coupled AND (b) `lag_spread <= TAU_LAG` AND (c) each present
channel's time-shuffled null collapses. Verdict PRESENT iff all three. The single shared latency L is itself a
useful by-product (the session's measured glass-to-glass lag) — useful to the coaching/accessibility surface.

WHY IT DEFEATS THE GCAP/SPECTATE FAMILY CLEANLY. A replay you watch can fake screen *motion* (geometric) but
its motion lag is not bound to your stick; an active-spectate POV can fake a *kill marker* (B2) but its lag is
not bound to your trigger; neither can make the two lags EQUAL each other AND equal to a flash lag AND an ADS
lag. The forger has to fake N channels each with the SAME fabricated lag derived from THEIR input — and they
have no rendering pipeline of their own that the victim's screen obeys. Cross-channel lag agreement is the
property only co-located physical authorship produces.

OPEN GATE (`likely`). The invariant is principled but the dispersion threshold TAU_LAG and the FAR of
"k-of-n channels agree" are UNMEASURED. Calibration: capture genuine multi-channel sessions (lag clusters) vs
the active-spectate / replay-along negatives the B2 audit already collected, and fit TAU_LAG to separate
agree-from-disagree, not score-from-score. Until that lands, this stays the design spine, not a certified gate.
No FROZEN-v1 / 228B PoAC / chain / IOTX touched; advisory presence layer only.
