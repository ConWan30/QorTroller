# A2A SYNC-GO r03 — CURSOR BUILD (B1+B2+B3 per grok r02 FORWARD)

**Builder:** Cursor · **Auditor:** Grok · **Charter (a)** · **Date:** 2026-07-18  
**Spend:** 0 · **No flag flips** · **Self-verdict:** NOT claimed (HOLD for grok r03)

## What changed

### B1 — CLI preflight + amplitude
- `scripts/poep_session_identity_attach.py`
  - `--wait-active-s` (default 45; `0` = legacy cold, no wait)
  - `--poll-s` (default 1.0)
  - `--amplitude` (default 60, clamp 1..80 via `clamp_cli_amplitude`)
  - `eval_preflight_ready` / `wait_for_active_gameplay` — live-only; timeout **exit 3**
  - Ready = sealed `pcc_allows_challenge` + `window_n>=3` + `frac>0` (bridge JSON only)
- `l9_presence/poep_session_identity_run.py` — thin `amplitude=` kwarg pass-through to sealed
  `challenge_live` (no candidate/activity forge)

### B2 — Operator card
- `docs/a2a/poep/syncgo-operator-card.md` (new)
- `docs/poep-campaign-runbook.md` — Shell B command + 5-line SYNC-GO pointer

### B3 — Tests
- `l9_presence/tests/test_poep_syncgo_preflight.py` — T1–T6 (fakes, no HID)

### Untouched (by design)
- `challenge_live` / `classify_activity` / `pcc_allows_challenge` fail-closed bodies
- `L6B_ENABLED` / `poep_enabled` / kill-switch / PoAC / FROZEN formulas

## How to test (local)

```powershell
python -m pytest l9_presence/tests/test_poep_syncgo_preflight.py `
  l9_presence/tests/test_poep_session_identity_run.py `
  bridge/tests/test_attest_feeds.py -q
# Builder ran: 29 passed
python scripts/vapi_invariant_gate.py
# Builder ran: PASS — 184 invariants verified
```

Live dogfood (operator only; not claimed done here):
```powershell
# see docs/a2a/poep/syncgo-operator-card.md
python scripts/poep_session_identity_attach.py --live --api-key $env:OPERATOR_API_KEY `
  --fire-timeout 25 --wait-active-s 45 --amplitude 80 --challenges 2
```

## Claims C1..C10 (attackable)

| ID | Claim | Cite |
|----|--------|------|
| **C1** | Live preflight ready requires `live_activity_window_n >= 3` AND `live_trigger_active_fraction > 0` AND sealed PCC; never invents fields from empty health. | `scripts/poep_session_identity_attach.py:107-142` (`eval_preflight_ready`) |
| **C2** | PCC ready set equals sealed `pcc_allows_challenge` (`NOMINAL` + `EXCLUSIVE_USB\|UNKNOWN`); DEGRADED is not ready. | CLI `:123` + `l9_presence/poep_gameplay_live.py:116-121` |
| **C3** | `--wait-active-s` default 45; `wait_s<=0` skips wait (legacy cold). Live timeout prints `PREFLIGHT TIMEOUT` and returns exit **3** without calling `run_session_identity_attach`. | CLI `:49`, `:152-196`, `:255-258`, `:287-294` |
| **C4** | Preflight is live-only; dry path never enters `wait_for_active_gameplay`. | CLI `:275-310` (wait only under `if live:`) |
| **C5** | `--amplitude` default 60; CLI clamps to `[1,80]`; `0`/`negative` → 60; `255` → 80. | CLI `:145-149`, `:264-266` |
| **C6** | Amplitude is threaded CLI → `run_session_identity_attach(..., amplitude=)` → sealed `challenge_live(..., amplitude=)`. | `poep_session_identity_run.py:65`, `:94`; CLI `:334` |
| **C7** | Runner still never assigns `presence_session_candidate_ok` / `effective_live` / `live_hardware` (purity rail). | `poep_session_identity_run.py` (no assignment; existing purity test still green) |
| **C8** | Operator card + runbook pointer ship copy-pasteable `--wait-active-s 45 --amplitude 80` command. | `docs/a2a/poep/syncgo-operator-card.md`; `docs/poep-campaign-runbook.md` Shell B |
| **C9** | T1–T6 tests green (cold / MENU / ready / timeout / amp clamp / dry IDENTITY_ONLY + sealed `refused_activity`). | `l9_presence/tests/test_poep_syncgo_preflight.py` |
| **C10** | PV-CI still **184**; no `L6B_ENABLED` / `poep_enabled` edits in this diff; sealed `refused_activity` still fires when no ACTIVE sample. | `vapi_invariant_gate.py` PASS 184; T6 |

**Known non-claims (ceiling):**
- No silicon attach artifact yet — SYNCHRONIZED / `n_go_issued>=2` on rig is **next operator fire**, not this build.
- Option (c) mapping left untouched (per r02: no code unless test fails).
- Option (d) hold_ms deferred.

## Auditor packet (paste to Grok for r03 VERIFY)

```
You are the AUDITOR in an A2A verification loop (charter ruling a). Cursor (builder)
produced SYNC-GO B1+B2+B3 against docs/a2a/poep/round-syncgo-02-grok-brainstorm.txt.
Your job is to break the claims, not to be agreeable and not to rewrite the work.

Read:
  docs/a2a/poep/round-syncgo-01-cursor-open.md
  docs/a2a/poep/round-syncgo-02-grok-brainstorm.txt
  docs/a2a/poep/round-syncgo-03-cursor-build.md
  scripts/poep_session_identity_attach.py
  l9_presence/poep_session_identity_run.py  (amplitude kwarg only)
  docs/a2a/poep/syncgo-operator-card.md
  l9_presence/tests/test_poep_syncgo_preflight.py

r03 bars (SHIP only if all hold) from grok r02 §C:
1. Diff confined to attach script (+ thin runner kwargs) + docs + tests; sealed
   challenge_live / classify_activity fail-closed unchanged.
2. Preflight wait is live-only; dry path still IDENTITY_ONLY.
3. Ready uses same fields as production fetcher + PCC == pcc_allows_challenge.
4. Timeout honest — exit 3; no GO without ACTIVE; n_go=0 not silent.
5. --amplitude default 60, max 80, wired into GO fire path.
6. Tests T1-T6 green; PV-CI 184; zero spend; no L6B/poep_enabled edits.
7. Operator card present; command copy-pasteable.
8. Next-rig readiness: preflight either issues under play or timeout explains why.

Rules:
- Attack each claim C1..C10 individually. State what you checked and how.
- Return numbered findings F1..Fn, each tagged BLOCK, WARN, or INFO.
- Look hardest for: free-fire seams, invented frac, PCC loosening, dry-path
  behavior change, amplitude bypass of clamp, silent timeout attach.
- End with exactly one verdict: HOLD (any BLOCK/WARN stands) or PASS.
- Do not propose full fixes; describing WHY a finding blocks is enough.
- Write artifact: docs/a2a/poep/round-syncgo-03-grok-verify.txt

Builder self-verdict: NONE (do not rubber-stamp).
```

## Sequencing
```
r03 grok VERIFY (HOLD/PASS)
  → fix if HOLD
  → operator commit on PASS
  → rig: mid-drive attach per syncgo-operator-card.md
```
