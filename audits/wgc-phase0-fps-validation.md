# WGC Phase-0 fps validation — process isolation is NOT the fix

**Date:** 2026-06-26 · **Scope:** `s-retina-wgc-process-isolation-scope` (VSD cycle-40) · **Tool:** `scripts/validate_wgc_standalone_fps.py`

## Test
Measure STANDALONE WGC frame rate (own process, no bridge contention) on monitor 1 while the operator plays
Warzone via Remote Play **fullscreen**, alongside the running bridge. Hypothesis under test: the bridge's
~2fps screen-lobe is in-bridge GIL/event-loop contention.

## Result
```
56 frames / 35s = ~1.6 fps standalone (fmt=uint8(1080,1920,4))   # steady +8 frames / 5s
```
The standalone capture is **also ~1.6 fps** — same as in the bridge.

## Verdict: (b) the capture surface is the limit
The ~2fps is **NOT** in-bridge contention. WGC samples Remote Play's fullscreen video at only ~1.6fps
regardless of process — the Remote Play presentation surface (DRM/overlay/protected) or monitor present-rate
to WGC is the ceiling. **Process isolation (Phase 1) is OFF — it would not raise the rate.** The Phase-0 gate
prevented building the entire wrong fix.

## Re-scope (honest options)
1. **Native-PC aim-game (recommended for the lag pillar).** A game rendering directly on the capture machine
   (controller→PC USB, game on the PC swapchain) is WGC-capturable at full 60fps — no streamed/protected
   surface. That's where the coupled-retina/lag pillar runs at full rate. Remote Play is structurally a
   low-rate witness for the screen-lobe.
2. **DXGI Desktop Duplication** — a different capture API that may handle the protected surface better than
   WGC. Separate engineering effort + new dependency + uncertain it beats the surface protection. Not worth it
   before option 1 is tried.
3. **Accept Remote Play screen-lobe as a low-rate witness.** It DOES produce real `COUPLED_CLEAN` intermittently
   (~25%) — valid presence evidence, just not continuous. The lag estimation runs whenever coupling computes.

## What still stands
The shape-guard fix (cycle-39) is correct and necessary regardless — it's what lets coupling compute at all.
The 4 non-screen pillars (presence/PoEP, hardware, input⊗gameplay, physicality L4·L5·L6) are at 100% and do
not depend on the screen-lobe rate. No code was built for Phase 1; this validation is the deliverable.
