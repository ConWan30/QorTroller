# VAPI Dry-Run Graduation Protocol
## Phase 207 — StagedDryRunGraduationGate · 2026-04-12

**Purpose:** Controlled, per-agent transition from `dry_run=True` (simulated enforcement)
to `dry_run=False` (live enforcement). Graduation is sequential, P0-gated, and
automatically reverting on false-positive detection.

**Authoritative endpoint:** `GET /agent/dry-run-graduation-status`

---

## Why Sequential Graduation Matters

All VAPI enforcement agents currently run with `dry_run=True`. In this mode:
- Rulings are logged but have no real-world consequence
- VHP minting proceeds regardless of ruling outcome
- Tournament blocks are simulated, never enforced

Moving ALL agents to `dry_run=False` simultaneously creates an unstable step function:
any miscalibration or unexpected input pattern generates a wave of real blocks.
Sequential graduation allows isolated observation of each agent's live behavior
before the next agent is activated.

---

## Graduation Sequence

Agents graduate in this order — never simultaneously:

| Stage | Agent | Rationale |
|-------|-------|-----------|
| 1 | `ruling_enforcement_agent` | Lowest blast radius — streak escalation only |
| 2 | `session_adjudicator` | LLM adjudication before autonomous block |
| 3 | `tournament_activation_chain` | Final gate — activates only after stages 1+2 stable |

---

## P0 Preconditions (All Must Pass Before Any Activation)

| Condition | Gate | How to Check |
|-----------|------|--------------|
| `staged_graduation_enabled=True` | Config | `STAGED_GRADUATION_ENABLED=true` in bridge/.env |
| `tournament_preflight overall_pass=True` | Separation+TTL+AllPairs | `POST /agent/run-tournament-preflight` |
| `non_convergence_detected=False` | TremorRestingConvergenceOracle | `GET /agent/tremor-convergence-status` |

**Fail-closed:** If any precondition fails, `POST /agent/activate-graduation-stage` returns HTTP 422
with a list of blockers. The gate never silently skips a precondition.

---

## Rollback Criteria

Rollback fires automatically when **n_false_positives ≥ graduation_fp_threshold** within the
graduation window. Default: **2 false positives** out of any **10 consecutive sessions**.

When rollback triggers:
1. `rollback_triggered=1` is set on the graduation stage record
2. The agent should be treated as `dry_run=True` again
3. A bus event `graduation_rollback_triggered` is published
4. A new graduation stage must be inserted after investigation — rollbacks are not auto-healed

**False positive definition:** Any ruling verdict of BLOCK issued on a session that subsequently
passes human review. Tracked via `record_graduation_false_positive(agent_id)` in the store.

---

## Commands

```bash
# Check current graduation state
curl http://localhost:8080/agent/dry-run-graduation-status | python -m json.tool

# Check all P0 preconditions
curl -X POST http://localhost:8080/agent/run-tournament-preflight | python -m json.tool
curl http://localhost:8080/agent/tremor-convergence-status | python -m json.tool

# Activate Stage 1 (ruling_enforcement_agent)
# Requires STAGED_GRADUATION_ENABLED=true and all P0 preconditions met
curl -X POST http://localhost:8080/agent/activate-graduation-stage \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "ruling_enforcement_agent", "notes": "Stage 1 activation — tournament gate met 2026-04-12"}'

# Monitor rollback state
curl http://localhost:8080/agent/dry-run-graduation-status | python -m json.tool
```

---

## Implementation Invariants

- `staged_graduation_enabled=False` default — never enable without P0 gate fully satisfied
- Rollback is irreversible for the active stage — a new stage insert is required to re-graduate
- Per-agent activation records are permanent in `dry_run_graduation_log` — audit trail preserved
- False positive recording (`record_graduation_false_positive`) must be integrated into
  the session adjudication result handler before Stage 2 (`session_adjudicator`) activation
- Never graduate Stage 3 (`tournament_activation_chain`) before Stages 1+2 are stable
  (minimum 10 clean sessions each without rollback)

---

## Store Schema

```sql
CREATE TABLE IF NOT EXISTS dry_run_graduation_log (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id              TEXT    NOT NULL,
    stage_number          INTEGER NOT NULL DEFAULT 1,
    activated_at          REAL    NOT NULL DEFAULT (unixepoch('now')),
    dry_run_disabled_at   REAL,
    rollback_triggered    INTEGER NOT NULL DEFAULT 0,
    rollback_triggered_at REAL,
    rollback_reason       TEXT,
    n_clean_sessions      INTEGER NOT NULL DEFAULT 0,
    n_false_positives     INTEGER NOT NULL DEFAULT 0,
    notes                 TEXT    NOT NULL DEFAULT '',
    created_at            REAL    NOT NULL DEFAULT (unixepoch('now'))
)
```

---

## Commitment Gate (before ANY graduation stage)

All of the following must pass before calling `POST /agent/activate-graduation-stage`:

| Condition | Check |
|-----------|-------|
| `separation_ok` | ratio ≥ 1.0 (per-type, tremor_resting) |
| `all_pairs_p0_ok` | all_pairs_above_1=True |
| `biometric_ttl_ok` | credential_age_days < 90.0 |
| `non_convergence_clear` | non_convergence_detected=False |
| `staged_graduation_enabled` | STAGED_GRADUATION_ENABLED=true |

The first three are checked by `POST /agent/run-tournament-preflight`.
The fourth is checked by `GET /agent/tremor-convergence-status`.
The fifth is a config gate enforced by the endpoint itself.

---

## WHAT_IF Entry

**WIF-039 (candidate):** If Stage 1 rollback fires within the first 3 sessions, it
likely indicates a false-positive rate problem in the L4 Mahalanobis threshold
calibration under live conditions (dim mismatch: calib_dim=12, live_dim=13).
Resolution: run `threshold_calibrator.py` on live session data and re-calibrate
before attempting Stage 1 graduation again.
