# HID Timing Resolution — Forward Note (2026-07-01)

**Unconditional correction to the record**, in the same idiom as the floor-transfer diagnostic
(`docs/composite-splice-far-2026-07-01.md` / `docs/floor-transfer-diagnostic-2026-07-01.md`): several
committed fields carry precision-implying names whose *actual* resolution is ~1.2 s, not milliseconds. This
note states that plainly so the public record isn't read as claiming precision it doesn't have.

## The finding

Surfaced while wiring l2_ads (the second anti-splice channel). Diagnostic evidence: in the l2_ads desktop
smoke, within a *single* ~1.2 s consumption tick the L2 analog spanned `0 → 255 → 0` (a full press **and**
release) with **every threshold crossing stamped at the identical millisecond**.

Root cause: the DualSense HID reports **buffer** over each consumption tick, and the session loop **drains
the buffer in a burst**, stamping every frame with `time.time()` at drain-time
(`dualshock_integration.py:2864`; backdating guard at `:1657–1658` can't recover the spacing because the
device `timestamp_ms` values are near-identical within a burst). Result: a tick's ~118 frames carry real
input in correct FIFO **order**, but share ~one timestamp. **Per-frame timing is only knowable to
consumption-tick resolution (~1.2 s).** The consumption cadence — the same lever that forced loop 1's R2
window widening (`docs/composite-splice-far-2026-07-01.md`) — now also sets HID timing resolution.

## Blast radius — fields whose actual resolution is ~1.2 s

- **Loop 2 (`f6e7061f`) `settle_ts_ms`** — the post-death stick-settle point, computed from `feed_death_stick`
  rx/ry samples that are HID-drain-stamped. A 4000 ms death window spans ~3 ticks, so the settle point is
  **quantized to ~1.2 s steps**, not the sub-window precision the field name implies.
- **Loop 2 `death_anchor_ms`** — added so the confirmation lag would be "recoverable offline." It is a
  consumption-tick (`now_ms`) timestamp, so the derived lag `ts_ms − death_anchor_ms` is **coarse to
  ~1.2 s**, not the fine offset the schema comment suggests.
- **Loop 1 R2 window placements** — `mark_r2_onset(_now_ms)` is per-tick wall-clock, so windows are placed
  at ~1.2 s resolution. **Masked** by the 5000 ms window width (which is why loop 1 still works), but real.

## What is NOT affected

- **The screen / ROI clock is precise** (~25 ms WGC presentation timestamps). Anything timed on the WGC
  side (B1/B2 center-ROI series, geometric coupling frame timing) keeps its resolution.
- **The composite splice-FAR conclusion is safe and, if anything, strengthened.** Coarser *attacker-side*
  input timing makes a replay-splice **easier** to land, not harder — so the honest-negative
  ("authorship-alone is not cert-grade against splice") only holds more firmly.
- **No verdict or cert depends on these fields** — loop 2 is a corpus-only oracle-in-training; the coarse
  timing degrades corpus precision, it does not produce a wrong gate decision.

## Status / routing — DEVICE CLOCK FOUND (2026-07-01)

The device-clock diagnostic **succeeded**. The DualSense USB input report carries a device-side sensor
timestamp — **raw offset 28, uint32 LE, ~3 MHz (0.333 µs/tick), perfectly monotonic (11999/11999 steps),
advancing every report** — stamped by the controller at report generation, so it **survives the
burst-drain**. Proof: three L2 holds in the diagnostic session measured at their *true* durations from this
clock (2824 / 3495 / 909 ms), i.e. per-report timing is recovered at device precision. (L2 itself is at raw
offset 5; the drain-stamped wall-clock collapses within a tick, but off[28] does not.)

**Routing: ingestion-layer fix.** Per-frame timing is recoverable, so the coarse-resolution condition
described above is **fixable at the source** rather than worked around per-channel — l2_ads's 300 ms binding
lives, and loop 2's `settle_ts_ms` / `death_anchor_ms` and loop 1's R2 window placement all regain device
precision once the timestamp is plumbed through. The sensor timestamp lives in the **raw hidapi read path**
(the interface-3 report reader), not the `pydualsense`-parsed main reader that currently supplies frames.

**Destination + migration.** The raw path **becomes the timing-authoritative frame source**, migrated
**consumer-by-consumer with validation gates between** (the house pattern: kill→death, archive-validate→
deploy) — not a big-bang source swap, because the blast radius spans every HID consumer (both loops, the
coupling oracles, PoEP, the cert stream). Increment one: route the device timestamp into **l2_ads only**,
prove the 300 ms binding end-to-end at the range (smallest consumer, session already pending); then promote
loops 1/2 in their own step. Correlating the two read handles by sequence-match (the "attach to pydualsense
frames" option) is **rejected outright** — one dropped report desyncs the pairing silently, and the failure
mode is wrong timestamps that look right, worse than honestly-coarse ones.

**Four design constraints for the plumbing (recorded here so git log surfaces them):**
1. **Cross-check the raw parse against pydualsense during smoke** — the raw path reads L2 at offset 5 while
   pydualsense parses the same physical signal via its own layout; confirm they agree before the raw path
   is authoritative for anything. Disagreement is a parsing finding to catch early.
2. **Monotonic unwrapping from day one** — the uint32 @ ~3 MHz wraps every ~1430 s (~24 min), *shorter than
   a normal session*. Unwrapping must be in the plumbing, with a wrap-boundary-crossing regression test
   (simulable in code, no rig).
3. **The 300 ms binding is cross-clock → the plumbing needs a device→wall anchor, not just raw stamps.** L2
   onset lands on the device clock, the ROI transition on the WGC clock. The drain gives the mapping: each
   burst's last frame was generated ≈ at drain time, so drain wall-time **anchors the device clock once per
   tick** and device deltas fill in within-tick at full precision (drift over ~1.2 s between anchors is
   negligible). Name this anchoring logic in the design, don't discover it when an onset-latency number
   comes out shifted by a tick.
4. **Label the clock source per record** (`ts_source` idiom, as capture already does with
   `ts_source=timespan`) — during migration three clocks are in flight (device for l2_ads, drain for loops
   1/2, WGC for ROI); every field that gains device precision says so on the record.

Until increment one lands, the coarse-resolution statement above holds for all data captured through this
date. **The record now pairs the disclosure with the recovery path** — the loop-2 timing fields are coarser
than their names imply *and* the fix is found and scoped; disclosed-and-being-fixed is a stronger record
than either half alone. This section gets a follow-up when the ingestion fix ships.
