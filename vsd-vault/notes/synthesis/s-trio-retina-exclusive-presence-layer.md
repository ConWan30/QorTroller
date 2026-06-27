---
type: synthesis
id: s-trio-retina-exclusive-presence-layer
title: Elevate Trio-Retina to QorTroller's exclusive PRESENCE layer — causal coherence dissolves the L4 identity-enrollment wall
created: 2026-06-26T00:00:00Z
modified: 2026-06-26T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Operator asked: what if Trio-Retina became an EXCLUSIVE QorTroller perception layer, as it could be?
This note records why that is not just viable but is the architecturally-correct resolution to the
wall the last three cycles circled — and names the two prerequisites honestly so it isn't promoted
on assertion. Ties off the arc of [[s-bt-capture-topology-inversion]] /
[[s-bt-capture-research-validation]] / [[s-l4-baseline-injection-boundary]].

WHAT TRIO-RETINA ALREADY IS (grounded, not aspirational): a built-but-advisory subsystem the code
itself frames as a "QorTroller-exclusive fusion," with three lobes —
  - CONTROLLER lobe (retina_controller_embedder): the INPUT world model, explicitly "the
    cryptographically-anchored 1 kHz HID retina"; pure-function HID-window → WorldState/Event
    encoder that NEVER touches the FROZEN 228-byte PoAC.
  - SCREEN lobe (retina_screen_lobe / screen_retina_fusion): the OUTCOME world model (OCR/screen).
  - CAUSAL COHERENCE (retina_causal_coherence): binds INPUT<->OUTCOME — do the controller inputs
    causally produce coherent screen outcomes?
It already carries a native on-chain provenance stack: da_upload, da_witness, pda_attestation,
events_root, state_commitment, w3bstream, zk_artifacts, depin_policy. Status today:
retina_perception_enabled=False (advisory/default-OFF).

THE LOAD-BEARING INSIGHT — IT ASKS A DIFFERENT, BETTER-SUITED QUESTION THAN L4. The whole session
dead-ended on L4 IDENTITY enrollment (corpus mismatch, zero baseline, the tighten-only +
separation-defensibility guards). That answers "is this the enrolled fingerprint?" Trio-Retina's
causal coherence answers "is there a LIVE, coherent perception-action loop?" A bot / relay / replay
produces INCOHERENT input<->outcome binding; a live human does not. That is a PRESENCE/liveness proof
that needs NO biometric enrollment. And M1 was always a PRESENCE claim (recency-bound human replay) —
so Trio-Retina is the correct primitive for it, where L4 was a category mismatch. This directly
resolves the miswiring named in [[s-l4-baseline-injection-boundary]]: "M1 is a presence claim but its
CERTIFY gate runs through the identity machinery." Trio-Retina IS the presence gate.

WHY IT'S GENUINELY EXCLUSIVE (and convergent with this session):
  - The fusion (input-perception + outcome-perception + causal binding) with native on-chain
    provenance is unique — no kernel anti-cheat does this; it is the "controller as cryptographic
    agency-holder" thesis made literal (the controller's perception, cryptographically attested).
  - It consumes EXACTLY what this session fixed: the controller lobe IS the 1 kHz HID retina. The
    BT-114 Hz era starved it; the USB ~1.6 kHz EXCLUSIVE_USB capture finally feeds it. So the cable
    fix and this layer are the same arc.
  - It sidesteps the dual-host capture wall on the INPUT side (it reads the controller stream the
    bridge already owns) and reframes "presence" away from the AIT identity-separation regime
    (ratio 0.060 for gameplay) toward causal coherence, which gameplay supports natively.

TWO NAMED PREREQUISITES (do NOT promote without these — the honesty rails):
  RETINA-EXCL-1 — SCREEN-LOBE OPTICAL/PRIVACY DECISION. OUTCOME perception means observing the
  screen, but the protocol deliberately pins frame_grabbing=false / optical_capture=false in the
  W3bstream sandbox (the same privacy discipline that DROPPED the mic array per TRACK1-LESSON-002/003
  and preferred the optical-WITNESS path). Making the screen lobe first-class re-opens that posture
  and MUST be a deliberate, documented privacy decision — not a silent flag flip. Candidate honest
  framings: passive optical-witness only / on-device OCR with no frame retention / outcome-hash
  commitments without raw-frame storage.
  RETINA-EXCL-2 — CAUSAL-COHERENCE DEFENSIBILITY STUDY. Promoting causal coherence from advisory to
  CERTIFYING requires its own separability study — measure that bots / relays / replays actually FAIL
  the coherence test at a defensible rate (the retina analog of the AIT 1.199 separation gate and the
  L9 presence validation in [[s-f2-recency-bound-presence-built]]). It cannot enter the verdict gate
  on assertion; it needs a measured false-accept/false-reject envelope, ideally adversarial.

HONESTY RAILS:
  - Advisory -> primary is a real validation + wiring effort, not a flag. retina_perception_enabled
    flipping True does not make it certifying; the verdict-gate wiring + RETINA-EXCL-2 do.
  - No FROZEN-v1 / 228-byte PoAC change — the controller embedder is explicitly PoAC-non-touching.
  - The screen lobe stays subordinate to the privacy discipline (RETINA-EXCL-1); when in doubt,
    optical-witness over frame-grab.
  - This note is a DIRECTION, not a build authorization. The build is operator-fired and gated on
    the two prerequisites.

NET: Trio-Retina-as-exclusive-presence-layer is the cleaner road to M1 than fighting L4 enrollment —
it is already built, already framed exclusive, already fed by the 1 kHz USB capture just unblocked,
and it asks the presence question M1 actually needs. The two prerequisites (screen-lobe privacy,
coherence defensibility) are the honest gates between "promising direction" and "primary layer."
