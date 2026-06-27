---
type: synthesis
id: s-posca-input-grounded-screen-authorship
title: PoSCA — Proof of Skilled Causal Authorship — input-grounded screen monitoring that binds device-vaulted controller input to on-screen action; a fusion QorTroller already aligns to (VMDR + L9/PoCP + L4/L5 + PoAC -> NQPV oracle). Emulated controller — CAN, mostly SHOULD-NOT (it IS the cheat vector); legitimate ONLY as a labeled red-team adversary harness, never a trust source.
created: 2026-06-27T04:10:00Z
modified: 2026-06-27T04:10:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 600
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Answers the operator's question in three parts: (A) the enhancement + whether QorTroller aligns to fuse it,
(B/C) the emulated-controller could/should. Honest throughout: this is a SCOPE note, not a build, and it
inherits the same two unmet prerequisites every presence claim in this protocol carries.

THE ENHANCEMENT — PoSCA (Proof of Skilled Causal Authorship). Today the retina/screen lobe watches the screen
ALONE (optical-flow coupling = L9/PoCP COUPLED_CLEAN). The enhancement grounds screen monitoring in the
device-verified INPUT stream: per discrete on-screen game-action (a tackle / juke / pass-release in NCAA CFB
26), prove the action was AUTHORED by input from the vaulted controller. It is a FUSION of three legs the
protocol already has, not a new sensor — which is exactly why it aligns:
  LEG 1 — PROVENANCE (the "vaulted device" anchor): VMDR `0x2e5B5FB1…` birth-cert + Path A silicon-rooted
    identity + the 228B PoAC chain. Establishes the input bytes came from THIS cryptographically-verified
    device, signed per cognition cycle. This is the non-repudiable "cannot be accused of cheating" anchor —
    the device identity, not a heuristic.
  LEG 2 — CAUSAL COUPLING (input -> screen): L9/PoCP. The screen REACTS to the input within the
    human actuation/reaction window (coupling 0.29-0.45 vs ~0.02 shuffle) -> the play is live, not replayed
    or pre-rendered.
  LEG 3 — SKILL STRUCTURE (the input is structured-human): L4/L5 — Mahalanobis fingerprint, tremor, and the
    adaptive-trigger force-curve (the PRIMARY discriminator per Sensor Stack v2.1). Proves the authoring input
    carried biomechanical structure, not a macro/translator-synthesized curve.
  THE NOVEL CLAIM = the CONJUNCTION, bound per game-action: "this skilled play was authored by a verified
  human on a verified device." A PoSCA record is a recomputable domain-tagged commitment over (device_id from
  VMDR, action_event_hash, coupling_score, skill_structure_ok, ts) — same witness-primitive grammar as the
  rest of the protocol. Buildable from scratch, EXCLUSIVELY by QorTroller, because no external/server-side
  anti-cheat has (1) the silicon-vaulted device anchor, (2) the 1 kHz biometric capture surface, (3) the
  per-cycle PoAC chain. Screen-only anti-cheat detects anomalous OUTCOMES; only QorTroller can prove
  AUTHORSHIP from a verified physical source. That is the moat.

(A) DOES QORTROLLER ALIGN ENOUGH FOR THE FUSION? YES, strongly — and it should compose INTO NQPV, not parallel
to it. The three legs already exist as separate primitives; PoSCA is the composition. Critically, the NQPV
calibrated split-output model (`novel_presence_fusion`, cycle-29/33) ALREADY ABSTAINS on exactly this missing
feed — "fusion separates ONLY when PRESENCE oracles (coupled-retina screen witness + device-anchored input)
are LIVE." PoSCA IS that oracle. So the right build is: PoSCA verdict -> SessionArtifact field -> the existing
calibrated model. The protocol was already converging here; this names + builds the convergence point.

(B/C) EMULATED CONTROLLER — could / should? COULD: yes, technically. SHOULD, as a TRUST/INPUT device:
almost-certainly-not — it negates the entire thesis. An emulated/virtual controller is software: no silicon
root (no ATECC608A secure element), no genuine adaptive-trigger force-curve, no real IMU tremor, no real 1 kHz
analog noise floor. It is structurally the Cronus Zen / XIM / reWASD translator class — the EXACT cheat vector
Sensor Stack v2.1 names the adaptive-trigger discriminator to DEFEAT (translators cannot synthesize
biomechanically-structured continuous force curves). V.A.P.I.'s definition is "the physical-input source is
also the cryptographic agency-holder" — an emulated controller has no physical source and no agency, so it
cannot be vaulted in VMDR nor cryptographically proven as a human-physical source. Building one as a trust
anchor is self-defeating. SHOULD, narrowly, as a RED-TEAM ADVERSARY HARNESS: yes, and it is genuinely useful.
The NQPV defensibility study needs assembled adversaries (REPLAY / MACRO_INJECTION / RELAY_AIM_ASSIST /
NEAR_MISS_HUMAN) — currently only MODELED in `nqpv_adversary_synth.py`. A real emulated controller emitting
spoofed HID + screen-coupled streams turns MODELED FAR into MEASURED FAR against PoSCA/NQPV — but it lives
strictly on the ATTACK side of the ROC curve, sandboxed, never registered, never a trust source. (Adjacent
legitimate non-cheat use already precedented: VBDIP-0006's 100 deterministic LABELED synthetic vectors — a CI
fixture, not a controller masquerading as human. Hold the distinction: synthetic input as a labeled
adversary/test artifact = good; synthetic input posing as a trusted human source = the thing the protocol
exists to defeat.)

BUILDABLE SHAPE (from scratch, cheapest-first; advisory/default-off): (1) action-event detector on the retina
lobe (discrete NCAA CFB 26 game-actions from HUD/motion cues) — gated on the screen capture-rate fix
(the live WGC/MPO deep-dive [[s-wgc-fps-deepdive-workflow]]); (2) causal binder per action -> device-verified
input event(s) in the preceding actuation window (reuse L9/PoCP + PoAC provenance); (3) skill-STRUCTURE scorer
(structured-human vs macro, NOT a skill RANK) with the mandatory anti-GCAP rail; (4) PoSCA commitment record;
(5) wire as a NQPV oracle feed via the SessionArtifact co-capture contract (abstains until co-captured +
calibrated).

HONESTY RAILS (load-bearing): the "skill" word is the over-claim trap — PoSCA proves AUTHORSHIP + causal
LIVENESS + human biomechanical STRUCTURE, NOT a graded skill rank. Ranking skill is the banked GCAP
human-TAR-collapse trap and would invert into FALSE low-skill-human accusations — explicitly out of scope.
Certification is GATED on: (a) the screen capture-rate fix (in progress — the MPO/WGC work this session);
(b) live co-capture of input+screen in a NON-blind regime (today's Remote Play dual-connection is
biometrically blind — BT->PS5 active => USB carries no live input [[project_dualconnection_capture_blind_finding]];
needs the 1000 Hz `scripts/capture_session.py` path or native-PC); (c) a MEASURED human-TAR/adversary-FAR study
with the anti-GCAP rail (fused TAR >= best single oracle) setting weights+threshold — same bar as NQPV, no
certify-on-architecture. The 4 non-screen pillars stay at 100% and independent; PoSCA only adds an
input-grounded screen lobe. No FROZEN-v1 / 228B PoAC / chain / IOTX touched by this note. Related:
[[l9-presence-arc]], [[project_l9_retina_fusion_capture_rig]], [[s-novel-fusion-m1-presence-assessment]],
[[s-nqpv-defensibility-study-scope]], [[recursive_verification_first_pattern]].
