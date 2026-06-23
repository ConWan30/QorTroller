---
type: synthesis
id: s-feature-fusion-enhancements
title: QorTroller enhancement leverage lives in fusing its own primitives
created: 2026-06-23T00:00:00Z
modified: 2026-06-23T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: possible
effort: 35
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Thesis: QorTroller's strongest enhancements are FUSIONS of primitives it already has, not new
bolt-ons. Each fusion below is grounded in shipped code; each is a hypothesis (confidence:
possible) gated on operator GO + the Stage-A measurements, NOT a shipped claim. See
[[s-purpose-of-vapi]] for the verification-over-assertion frame this all serves.

F1 — TRI-WITNESS CO-PRESENCE. Fuse three INDEPENDENT physical channels into one session
attestation: (a) L9/PoCP causal coupling (input->output, `InputOutputCouplingOracle`
coupling_score/lag_ms), (b) retina dual-lobe causal coherence (controller INPUT lobe x OCR HUD
OUTCOME lobe), (c) RF co-presence (Qorvo UWB QM35825 outreach + the canonical BT-witness
anchor). A cloud-relay bot can fake one channel, not all three at once. Defeats the exact
cloud-gaming-bot stealth pattern the BT calibration anchor names. Honest limit: retina coupling
is WEAK on dead-zone-stick games (NCAA finding — injection axis was dropped); UWB is
partner-gated (Qorvo response pending).

F2 — RECENCY-BOUND LIVING PRESENCE. Fuse PoSR temporal beacon (FROZEN-v1 #14) x PoCP x GIC:
the proof is simultaneously causally-live AND unable to backdate/replay. Closes the
relay+replay seam that either primitive alone leaves open. Arc 6 already built the beacon; the
fusion is binding it to the causal-presence verdict.

F3 — FORCE-CURVE-ANCHORED PRESENCE (not identity). Fuse the adaptive-trigger force-curve
(Sensor Stack v2.1 Surface 1 = PRIMARY DISCRIMINATOR, the moat) x L4 Mahalanobis x a VPM
honesty label. Yields per-session "this controller, this hand, now" — wearing a closed-enum
VPM label so it CANNOT overclaim cross-session identity (CROSS-LESSON-001 / same-model
separability study still open). The VPM grammar is the guardrail that keeps the fusion honest.

F4 — SOVEREIGN DATA-ECONOMY FUSION. Fuse consent manifest (gamer-address-keyed) x ZKBA x
marketplace buyer-category ZK verifier: a buyer proves category-eligibility in zero-knowledge,
the gamer sells verified-human gameplay data, raw biometrics never leave the gamer. Arcs 1-6 +
Phase 238 already shipped most pieces; the fusion is the end-to-end sovereign sale path.

F5 — THE PROVENANCE QUADRILLE. GIC (cognitive) + WEC (operational) + CORPUS-SNAPSHOT (corpus)
+ SIC (methodology) anchored together = full-stack provenance over BOTH the product and the
process that builds it. VSD-emits-VPM (this session) is the first concrete step: it binds the
methodology chain to the protocol's own visual-honesty grammar. Anchoring the SIC head on
IoTeX (as GIC_100 was) would close the quadrille — operator-fired, not autonomous.

What makes QorTroller *itself*: it is the only protocol where the physical-input source is also
the cryptographic agency-holder. Every fusion above deepens that — more independent physical
evidence (F1/F2/F3), more gamer sovereignty over the resulting data (F4), more verifiable
provenance over the whole stack (F5) — without ever asserting what it cannot prove.
