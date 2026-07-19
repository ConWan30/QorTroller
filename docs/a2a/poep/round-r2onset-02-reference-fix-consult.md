# A2A FORWARD-CONSULT — F-R2ONSET-1: the true device-clock reference fix (co-design)

**Charter:** (a) — grok co-designs the fix BEFORE Claude builds; then grok verifies the build.
**Operator ask:** the *true, honest, profound* fix — not a reflexive patch. **Operator = sole committer.**
**Branch:** `feat/l9-consistency-adversarial-harness` · **Spend:** 0 · no flag flips · kill-switch held.
**Date:** 2026-07-18 · follows the R2-onset Increment-0 rig result (`c68da648`,
`audits/r2onset-inc0-rig-result-2026-07-18.md`).

## The problem (F-R2ONSET-1)
The device-clock reaction latency uses `poep_probe_device_ts` = the LAST PRE-FRAME's `device_ts` as t0.
Rig-4d proved that is wrong: even spaced, the pre-frame is ~972 ms before the first post-frame; under rapid
fire the pre-buffer never refills, freezing t0 entirely (20 s artifact "onsets"). The reaction latency
cannot be trusted until t0 = the FIRE INSTANT in device-clock space.

## Grounding (verified in code today)
- **`_probe_ts` IS the fire instant, in monotonic time.** `send_l6b_probe` returns `time.monotonic()`
  captured at the HID write (`l6_trigger_driver.py:104`). The pending stores it as `probe_ts`.
- **Every frame carries BOTH clocks:** `t_mono = time.monotonic()` (bridge receive/process time) AND
  `device_ts` = the DualSense offset-28 silicon counter (~3 MHz sample time), proven live+accurate under RP
  (rig-4c: advances at 3.07 MHz).
- **The t_mono latency `(crossing_t_mono − probe_ts)` is already correctly referenced to the fire** — it is
  just INFLATED because `crossing_t_mono` is bursty *receive*-time under RP (frames delivered in ~1 s bursts).
- **The crossing's `device_ts` is accurate** (silicon sample-time, immune to receive-burst).
- **`_t_fire_ns = time.time_ns()`** (wall clock) is also captured at fire — a DIFFERENT clock from the
  frames' monotonic, so not directly comparable to frame timestamps.

So the entire fix reduces to: **map the fire instant `_probe_ts` (monotonic) → t0 in device-clock ticks**,
so latency = `(crossing_device_ts − t0_device_ts) / 3000 ms`.

## The crux (why this is subtle, not a one-liner)
`device_ts` (sample-time) and `t_mono` (receive-time) DIVERGE under RP's bursty delivery: `device_ts` is a
smooth dense silicon counter; `t_mono` jumps in bursts. So a naive linear `t_mono→device_ts` interpolation
at `_probe_ts` is corrupted by the burst. The true device sample-time of the fire lies SOMEWHERE in the gap
`[pre.device_ts, post.device_ts]`, and the burst interval may be an irreducible precision floor.

## Candidate directions (react/steer/replace — do NOT rubber-stamp)
- **A — first post-frame `device_ts`.** Simple; but it's *after* the fire+gap → under-counts the latency.
- **B — interpolate `_probe_ts` into device space** using the two bracketing frames' `(t_mono, device_ts)`.
  Principled, but relies on `t_mono` (bursty receive-time) for the map — noisy across a burst gap.
- **C — read-at-fire.** Pair a `device_ts` READ with the fire WRITE to capture t0 directly in device space
  (the drain thread already reads offset 28). Cleanest IF a fresh read is available at fire; RP burst may
  return a stale buffered report.
- **D — honest uncertainty.** Whatever t0 we pick, REPORT the reference uncertainty (the `pre→post`
  device_ts gap = the local burst interval) as an explicit ± error bar on the latency. If the burst floor
  exceeds the 80–280 ms band, the honest conclusion may be that the reflex band is UNMEASURABLE under RP —
  and that is a profound, publishable negative, not a failure.

