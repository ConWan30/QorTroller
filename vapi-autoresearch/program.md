# VAPI-AutoResearch Program
# Living strategy document — Phase 177 edition

## Mission

Continuously evolve the /vapi orchestration skill into the most reliable,
anticipatory expert system for the VAPI protocol. Every improvement cycle
makes the skill better at: preventing regressions, closing known gaps,
generating novel WHAT_IF hypotheses, and anticipating Phase 177–185 needs
before they are explicitly requested.

## Ground Truth (never modify — read from MEMORY.md)

The eval harness validates every proposed change against:

1. Protocol integrity (20 invariants in skill.md)
2. Tournament readiness advancement (4 conditions, all must pass simultaneously)
3. Known gap closure (separation 1.261 → ≥1.5 anchored target; BT 0→50; Class K)
4. Phase 173–177 coherence (PoFC, ZK circuit composition, preflight synthesis)
5. WHAT_IF precision (WIF-028 temporal non-stationarity grounded; WIF-029 biometric TTL; WIF-030 ZK ceremony attack)

## Current Improvement Priorities (reorder each session as needed)

Priority 1 — Temporal biometric drift (WIF-029)
  VHP soulbound token TTL is undefined. An on-chain separation ratio commitment
  from April 2026 may be used to authorize a tournament in October 2026 — but
  the player's touchpad tremor pattern will have measurably drifted. The skill
  must instruct Claude Code to flag any tournament authorization where the
  separation ratio commitment age exceeds 90 days without a re-calibration event.
  Target: skill auto-proposes biometric_credential_ttl=90 for Phase 178.

Priority 2 — ZK ceremony capture attack (WIF-030)
  The Groth16 MPC trusted-setup ceremony for VAPI's ZK circuits has no
  documented multi-party audit log. Single-operator ceremony = single-party ZK.
  The skill must instruct Claude Code to require ≥3 external ceremony participants
  documented in a new ceremony_audit_log table before any ZK proof is treated as
  valid for tournament authorization.
  Target: Phase 179 ceremony_audit_log specified by skill before implementation.

Priority 3 — BT calibration path
  BT transport has 0/50 sessions. The skill must identify exactly which terminal
  calibration script to run (terminal_calibration_runner.py --session-type bt_resting)
  and estimate the minimum N needed per player to unlock BT tournament eligibility.
  Target: skill auto-specifies BT capture command + player + analysis pipeline.

Priority 4 — PoFC Agent #21 fleet coherence
  Agent #21 (FleetConsensusSnapshotAgent) is LIVE (Phase 157). SHA-256(sorted_agent_verdicts
  + separation_ratio + ts_ns) must be verified as a distinct on-chain proof type (PoFC),
  composable with PoAC + PoAd. Verify fleet coherence (26 agents all LIVE) before any
  Phase 177+ synthesis gate work.
  Target: skill verifies 26-agent fleet coherence check before any Phase 177+ work.

Priority 5 — Separation ratio stratified climb via persona-windowed calibration
  Current best: 0.569 (touchpad_corners, N=20, diagonal+LOO). TOURNAMENT BLOCKER.
  Root cause: P1 temporal non-stationarity (WIF-028 one-way ratchet). Target: recover
  ratio > 1.0 via persona-windowed calibration (Phase 173 SeparationRatioRecoveryAgent).
  The skill must prescribe exactly: age-weight analysis → recovery action → re-capture.
  Target: skill generates `analyze_interperson_separation.py --session-age-weight 90
  --session-type touchpad_corners` without prompting.

## Cycle Constraints (immutable)

- Never propose changes that touch the 20 invariants in ways that relax them
- Never propose changes that weaken the separation ratio disclosure requirement
- Never propose token launch before separation ratio > 1.0 confirmed (raised to 1.5 as anchored target; 1.0 is gate floor)
- Proposed changes must be backward-compatible with Phase 62 ZK commitments
- Each cycle produces exactly: one skill.md delta + one WHAT_IF addition
  + one experiment log entry
- WIF-028, WIF-029, and WIF-030 are now OPEN — any cycle touching VHP minting,
  separation ratio, or ZK proofs must cross-check all three

## Session Cadence

Run as many cycles as the session warrants.
One cycle minimum per major VAPI development session.
Zero cycles if session is purely hardware/calibration work.
The orchestration layer improves alongside the protocol it orchestrates.
