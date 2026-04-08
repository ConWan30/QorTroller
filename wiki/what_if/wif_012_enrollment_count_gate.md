# WHAT_IF: WIF-012 — Enrollment Count-Gate Without Quality Gate

[VAPI:Phase166:VAPI_WHAT_IF.md:MEASURED]

## Classification

| Field | Value |
|-------|-------|
| Layer | W1 (Protocol Risk) |
| Status | CLOSED (Phase 157 — dual-condition enforcement) |
| Filed | 2026-04-04 |
| Phase closed | 157 |

## W1 — Failure Mode

`enrollment_complete` bus event fires when `sessions_needed_total == 0` without
requiring `defensible=True` from `separation_defensibility_log`.

An adversary could capture exactly `min_n_per_player` sessions of any type,
satisfying the count-gate and triggering `TournamentActivationChainAgent` without
achieving separation ratio > 0.70. The activation chain is breached without
tournament-viable biometric separation.

**Cryptographic grounding:** `defensible=True` requires SHA-256-committed ratio > 0.70
via `SeparationRatioRegistry.sol`. Count-gate bypass is economically motivated
(VHP mint → tournament entry → prize eligibility).

## Mitigation — CLOSED (Phase 157)

Dual-condition enforcement in `EnrollmentAutoGuidanceAgent._compute_overall_ready()`:

```python
overall_ready = (sessions_needed_total == 0) AND (defensible == True)
```

Both conditions must be True simultaneously. Defensible=True requires:
- All players ≥ min_n_per_player
- ratio ≥ min_separation_ratio (0.70)
- all_pairs_above_1 (Phase 150)

## W2 — Opportunity (Phase 157)

Dual-condition `enrollment_complete` becomes a legally enforceable signal:
"This player has N sessions AND separation ratio > 0.70 with defensive coverage."
Tournament operators can rely on it as a single composable gate.

## Invariants

- `auto_activate_on_breakthrough = False` PERMANENT (Agent #16)
- `overall_ready` requires BOTH count-gate AND defensibility
- Dual-condition gated by Phase 157 FleetConsensusSnapshotAgent

## Related Pages

- [[agent_fleet]]
- [[separation_ratio]]
- [[wif_016_covariance_regime]]
