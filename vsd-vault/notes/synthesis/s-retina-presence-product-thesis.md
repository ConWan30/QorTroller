---
type: synthesis
id: s-retina-presence-product-thesis
title: Retina Presence — WGC/HUD input↔screen causal-presence attestation as a standalone product (the screen must agree with the controller)
created: 2026-06-28T14:05:00Z
modified: 2026-06-28T14:05:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

PRODUCT THESIS. The B1/B2 trigger→HUD work is not just another PITL advisory layer — it is the seed of a
**standalone product**: *input↔screen causal-presence attestation*. The pitch in one line: **a certified
controller emits 1000 Hz ground-truth telemetry; the screen is the rendered consequence; if the screen
causally agrees with the controller at the session's single render+stream latency, a live human authored
both.** This is a category the existing anti-cheat market does not occupy — kernel anti-cheats (Vanguard,
RICOCHET, EAC) inspect the *machine*; Retina Presence inspects the *causal bond between the human's input and
the pixels it produced*, and needs no kernel driver, no client trust, and no biometric identity claim.

WHY IT IS A PRODUCT, NOT A FEATURE. The thing the market cannot currently do is attest a player over an
**untrusted client** — the cloud-gaming-bot stealth pattern named in the BT-calibration anchor (WormVision
Lite, the GeForce-NOW attestation gap, RICOCHET conceding the input-stream side). A bot streaming into a
cloud session injects *input*; it cannot make the *remote screen* causally respond to a trigger it pulled at
the victim's actual pipeline lag. Retina Presence turns that gap into the product's core claim. It runs
entirely off-device (the operator's own capture box / sidecar), so it is deployable by a tournament, a
platform, or a streamer without touching the game or the anti-cheat the publisher already ships — it is
**additive trust**, not a replacement, which is the only way a third party gets to deploy anti-cheat at all.

THE MOAT IS NOT ANY ONE CHANNEL — IT IS THEIR SHARED CLOCK. B2 alone is forgeable (the live calibration found
active-spectate negatives at 0.26 vs a kill-min of 0.28 — a ~0.02 margin; see the B2 calibration audit). The
defensible primitive is the **cross-channel render-latency invariant** ([[s-cross-channel-latency-invariant]]):
B1 (flash), B2 (kill marker), the geometric stick→pan channel, recoil-compensation
([[s-recoil-compensation-coupling]]), and the new ADS/FOV channel ([[s-ads-fov-coupling-channel]]) each
independently estimate the input→screen lag. A genuine session has ONE physical pipeline → all coupled
channels must agree on the SAME lag within jitter. A forger can fake one channel's *score*; it cannot make
that channel's *lag* agree with the others, because it does not share the victim's pipeline clock. The product
sells the consistency invariant, not the channels.

POSITIONING. This is the physics-of-play thesis ([[s-physics-of-play-attestation-thesis]]) made into a
shippable surface, and the input-grounded-screen-authorship framing ([[s-posca-input-grounded-screen-authorship]])
made into a claim a customer pays for. Anti-cheat is the lead market; the same primitive resells across five
adjacent purposes ([[s-retina-presence-cross-purpose-map]]) — streamer "Verified Live", remote-tournament
admission, marketplace authored-gameplay provenance, manufacturer device-cert tiers, and a non-adversarial
coaching/accessibility instrument. One causal primitive, many buyers.

OPEN GATE (why `likely`, not `certain`). The invariant is sound in principle and the channels exist, but the
cross-channel-lag-agreement separation is UNCALIBRATED — no measured FAR for "all channels agree" vs a forger
who fakes a subset. The B2 audit is the only live data point and it says the single channel is too thin. The
product claim stands or falls on the multi-channel lag-agreement campaign, not on any one coupling score.
No FROZEN-v1 / 228B PoAC / chain / IOTX touched; design-only, advisory presence layer.
