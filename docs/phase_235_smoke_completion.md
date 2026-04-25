# Phase 235 Smoke Run — Completion Record

**Date:** 2026-04-25
**Session ID:** `grind_phase235_smoke`
**Target:** 3 GIC chain links
**Result:** ✅ chain_length=3, chain_intact=true

## Final state

```
chain_length         3
chain_intact         True
latest_gic_hash      d65c7b4f4f506bac...
genesis_ts           1777101420.27 (first link)
latest_ts            1777101720.89 (third link, 300s after genesis)
grind_session_id     grind_phase235_smoke
```

300 seconds between first and third stamp = exactly one full
`SessionAdjudicator` (5 min) + `SessionAdjudicatorValidationAgent` (5 min)
poll-cycle pair processing all three queued rulings in a single batch.

## What was verified

1. **GIC formula v1 wires correctly** — three sequential SHA-256 stamps with
   chain_intact=true throughout. The two-step session-1 logic (`genesis_gic`
   then `compute_gic`) executed correctly: `genesis_ts == latest_ts` on stamp
   1, links 2 and 3 chain back through `prev_gic` per the FROZEN formula.
2. **Validator pipeline runs end-to-end**:
   `agent_events(ruling_request)` → `SessionAdjudicator` → `agent_rulings`
   → `SessionAdjudicatorValidationAgent` → `ruling_validation_log` →
   GIC stamp via `update_grind_chain_hash`.
3. **Phase 235-BRIDGE-WEDGE-FIX holds** — bridge ran continuously through
   the entire smoke run with no event-loop wedge. `_check_continuity`,
   `session_adjudicator_validator` GIC cluster, and the operator endpoints
   all stayed responsive under sustained load.
4. **`PCC_SMOKE_BYPASS` opt-in flag works** — emitted WARNING per stamp,
   off by default, scoped to a single config field that gets flipped via
   env var.

## What was NOT verified

The smoke run validated the **chain-stamping pipeline**, not the
**protocol's discrimination layer**. With `PCC_SMOKE_BYPASS=true`:

- `_pcc_eligible` was forced True regardless of `capture_state` /
  `host_state` — the USB-vs-BT discrimination is the entire reason
  PCC exists, and it was disabled for the smoke
- `_gameplay_ok` was forced True regardless of `gameplay_context` —
  the GAD layer's ACTIVE_GAMEPLAY-vs-MENU_DETECTED gate was disabled
- `consecutive_clean_toward_target` did NOT advance to 3 — that
  counter respects a different gate (`get_validation_summary`) that
  was not bypassed; it stalled at 2

**The cryptographic chain is valid. The protocol's anti-cheat layers
were not exercised.** That distinction is intentional: smoke validates
plumbing, not policy.

## Blockers for the real 100-session grind

Three things must be addressed before flipping the smoke bypass off and
running `grind_phase235_v1`:

1. **Windows USB enumeration drops the DualSense Edge to ~80–118 Hz**
   with high coefficient-of-variation rate flapping (6 Hz ↔ 118 Hz observed
   during gameplay). PCC's CV-based `host_state` classifier flags this as
   `CONTESTED`. Fix path: Device Manager → DualSense Edge → Properties →
   Power Management → uncheck "Allow the computer to turn off this device";
   try a different chassis-direct USB port; try a different USB-C data
   cable. Goal: `poll_rate_hz` ≈ 1000 sustained.

2. **`SessionAdjudicator` has no automatic gameplay-session trigger.** It
   only fires when an `agent_events(ruling_request)` row is inserted.
   Today those come from BridgeAgent's LLM tool or manual
   `POST /agent/adjudicate`. For a 100-session grind, either:
   - A small auto-trigger agent that detects session boundaries from
     gameplay records (e.g. trigger N seconds after the last NOMINAL
     record), OR
   - Manual triggers via `trigger_adjudication.py` between plays
     (acceptable but tedious).

3. **Phase 236 cleanup — ~38 agents have sync-DB-on-event-loop pattern**
   that causes transient contention windows where `/operator/*` endpoints
   take 1–3 s instead of <100 ms. The Phase 235-BRIDGE-WEDGE-FIX commit
   addressed the highest-impact instances (`_check_continuity`, the
   validator's GIC cluster, batcher writes, operator handlers) but
   `DataCuratorAgent` and others still have the pattern. Not blocking the
   grind directly, but causes dashboard stutter during agent poll cycles.

## How to resume

```powershell
# 1. Verify USB enumeration: poll_rate_hz should be ~1000
python check_grind.py

# 2. Switch to real-grind config in bridge/.env:
#    GRIND_SESSION_ID=grind_phase235_v1
#    GRIND_TARGET=100
#    (PCC_SMOKE_BYPASS already removed; default thresholds restored)

# 3. Restart bridge
python -m bridge.vapi_bridge.main

# 4. Confirm gate is OPEN under default thresholds:
python check_grind.py
# expecting: capture_state=NOMINAL, host_state=EXCLUSIVE_USB,
# grind_ready=True under default 950 Hz threshold

# 5. Run the grind — either play 100 distinct sessions and trigger
#    adjudication after each, OR build the auto-trigger agent first.
```

## Test artifacts

- T-WEDGE-1/2/3 still passing after the bypass code was added (validated
  during smoke setup).
- T235A-1..8 (GIC formula) still passing — bypass does not modify the
  cryptographic spine; it only short-circuits the eligibility gate.
- T-SMOKE-1/2 (HTTP cold-start) still passing.

The bypass is opt-in via env var, defaults to false, and emits a WARNING
on every stamp it short-circuits. It is safe to leave in main.