## Questions for grok (co-design)
1. What is the correct, honest t0-in-device-space? Pick/combine A/B/C, or propose the true one.
2. Is the RP burst interval an irreducible latency-precision floor? If so, is the 80–280 ms reflex band
   even measurable under Remote Play — or must the SYNCHRONIZED path be a NON-RP (direct-USB-play) topology?
3. The error-bar (D): how should the study + any future detector REPORT reference uncertainty so we never
   claim precision we don't have?
4. Smallest honest increment: fix t0 + add the ± reference-gap column + a plausibility bound to
   `poep_ring_coupling_study.py`, re-run on the 6 existing local dumps (no rig needed) — then decide.

## Rails
Instrument/study-only. No flag flips (`L6B_ENABLED`/`poep_enabled`/`L6_CHALLENGES_ENABLED` stay False),
no spend, no corpus/verdict touch, no FROZEN/228B/PV-CI edits, sealed `l9_presence` untouched. The 6 rig
dumps are LOCAL (gitignored) and can be re-analyzed offline with no rig.

---

## OUTCOME (grok co-design → Claude build → grok SHIP)

**Design (grok):** t0 = mono-EXTRAPOLATED, gap-CLAMPED device tick from the last pre-frame anchor
(`t0 = anchor.device_ts + (probe_ts_mono − anchor.t_mono)·rate`, clamped to `[anchor, post0]`; the 3 MHz
rate is KNOWN so no invalid mono↔device regression). Report the FULL `[lat_lo(t0=post0), lat_pt(t0=extrap),
lat_hi(t0=anchor)]` interval + `reference_gap_ms` (the burst floor). RP burst is NOT a proof the 80–280 ms
band is unmeasurable under RP — but resolving it needs the live gold standard **read-at-fire (C)**, the next
increment. Offline slice only; no bridge edit.

**Build (Claude):** `scripts/poep_ring_coupling_study.py` reworked (study-only) + 5 tests. Re-ran on the 6
existing local dumps:
- The 3 **rapid-fire 20 s artifacts are now REJECTED** (`plausible=False` via `reference_gap > 1500 ms`) —
  the core F-R2ONSET-1 bug is fixed; the go/no-go can no longer be fooled by a frozen reference.
- 2 spaced fires plausible: `lat_pt` 855 / 1298 ms with WIDE `[lo,pt,hi]` intervals (`ref_gap` 349 / 972 ms).
  `lat_pt` is biased HIGH (the anchor's receive-time ≠ its sample-time under burst); the honest surface is
  the interval, never the point, and never the optimistic `lat_lo`.
- **Verdict: NO-GO** — median plausible onset ≫ 280 ms with wide bounds → honestly EITHER a ~voluntary press
  (physiology/UX) OR residual t0 error, and **offline analysis cannot tell them apart**. Only live
  read-at-fire (C) can pin t0 tightly enough to decide.

**Profound honest conclusion:** the fix does not make the band pass — it makes the study HONEST, kills the
artifacts, and proves that resolving the reflex band under Remote Play requires the live read-at-fire
reference (C) + likely a direct-USB-play topology for a tight gap. `t_mono` cannot resolve it; recovered
device t0 can, but only within the reported uncertainty.

**Verify (grok):** SHIP — t0 math + wrap + clamp correct; `lo≤pt≤hi` honest; 20 s trap stays rejected via
`ref_gap`; study-only, no presence claim, no bridge/corpus/flag touch. Non-blocking residual: `lat_pt`
biased-high is covered by the interval + the "no finer than ref_gap / next=read-at-fire(C)" note.

**Next increment (C — the live gold standard, bridge-side, gated):** pair a `device_ts` read with the fire
write to capture t0 directly in device space; re-capture spaced felt taps; then decide detector vs
voluntary-not-reflex. STAGED — operator commits the two study/test files + this doc.
