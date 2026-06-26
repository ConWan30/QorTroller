---
type: synthesis
id: s-novel-fusion-m1-presence-assessment
title: Does grok's cycle-26 NovelPresenceFusionOrchestrator solve the M1 presence path? It can DISSOLVE the screen-lobe gate by reframing presence as multi-oracle fusion, but RETINA-EXCL-2 defensibility is unsolved and the conjunctive design risks the GCAP human-TAR-collapse trap
created: 2026-06-26T15:40:00Z
modified: 2026-06-26T15:40:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Assesses grok's cycle-26 `bridge/vapi_bridge/novel_presence_fusion.py` (NovelPresenceFusionOrchestrator
/ NQPV) against the M1 presence path, which [[s-trio-retina-controller-lobe-first-scope]] established is
gated on (a) the SCREEN LOBE / RETINA-EXCL-1 (causal coherence is structurally input->outcome, needs
the outcome stream) and (b) RETINA-EXCL-2 defensibility (coherence promoted to certifying only with a
measured FAR/FRR study). R1 built only the advisory INPUT spine. Grounded in the code, not grok's
status report.

WHAT THE CODE ACTUALLY IS (V-checked): `fuse()` is a pure decision-tree over PRE-COMPUTED oracle
outputs — it string-matches `retina_report.verdict` (COUPLED_CLEAN / LIVE_COHERENT / IMPLAUSIBLE /
PLAUSIBLE / INACTIVE), `cco.tier`, `poep_present` (bool), `l4_l5_l6_ok` (bool) -> an NQPVVerdict.
It computes NO new physics/biometric signal; it is a COMBINING SEAM + disagreement classifier.
Default-off, fail-open, pure. Bindings are presence-only (`binding_ok = bool(device_id and
record_hash)`), NOT the time-window cross-oracle binding the status implied. Currently fed only the
screen-retina result + PLACEHOLDERS for CCO/PoEP (per the oracle_panel wiring), so it cannot yet
produce a real fused human verdict. (Minor code bug: line ~123 operator precedence —
`(A and B and C) or D` makes the LIVE_COHERENT branch fire regardless of poep_present.)

(1) CAN IT DISSOLVE THE SCREEN-LOBE GATE (RETINA-EXCL-1)? **Yes, architecturally.** The fusion reaches
CONSISTENT_HUMAN from `poep_present + COUPLED_CLEAN + cco_tier`. COUPLED_CLEAN is the L9/PoCP coupling
verdict (controller stick<->camera/IMU, input-side + external witness) — it does NOT need the screen
lobe. LIVE_COHERENT (causal coherence) does need the screen, but the fusion treats it as ONE input,
not the sole primitive. So M1 presence can be reframed as "fusion of input-side + hardware + crypto
oracles (CCO + L9/PoCP + PoEP + L4/L5/L6)", with screen-coherence ADDITIVE not REQUIRED. That genuinely
relocates the M1 path off the screen-lobe dependency — the real architectural value of grok's seam.

(2) DOES IT SOLVE RETINA-EXCL-2 (DEFENSIBILITY)? **No — and there is a strong prior it WON'T as
designed.** The orchestrator adds the combining layer, not the evidence. Grok's claim "a bot cannot
satisfy the whole chain without failing at least one layer" is an ASSERTION — exactly the thing
RETINA-EXCL-2 says must be MEASURED (real bots/relays/replays/modified-hardware FAR + real-human pass
rate). Worse, the L9_presence arc ALREADY ran multi-oracle presence fusion and banked two cautionary
findings the status ignores: L9/PoCP "VALIDATED but not standalone-tournament-grade; FUSION DID NOT
GENERALIZE", and GCAP = "honest negative: catches more adversaries but human TAR collapses
0.806->0.581". grok's chain is CONJUNCTIVE ("fail at least one layer") = the GCAP trap maximized: with
sub-grade oracles (L4 EER ~29%, L9 non-generalizing) any one oracle's false-negative rejects a real
human, so a strict conjunctive fuse would have a HIGH human false-reject rate. The hard side of M1 was
never catching bots; it is passing real humans at tournament grade — and conjunctive fusion makes that
side WORSE, not better.

NET: grok's NQPV is a clean, useful RESTRUCTURING — the single seam that lets the whole stack
interoperate and that CAN route M1 presence around the screen lobe (RETINA-EXCL-1 dissolved, conditional
on the input-side oracles being wired + defensible). But it does NOT solve M1 certification: RETINA-EXCL-2
moves UP to the fusion level and is not just unsolved but at risk of failing the human-pass-rate side
per the banked L9/GCAP precedent. The load-bearing open question is unchanged in spirit, sharper in
form: a MEASURED fusion-level defensibility study with a CALIBRATED / weighted disagreement model
(NOT binary "fail any layer") that hits a defensible human-TAR AND adversary-FAR simultaneously.

WHAT WOULD ACTUALLY ADVANCE M1 (honest next steps, none built here):
  - Wire the real oracle feeds (CCO/PoEP/L9-PoCP) into the seam (placeholders today) so it can emit a
    real fused verdict at all.
  - Replace the binary conjunctive decision tree with a calibrated/weighted disagreement model whose
    thresholds come from data, not string-matching.
  - The defensibility study (RETINA-EXCL-2 generalized): measure fused FAR (bot/relay/replay/mod-HW) AND
    human TAR on a real corpus; explicitly check for the GCAP human-TAR collapse before any promotion.
  - Tighten the seam's binding to the real time-window cross-oracle check (not presence-only).

HONESTY RAILS: assessment only — no code change. grok's module is default-off / fail-open / research;
no FROZEN-v1 / 228B PoAC / chain touch. The screen lobe's privacy posture (RETINA-EXCL-1) is dissolved
only if M1 leans on the input-side oracles; if LIVE_COHERENT (screen) is ever required, RETINA-EXCL-1
returns. Related: [[s-trio-retina-exclusive-presence-layer]], [[s-l4-baseline-injection-boundary]].
