# (ii) R2-onset Increment-0 — rig result (LIVE 2026-07-18)

**Branch:** `feat/l9-consistency-adversarial-harness` · **Spend:** 0 · no flag flips (`L6B_ENABLED`/
`poep_enabled`/`L6_CHALLENGES_ENABLED` stay False) · kill-switch held · `bridge/.env` untouched.
Increment-0 code (grok SHIP) run from the working tree with process-scoped `POEP_RING_DUMP_ENABLED=1`
in LEAN + campaign under Remote Play on the registered Edge `581a836c…`. Follows the F-RIG27-8b read
(`27406426`) that closed the device-clock avenue and redirected to (ii).

## What we captured
6 nonce-bound fires, each dumping the full pre(50)+post(~430–460) `r2`/`accel`/`device_ts` series to
`audits/poep_ring_dump/` (gitignored). Studied offline with `scripts/poep_ring_coupling_study.py`.

| batch | fires | probe_device_ts | maxdR2_act | maxdR2_post | gated R2 onset |
|---|---|---|---|---|---|
| rapid (4, ~6 s apart) | r2onset n1–n4 | **FROZEN 1381120253** (all 4) | 0 | 255 | 1204 / 6860 / 14724 / 20444 ms |
| diagnostic (spaced) | r2diag | 2061859879 (fresh) | — | — | no tap landed |
| clean tap (spaced) | r2tap | 2258963275 (fresh) | 0 | 255 | **1364 ms** (probe→post gap 972 ms) |

## Findings

### 1. The crux is SOLVED (the load-bearing positive result)
**`maxdR2_actuator = 0` on every fire.** The commanded adaptive-trigger force does NOT move the R2 analog
*position* channel — it applies resistance, not displacement. So the confounder grok flagged in
`round-r2onset-01` (separating the operator's R2 reaction from the challenge's own commanded force) is a
**non-issue**: R2 position reflects only the operator's finger. The operator's R2 tap registers as a clean
**full-range (255)** deviation, entirely in the actuator-blind post window — the reaction signal the accel
channel misses (accel peaks stayed 9–660 LSB, below the 500 threshold).

### 2. The R2-onset channel is VIABLE
On a fresh reference, a real R2 tap produces a bounded gated onset (1364 ms) with `maxdR2_post=255` — a
clean, detectable reaction on the R2 channel, unlike the accel crossing that landed on late whole-hand
motion at ~4 s.

### 3. F-R2ONSET-1 — the device-clock reference is NOT the fire instant (must fix before the detector)
- **Freshness gap:** even spaced, `probe→post_start` is ~972 ms — the probe reference is the last
  *pre-frame*, and the RP frame-processing gap around the fire opens a ~1 s hole. So the 1364 ms onset is
  ~972 ms reference lag + ~400 ms actual reaction; the latency is not yet trustworthy.
- **Rapid-fire staleness:** the `_l6b_pre_buffer` does not refill between close fires (the ~7 s capture
  window leaves no time), freezing `probe_device_ts` — the 20 s "onsets" in the rapid batch are pure
  artifacts of a frozen reference.

### 4. Capture-window reality
The pending's `frames_remaining=350` is a FRAME COUNT; at the RP-throttled session-loop rate (~76 Hz) the
post window is ~7 s of real time (~430–460 frames), not 350 ms.

### 5. Study go/no-go gap
`poep_ring_coupling_study.py` GREENLIT despite the 20 s stale-buffer onsets — its criteria lack a
plausibility bound. Needs a `gated_ms` sanity ceiling + a `probe→post_start` reference-gap column so a
stale/garbage reference fails the go/no-go instead of passing it.

## Next increment (before wiring any detector)
**Fix the reference:** anchor `probe_device_ts` to the FIRST post-frame after the fire (capture-resume),
not the possibly-stale last pre-frame — removes the ~972 ms gap and is immune to rapid-fire pre-buffer
staleness. Then add the plausibility bound + reference-gap column to the study, re-capture spaced felt
taps, and only then decide on wiring the ring onset detector (Increment-1). More taps *before* the
reference fix do not help — the latency can't be trusted until it lands.

## Honest ceiling
Instrument-only Increment-0: no presence claim, no corpus/verdict/flag touch, zero spend. The R2-onset
channel is proven viable and the actuator-contamination crux is solved; the reaction-latency measurement
is blocked on F-R2ONSET-1 (reference-to-fire-instant). Increment-0 code (grok charter-(a) SHIP) is staged,
awaiting operator commit.
