# VAPI-AutoResearch Program
# Living strategy document — update this to steer improvement cycles

## Mission

Continuously evolve the /vapi orchestration skill into the most reliable,
anticipatory expert system for the VAPI protocol. Every improvement cycle
makes the skill better at: preventing regressions, closing known gaps,
generating novel WHAT_IF hypotheses, and anticipating Phase 109–113 needs
before they are explicitly requested.

## Ground Truth (never modify — read from MEMORY.md)

The eval harness validates every proposed change against:

1. Protocol integrity (20 invariants in skill.md)
2. Tournament readiness advancement (4 conditions)
3. Known gap closure (separation 0.362 → >1.0, W1 threshold, Class K)
4. Phase 109–113 coherence (ioSwarm architecture)
5. WHAT_IF precision (W1 grounded, W2 genuinely novel)

## Current Improvement Priorities (reorder each session as needed)

Priority 1 — WHAT_IF corpus depth
  The current WHAT_IF mode generates W1/W2 on demand but does not
  retain a curated corpus of validated hypotheses. AutoResearch should
  build a growing library of high-quality WHAT_IF pairs that have been
  tested against the eval harness and found to be genuinely predictive.
  Target: 20 curated WHAT_IF pairs covering Phases 109–113.

Priority 2 — Phase 109B–113 instruction precision
  The skill.md covers Phase 99 architecture in detail but Phase 109+
  ioSwarm integration is described at lower precision. Each cycle should
  make one concrete improvement to ioSwarm instruction quality.
  Target: same instruction depth for Phase 109 as Phase 62 ZK invariants.

Priority 3 — Separation ratio resolution pathways
  Terminal calibration scripts exist but the skill does not yet instruct
  Claude Code to autonomously identify which terminal battery to run next
  based on which feature is most likely to advance the ratio.
  Target: skill should suggest specific terminal script + player + analysis
  command in response to "advance separation ratio" without prompting.

Priority 4 — Adversarial class hardening
  Class K (GSR spoofer) is an open gap with no defined detection pathway.
  Each cycle should propose one concrete step toward Class K specification.
  Target: Class K has a defined detection approach by Phase 113.

Priority 5 — Legal defensibility language
  The skill needs stronger language around what constitutes a legally
  defensible BLOCK ruling under epistemic consensus. Phase 111 PoAd
  creates new language requirements.
  Target: skill can generate legally-precise language for each verdict tier.

## Cycle Constraints (immutable)

- Never propose changes that touch the 20 invariants in ways that relax them
- Never propose changes that weaken the separation ratio disclosure requirement
- Never propose token launch before ratio > 1.0
- Proposed changes must be backward-compatible with Phase 62 ZK commitments
- Each cycle produces exactly: one skill.md delta + one WHAT_IF addition
  + one experiment log entry

## Session Cadence

Run as many cycles as the session warrants.
One cycle minimum per major VAPI development session.
Zero cycles if session is purely hardware/calibration work.
The orchestration layer improves alongside the protocol it orchestrates.
