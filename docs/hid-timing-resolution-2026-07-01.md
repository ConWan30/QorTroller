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

## Follow-up 2026-07-02 — increment one landed (`75a9654f`); range session surfaces an RP-specific L2 finding

Increment one shipped: `DeviceClockL2Source` + `push_l2_raw` + `feed_ads` on the device clock, **desktop-
validated** (5 firm L2 holds → 5 clean single events, `held_n` 77–188, split GONE). The device-clock
**timing** mechanism is sound. **But that validation was on the DESKTOP config (controller USB'd, no Remote
Play).** The firing-range session (Remote Play running Warzone) surfaced a distinct, config-specific
problem the rider-1 crosscheck caught immediately:

**During Remote Play, the raw interface-3 L2 (report offset 5) sticks HIGH on release.** All 113 crosscheck
disagreements were one-directional — raw path `L2=255` (held) while pydualsense `L2=0` (released) — i.e. the
raw read lags/goes stale on the release edge under Remote Play (controller-ownership contention). Symptom:
every range ADS event resolved with `held_n=1` (the hold's real duration was lost), so the L2 edge timing
the 300 ms binding depends on is corrupt in this config. The device *timestamp* (offset 28) kept advancing
(~627k pushed, anchored) and the split stayed fixed (0 splits) — it is specifically the L2 *value* on
interface 3 that is Remote-Play-unreliable, not the device clock.

**Consequences:** (a) the desktop split-fix claim for `75a9654f` stands, but l2_ads is NOT yet validated in
the Remote-Play gameplay config it must run in; (b) the 8× kill-check is **inconclusive** — the center-ROI
ADS luminance shift looked detectable (magnitude median ~22 vs background std ~2.3) but the corrupt L2
timing means those magnitudes can't be trusted as ADS-onset-aligned; (c) the calibration is blocked until a
Remote-Play-reliable L2 source is established. **(d) MIGRATION GATE — loops 1/2 do NOT migrate onto the
device clock until this same RP-reliable-source finding is resolved AND validated in the Remote-Play
config.** The consumer-by-consumer migration destination stands, but promoting loop 1 (R2 window placement)
or loop 2 (`settle_ts_ms` / `death_anchor_ms`) onto the raw interface-3 path while its input value is
Remote-Play-unreliable would corrupt THEIR timing too — trading the honestly-coarse drain clock for a
silently-wrong one. The gate on all three (l2_ads calibration, loop-1 migration, loop-2 migration) is the
same: a demonstrated Remote-Play-reliable L2 source. The rider-1 crosscheck (built before it was needed, at
operator insistence) did exactly its job — caught the bad ingestion before it produced a garbage corpus.

**Next (needs one Remote-Play session):** diagnose the raw report *during Remote Play* — is offset 5 wrong
under RP, are reports stale/lagged, or does RP change the report mode? — then establish a
Remote-Play-reliable L2 value source (candidates: a different offset/interface under RP; the device
timestamp from interface 3 paired with a reliable L2 value; or a pydualsense-L2 + device-timestamp anchor).
Preparatory (non-gaming) work can build the RP-config raw-byte + dual-L2 diagnostic so that session is
one-shot.

## RESOLVED — 2026-07-02 Remote-Play session

The one-shot RP session ran. **Offset 5 IS the RP-reliable L2 under Remote Play.** Against pydualsense
ground truth (156 ticks, 90k raw reports): offset 5 reads mean **202.4 held / 0.6 released** (separation
+201.8) — it tracks L2 cleanly and drops to ~0 on release. device-ts @28 advances (0% repeats), 64-byte
reports, no layout change; iface-3 is fully live. `push_l2_raw` already reads `data[5]`, so the production
reader is already on the right byte — **Route 1: RP-reliable source established.**

**Two diagnostic fixes made the clean read possible (F-RP-DIAG-1 / F-RP-DIAG-2):**
- **F-RP-DIAG-1** — the RP dual-L2 diagnostic did per-frame `open(...,"a")` on the ~1 kHz raw thread. That
  hot-path fopen would measure its own jitter and could manufacture false "stream starved" evidence. Rebuilt
  as count-capped **drop-oldest** ring buffers flushed once on a trigger file / at stop, with a
  `capped`/`total_seen` marker so a post-cap event is either present or the record says it can't.
- **F-RP-DIAG-2** — the pyds ground-truth side of the diag was nested under `if _ads_on:` (ads-coupling),
  which is off per the "no l2_ads enabled" rail — so ground truth never captured on the first pass. Moved to
  its own env gate: logging ground truth emits no verdict, so the rail (about the *detector*) doesn't apply.

**Cause of the prior 113/113 stuck-high: UNRESOLVED (honest correction).** The tempting story — that the old
diagnostic's hot-path fopen stalled the reader — was checked against the git timeline and REFUTED: the
per-frame diag (`retina_rp_rawdump`, `d5acb73c` 05:33) was built *for the next session*, AFTER the 113/113
finding; during the 113/113 session (`75a9654f` 04:48) the raw reader thread had **zero** per-frame disk I/O
(`push_l2_raw` is in-memory; `crosscheck_l2` runs on the consumption thread). So the prior stuck-high was NOT
self-inflicted instrumentation. Candidates remain: transient RP contention (didn't recur), or
**consumption-load / GIL contention with ads-coupling ON** (the 113/113 session had it on; tonight it was
off) — the last candidate **recurs in Phase 2**, where l2_ads feeding turns ads-coupling back on.

**MIGRATION GATE — source resolved, intermittency monitored.** The RP-reliable-source finding is resolved
(offset 5), so the *source* gate on l2_ads calibration + loop-1/2 migration is cleared in principle. But one
clean session against a prior 113/113 counterexample is **"works tonight, intermittency unresolved"** — so
the honest posture is: source established, **live tripwire required** through Phase 2/4. The tripwire =
`crosscheck_l2` (which already runs when ads-coupling is on, i.e. through Phase 2/4) extended to detect the
one-directional PERSISTENT stuck pattern (raw≥thr / pyds<thr sustained, away from a transition, vs expected
edge-skew) → a tripped state the Phase-2 calibration runner reads per segment → halt segment + mark records
suspect. Loop-1/2 migration stays gated until the intermittency is explained or shown absent across enough
sessions. Evidence pair archived (gitignored): `retina_kf_archive/rp_l2diag/`
(`rp_2026-07-02_s1_cleanoffset5_rawonly` + `rp_2026-07-02_s2_dual_{raw,pyds}` with ground truth).
