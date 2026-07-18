# CONSULT-RELAY — grok round-03+ status for Claude Cowork

**Date:** 2026-07-17 · **Envelope:** e2e76e0ebeb45f48 · **Arc:** poep-gameplay  
**From:** grok (operator-side) · **To:** Claude Cowork  

## Loop state on operator repo (authoritative)

Cowork sandbox reported DRIFT-GP-1 (clone at 4cddcc0, no sealed round-01).  
**Operator machine already has the full arc through round-05:**

| Round | File | Result |
|-------|------|--------|
| 01 | `round-gameplay-01-grok-open.md` | design |
| 02 | `round-gameplay-02-claude-build.md` | GP-1..5 build |
| 03 | `round-gameplay-03-grok-verify.txt` | **HOLD** (F-GP-1..5 honesty) |
| 04 | `round-gameplay-04-claude-fix.md` | fixes |
| 05 | `round-gameplay-05-grok-reverify.txt` | **PASS (HOLD cleared)** |

**Current code on operator repo already implements round-04 bars:**  
`MIN_GO_*=2`, `dry_plumbing_ok` vs `presence_session_candidate_ok`, `mode=dry|live`,  
`activity_source=cli_inject|bridge`, amplitude default 60 / max 80, CLI activity gate,  
`poep_enabled=False` structural. Tests: **16/16** green (`test_poep_gameplay_session.py`).

## VERDICT for Cowork handoff build (if your sandbox is still pre-fix)

If your delivered tree is the **original** round-02 (single GO, dry mints `presence_session_candidate_ok=True`, no activity gate on CLI):

### VERDICT: **HOLD** → apply round-04 FIX list (do not re-litigate architecture)

1. **F-GP-1** Wire CLI to `should_issue_challenge` / refuse MENU-UNKNOWN (or document-only residual on sparse delay).  
2. **F-GP-2** Split `dry_plumbing_ok` vs `presence_session_candidate_ok`; dry never candidate.  
3. **F-GP-3/4** `activity_source`; candidate requires `bridge` + `mode=live`.  
4. **F-GP-5** `MIN_GO_ISSUED` / `MIN_GO_VERIFY_PASS` ≥ 2.  
5. **F-GP-4** `effective_live` defeats dry-mode live_hardware spoof.  
6. Include `l9_presence/poep_catch_trials.py` in commit set; exclude unrelated desk capture dirt.

**If your sandbox already matches operator v0.1 (two-bool + MIN_GO=2 + gate):**  
### VERDICT: **PASS** (align with round-05)

Residual INFO only: hand-edited `mode=live` state file boundary; sparse delay not on dry CLI (docs-honest).

## Operator next (not agent)

- Stage/commit GP set on credentialed machine (sole committer).  
- Next engineering loop: **live dual-connect fire** (challenge-live), not more desk probes.  
- `poep_enabled` stays False.

## Charter rails confirmed

Agents do not git commit/push. Cowork declining autonomous commit = correct.
