---
type: synthesis
id: s-trio-retina-controller-lobe-first-scope
title: Controller-lobe-first scope for Trio-Retina presence — the certifying coherence verdict is structurally input-to-outcome, so the controller lobe alone hardens the input-presence spine but cannot certify M1
created: 2026-06-26T06:50:00Z
modified: 2026-06-26T06:50:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Operator chose to scope the cycle-21 Trio-Retina elevation as a real, controller-lobe-first plan,
gated on RETINA-EXCL-1/2. This note records the scope AND a load-bearing correction the code forced
on the cycle-21 framing. Builds on [[s-trio-retina-exclusive-presence-layer]] and
[[s-l4-baseline-injection-boundary]].

LOAD-BEARING CORRECTION (the code, not the paraphrase). Cycle 21 implied the controller lobe alone
carries presence. retina_causal_coherence.py::assess_coherence (lines 109-146) is structurally
INPUT->OUTCOME: it matches each input-caused screen OUTCOME to a preceding controller INPUT inside a
causal window. With no screen lobe there are zero outcomes, so the verdict can only be INSUFFICIENT
or ORPHAN_INPUT and can NEVER reach COHERENT. Therefore the CERTIFYING presence verdict (causal
coherence, the actual M1 primitive) cannot come from the controller lobe alone; it needs the OUTCOME
stream = the screen lobe = RETINA-EXCL-1. The cycle-21 line "the controller lobe is what M1 needs,
no privacy decision" was true for the INPUT world model, not for the certifying verdict.

WHAT CONTROLLER-LOBE-FIRST DOES DELIVER (grounded, privacy-clean, no screen):
  - A controller-ONLY liveness signal already exists: controller.trajectory.anomalous /
    controller.tremor.anomalous from a forward-dynamics residual model
    (retina_controller_embedder.py; TRAJECTORY_RESIDUAL_THRESHOLD=0.35, marked UNCALIBRATED). This is
    input-PLAUSIBILITY/liveness (does the stream follow live-human dynamics?), NOT identity
    enrollment, so it sidesteps the L4 wall named in [[s-l4-baseline-injection-boundary]] — but it is
    NOT the same primitive as coherence.
  - A full provenance spine: embedder -> events_root -> state_commitment -> da_upload/da_witness ->
    pda_attestation -> w3bstream (all default-OFF flags, config.py ~1890-1941).
  - An already-built controller-only orchestrator: retina_perception.py::run_controller_perception()
    -- "pure orchestration over retina_controller_embedder," importing neither the screen lobe nor
    coherence; its trajectory anomaly is already FSCA-cross-checked against L4
    (RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY). It is fed exactly by the 1 kHz EXCLUSIVE_USB capture this
    session unblocked.

PHASED PLAN (controller-lobe-first; each phase ends in an operator HOLD):
  PHASE 0 — feed the live spine (privacy-clean, no new gate). Wire the live 1 kHz USB snap buffer the
  bridge already owns into run_controller_perception(); enable provenance flags incrementally
  (events_root -> state_commitment -> w3bstream validation), keeping INV-RETINA-001 (228B PoAC) green.
  Output stays ADVISORY. Deliverable: real state-committed RetinaPerceptionResults on live hardware.
  PHASE 1 — RETINA-EXCL-2a, controller-side defensibility. The trajectory/tremor liveness signal is
  UNCALIBRATED. Measure that macro/bot/replay inputs fail the forward-dynamics residual at a
  defensible rate vs live human; calibrate TRAJECTORY_RESIDUAL_THRESHOLD. The controller-side analog
  of the AIT 1.199 separation gate / L9 presence validation. Only after this may the signal INFORM
  (not own) a verdict.
  PHASE 2 — RETINA-EXCL-1, screen-lobe privacy decision (operator-authored). A documented posture
  before any outcome stream exists: optical-witness only / on-device OCR with no frame retention /
  outcome-hash commitments. Re-opens the frame_grabbing=false discipline (the mic-array DROP
  precedent, TRACK1-LESSON-002/003). Blocks ALL of coherence.
  PHASE 3 — RETINA-EXCL-2b + verdict wiring. Causal-coherence defensibility study
  (relay/replay/spectator FAR/FRR with real co-capture), then wire COHERENT into the presence gate as
  the M1 primitive, replacing the L4-identity miswiring named in [[s-l4-baseline-injection-boundary]].

HONESTY RAILS:
  - No FROZEN-v1 / 228-byte PoAC change (the embedder is PoAC-non-touching; INV-RETINA-001 is the
    regression rail). Default-OFF preserved (INV-RETINA-002).
  - advisory -> primary is validation + verdict-wiring, never a flag flip. retina_perception_enabled
    flipping True does not certify; the defensibility studies + gate wiring do.
  - The screen lobe stays subordinate to RETINA-EXCL-1; when in doubt, optical-witness over
    frame-grab.
  - This is a DIRECTION SCOPED, not a build authorized. Even Phase 0 is real wiring; it is
    operator-fired.

NET: controller-lobe-first is a real, privacy-clean milestone — a hardened, attested, advisory
INPUT-PRESENCE SPINE validated on the 1 kHz USB capture just unblocked. It is NOT the M1 certifying
verdict; M1 certification still gates on the screen lobe (RETINA-EXCL-1) AND both defensibility
studies (RETINA-EXCL-2a controller-side, RETINA-EXCL-2b coherence). The honest sequence puts every
privacy-clean, no-new-claim gain first and defers the privacy + certification decisions to explicit
operator gates.
