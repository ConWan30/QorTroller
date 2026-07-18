# A2A ENVELOPE — F-RIG27-8b raw-tick instrumentation (Claude built → grok verify)

**Charter:** (a) — Claude built, grok independently verifies before the operator commits.
**Branch:** `feat/l9-consistency-adversarial-harness` · **Spend:** 0 · no flag flips · kill-switch held.
**Date:** 2026-07-18 · follows F-RIG27-8 (`c7ba84b7`) + rig-4 (`audits/rig-session-cfb27-4-2026-07-18.md`).

## Why (the rig-4 finding)
Rig-4 fired **9 real-hardware probes** on the registered Edge under Remote Play. Every one resolved
`dev_lat=-1.0` — the F-RIG27-8 device-clock companion never rescued the RP-inflated t_mono latency.
`_rp_device_latency_ms` returns -1.0 for TWO very different causes and the resolve log doesn't print the
raw ticks, so we can't tell them apart:
- **dead-wire**: `sensor_ts_ticks` reads 0 in the RP frame path (crossing/probe ticks ≈ 0), or
- **span-reject**: ticks populate but the reaction span > 500ms (reaction genuinely slow).

That split forks the whole PoEP-under-RP path, so it must be measurable on the next rig fire.

## What changed (3 edits, `bridge/vapi_bridge/dualshock_integration.py` — log-only, non-gating)
1. `_resolve_poep_fire(...)` gains param `crossing_device_ts: float = -1.0` (default-safe).
2. Caller in the session-loop completion block passes
   `crossing_device_ts=getattr(_l6b_result, "crossing_device_ts", -1.0)` (the exact value already fed to
   `_rp_device_latency_ms` two lines above).
3. The `POEP-HID-RING: resolve` INFO line adds `cross_ts=%s probe_ts=%s`, where `probe_ts` reads
   `_p.get("poep_probe_device_ts", 0.0)` (the exact other input to `_rp_device_latency_ms`).

The analyze-fail caller (2nd `_resolve_poep_fire`) doesn't pass the new param → default -1.0 (correct: no
`_l6b_result` there). Nothing else touched.

## Claim ceiling
Diagnostic-only. Does NOT touch `latency_ms`/`device_latency_ms`/verdict/corpus/band; does NOT change any
resolve behavior; does NOT flip `L6B_ENABLED`/`poep_enabled`/`L6_CHALLENGES_ENABLED`. The log-line prefix
`"POEP-HID-RING: resolve nonce="` is preserved (asserted by `test_fire_timeout.py:81`).

## Verify done (Claude)
- syntax + import OK; new param present in signature.
- `test_rp_device_latency.py` 15 + `test_fire_timeout.py` 8 = 23 passed.
- `test_l6b_bridge_integration.py` + `test_cco_l6b_wiring.py` = 35 passed.
- `scripts/vapi_invariant_gate.py` → PASS 184.

## Grok — please independently verify (break-attempt)
1. Confirm the two logged raw values (`cross_ts`, `probe_ts`) are **exactly** the two args passed to
   `_rp_device_latency_ms` at the caller — i.e., the log cannot show ticks that differ from what the helper
   actually consumed (no drift / no recompute).
2. Confirm log-only + non-gating: no path where the added param or log changes `latency_ms`, the resolved
   Future payload, the corpus write, or the sealed band verdict.
3. Confirm the analyze-fail caller and any auto-tick (no `poep_future`) path are unaffected (default -1.0).
4. Confirm the resolve-log prefix assertion still holds and no other test asserts the mid-line format.
5. Verdict: SHIP / HOLD / findings. Tightening an over-claim in this envelope is a valid fix.
