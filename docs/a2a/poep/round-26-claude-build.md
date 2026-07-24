# Round 26 — corpus tooling BUILD (grok-executed; operator may treat as Claude-slot)

**Status:** BUILT · tests green · `poep_enabled=False`  
**Prior:** round-25-grok-corpus-tooling · envelope `faecc5eb2b091791`  
**Note:** Operator said BEGIN; build landed in this session (grok/build path). Round-27 still available for independent re-verify.

## verdicts

| Item | Tag |
|------|-----|
| T1 player stamp | **BUILD-NOW shipped** |
| T2 audit no-clobber | **BUILD-NOW shipped** |
| T3 latency CLI | **BUILD-NOW shipped** |
| T4 tests T-CT-1..6 | **PASS 6/6** |
| Band freeze / poep flip | **NON-goal — not touched** |

## build-results

### T1 — `player` on `l6b_probe_log`
- Idempotent `ALTER TABLE … ADD COLUMN player TEXT` in `store/_core.py`
- `CalibrationMixin.insert_l6b_probe(..., player=)` 
- `persist_desk_probe` passes `player=` through (live capture already had `player=args.player`)

### T2 — session-stamped audits
- `audit_capture_path()` → `audits/poep_live_capture_{player}_{YYYY-MM-DD}_{HHMMSS}.json` (UTC)
- `session_id` local bookkeeping field on audit JSON (not FROZEN)
- Same player same day → distinct files; first block preserved

### T3 — `scripts/poep_latency_report.py`
- Imports `REACTION_BAND_MS` from `poep_live_verify` (single source of truth)
- Prefer `player` column; legacy `--cut` + 2026-07-16 default cuts if unlabeled
- Held-out 70/30 + draft ceiling rule documented
- `_tmp_poep_latency_report.py` delegates to this CLI

### T4 — tests
```text
bridge/tests/test_poep_corpus_tooling.py
6 passed in ~2.8s
```

## re-run latency report

```powershell
cd C:\Users\Contr\vapi-pebble-prototype
python scripts/poep_latency_report.py --date 2026-07-16
```

## open-questions (operator / next nights)

1. Re-capture with `--player Pn` so DB labels are first-class (legacy night still uses cuts).
2. Catch trials + adversarial FAR (next security loop — not this PR).
3. Second calendar day before any band freeze.

## rails

- `poep_enabled` / `L6B_ENABLED` / `L6_CHALLENGES_ENABLED` **unchanged False**
- No FROZEN / PoAC / chain edit
- Staged-ready for operator commit when ready

---
*Corpus tooling is the first software gate on the FLIP-A path — not the flip itself.*
