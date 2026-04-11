# VAPI-AutoResearch Program
# Living strategy document — Phase 193 edition (updated 2026-04-11)

## Mission

Continuously evolve the /vapi orchestration skill into the most reliable,
anticipatory expert system for the VAPI protocol. Every improvement cycle
makes the skill better at: preventing regressions, closing known gaps,
generating novel WHAT_IF hypotheses, and anticipating Phase 193–200 needs
before they are explicitly requested.

## Ground Truth (never modify — read from MEMORY.md)

The eval harness validates every proposed change against:

1. Protocol integrity (20 invariants in skill.md)
2. Tournament readiness advancement (4 conditions, all must pass simultaneously)
3. Known gap closure (separation 0.998 → ≥1.0 gate / ≥1.5 anchored target; BT 0→50; Class K)
4. Phase 193–200 coherence (FleetSignalCoherenceAgent, contradiction fingerprint registry,
   orphan signal detection, coherence-weighted separation analysis, Phase 194+ roadmap)
5. WHAT_IF precision (WIF-028 temporal non-stationarity; WIF-029 biometric TTL CLOSED Phase 178;
   WIF-030 ZK ceremony attack CLOSED Phase 179; WIF-031/032/033 fleet coherence open;
   WIF-034 TSP threat succession CLOSED Phase 191)

## Current Improvement Priorities (reorder each session as needed)

Priority 1 — Fleet coherence ORPHAN detection (Phase 193)
  FleetSignalCoherenceAgent (agent #36) has 5 ORPHAN rules but the skill's ANALYSIS
  mode has no explicit guidance for operators encountering unresolved signals >48h.
  The skill must prescribe: check cmd_coherence_status() for ORPHAN entries in the
  separation_ratio domain specifically — an ORPHAN there means the 0.998→1.0 threshold
  crossing event was detected but not confirmed on-chain via SeparationRatioRegistry.
  Target: ANALYSIS mode updated with ORPHAN-aware triage procedure for Phase 193 era.

Priority 2 — Contradiction fingerprint → ProtocolMaturityScoring feedback (Phase 194)
  Cycle 21 W2: coherence_id occurrence counts identify structurally persistent
  inter-agent contradictions. When the same coherence_id appears ≥3 cycles
  (N_PROMOTE_THRESHOLD), extend to also decrement ProtocolMaturityScoringAgent's
  threat_forecast_accuracy_component proportionally. Direct fleet-coherence → maturity
  feedback loop with no human intervention required.
  Target: skill specifies Phase 194 scope (coherence_fingerprint_log table +
  Tool #148 + ProtocolMaturityScoring wire-in) before implementation begins.

Priority 3 — Separation ratio P2/P3 pair gap (P0 defensibility)
  Current: ratio=0.998, P2vP3 inter-distance=0.401 < P2 intra-player=0.502.
  P1 needs 2 more touchpad_corners sessions to likely cross 1.0. But crossing 1.0
  globally while P2vP3 remains below 1.0 leaves all_pairs_above_1=False, blocking
  the Phase 150 defensibility gate. The skill must flag this pre-crossing:
  ratio > 1.0 is necessary but not sufficient — per-pair gate must also pass.
  Target: skill adds explicit all_pairs_above_1 check to PHASE_ADVANCE P0 criteria.

Priority 4 — BT calibration path (hardware)
  BT transport has 0/50 sessions. The skill must identify exactly which terminal
  calibration script to run (terminal_calibration_runner.py --session-type bt_resting)
  and estimate the minimum N needed per player to unlock BT tournament eligibility.
  Target: skill auto-specifies BT capture command + player + analysis pipeline.

Priority 5 — Fleet coherence INVERSION guidance (expected vs attack)
  INVERSION findings (3 rules, Provenance DAG walk) are MEDIUM severity when ratio < 1.0
  and are EXPECTED (BP-001 decay + LOO centroid recalculation cause inversion at N<30).
  The skill currently lacks explicit guidance distinguishing expected inversions from
  attack-indicative inversions. At ratio=0.998 this matters — operators should NOT
  pause tournament prep based on expected INVERSION findings.
  Target: ANALYSIS mode adds INVERSION classification rubric (expected vs anomalous).

## Cycle Constraints (immutable)

- Never propose changes that touch the 20 invariants in ways that relax them
- Never propose changes that weaken the separation ratio disclosure requirement
- Never propose token launch before separation ratio > 1.0 confirmed (raised to 1.5 as anchored target; 1.0 is gate floor)
- Proposed changes must be backward-compatible with Phase 62 ZK commitments
- Each cycle produces exactly: one skill.md delta + one WHAT_IF addition
  + one experiment log entry
- WIF-029, WIF-030, WIF-034 are CLOSED — do not re-propose
- WIF-031, WIF-032, WIF-033 are OPEN — any cycle touching fleet coherence,
  ProtocolMaturityScoring, or attestation chains must cross-check all three
- fleet_coherence_enabled=True DEFAULT (Phase 193) — skill must reflect this in
  all SECURITY_REVIEW and ANALYSIS mode procedures

## Session Cadence

Run as many cycles as the session warrants.
One cycle minimum per major VAPI development session.
Zero cycles if session is purely hardware/calibration work.
The orchestration layer improves alongside the protocol it orchestrates.

## Phase 193 State Reference (ground truth — do not edit; read from CLAUDE.md)

  Phase: 193 COMPLETE | Bridge: 2142 | SDK: 394 | Hardhat: 482 | Agents: 36 | Tools: 147
  Contracts: 43 ALL LIVE | Separation ratio: 0.998 (N=29, touchpad_corners, 2026-04-11)
  Next implementation: Phase 194 (contradiction fingerprint registry)
  Next autoresearch cycle: #24 (fleet_coherence_orphan)
