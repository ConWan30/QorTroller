# L4 timing exposure — investigation findings

**Scope:** read-only investigation, per operator instruction. No new fix
built or shipped — the one real defect found here turns out to have already
been silently repaired as an unintended side effect of the already-shipped
C-fail-4 fix (`dualshock_integration.py::_stamp_frame_collection_times`,
commit `71bb6341`), confirmed empirically, not assumed. Grok credits remain
exhausted; proceeds solo, disclosed as such.

## Question

Does L4 (`controller/tinyml_biometric_fusion.py`, `BiometricFeatureExtractor`
+ `BiometricFusionClassifier`) share the batch-timestamp-collapse exposure
investigated for L2B (confirmed+fixed), L2C (refuted), and L5 (confirmed+fixed)?

## Finding 1: L4's timing model is architecturally different from L2B/L2C/L5 —
## no `monotonic()` fallback anywhere in it

Unlike the other three oracles, `BiometricFeatureExtractor` never calls
`time.monotonic()` internally. Its two timing-dependent mechanisms are:

1. **`inter_frame_us`** (feeds `trigger_onset_velocity_L2/R2` and the tremor
   FFT's sampling-rate estimate `fs`): read via `_g(s, "inter_frame_us", ...)`.
2. **`timestamp_ms`** (feeds `press_timing_jitter_variance`, index 11): read
   via `getattr(s, "timestamp_ms", 0)` — note the **default is `0`, not a
   `monotonic()` call**.

These needed separate investigation since neither shares L2B/L2C/L5's exact
mechanism.

## Finding 2: `inter_frame_us` is immune, by construction

Traced to `controller/dualshock_emulator.py::DualSenseReader.poll()`:
`dt_us = int((now - self.last_poll_time) * 1_000_000)`, computed via
`time.time()` **at the top of `poll()` itself** — i.e., at real hardware
collection time, once per actual HID read inside `_poll_frames`'s own
real-time loop (`time.sleep(dt_ms/1000.0)` between iterations). This is
computed at the *right* moment structurally, the same discipline
`_frame_collect_t_mono` uses for the C-fail-4 fix — just built correctly
from the start for this specific field, never exposed to the
processing-time-batching problem. `trigger_onset_velocity_L2/R2` and the
tremor FFT's frequency-axis scaling are unaffected by anything investigated
in this arc.

## Finding 3: `press_timing_jitter_variance` was genuinely broken — but
## differently than L2B/L5, and already silently fixed

Traced `_ts = float(getattr(s, "timestamp_ms", 0))` (`tinyml_biometric_
fusion.py:604`) through to `self._jitter_cross_last_ts = _ts` (unconditional,
every call) and the accumulation guard `if self._jitter_cross_last_ts > 0`.
Before `InputSnapshot` carried a real `timestamp_ms` (i.e., before the
C-fail-4 fix), every live snap's `_ts` would default to exactly `0` — and
since the guard requires the *previous* stored timestamp to be `> 0`, it can
**never** pass when every value is `0`. No interval is ever appended to the
IBI deque, for any button, ever.

`_press_timing_jitter_variance()`'s own documented "insufficient data"
return value is `0.0` — but its own docstring defines **"Bot deterministic
macro: < 0.00005 (essentially zero variance)"** as the bot-like signature.
`0.0` sits squarely inside that range. **"No data yet" and "definitely a
bot" produce the identical value** — a real, independent design flaw, not
merely a consequence of missing timestamps.

### Empirical confirmation (`scripts/diag_l4_jitter_timestamp_repro.py`,
real, unmodified `BiometricFeatureExtractor`, no hardware, no bridge)

Realistic Cross-press pattern (8 presses, deliberately varied gaps 290-410ms,
not periodic) fed two ways:

| | IBI samples accumulated | `press_timing_jitter_variance` |
|---|---|---|
| Without `timestamp_ms` (pre-fix state) | **0** | **0.0** (bot-range) |
| With `timestamp_ms` (current, post-fix state) | **7** | **0.0112** (human range 0.001-0.05) |

Clean, decisive confirmation of both halves: permanently stuck pre-fix,
correctly functional post-fix.

## Finding 4: already fixed — confirmed by code trace, not assumed

`dualshock_integration.py:2200`: `bio_features = self._bio_extractor.
extract(frames)` operates on the **same** `frames` list that
`_stamp_frame_collection_times(frames, ...)` mutates earlier in the same
`_session_loop` iteration (the C-fail-4 fix). Python list iteration shares
object references, so by the time L4's extraction runs, every snap in
`frames` already carries the real `timestamp_ms` the fix stamped on. **This
means L4's `press_timing_jitter_variance` defect was already repaired the
moment the C-fail-4 fix shipped (commit `71bb6341`) — neither of us knew L4
was affected at the time.** No new code change was needed or made here; this
finding documents what already happened, retroactively.

## Historical corpus check

`sessions/human/hw_*.json` report objects carry a real, correctly-
incrementing `timestamp_ms` at the top level (confirmed: `hw_005.json`,
30002 reports, min=0 max=29999, mean delta≈1.0ms — the leading `0,0,0`
values are ordinary clock-resolution artifacts at session start, not a
broken field). This means **offline calibration** (the documented L4
thresholds anomaly=7.009/continuity=5.367) was computed from correct
`press_timing_jitter_variance` values the entire time — mirroring the exact
"offline always fine, only the live bridge path was broken" pattern found
for L2B.

## Separate, independent design question surfaced (NOT fixed here — flagging
## for a future decision)

Even with the timing fix in place, a **freshly-started live session** (before
any player accumulates ≥4 presses of a single button) will *also* briefly
show `press_timing_jitter_variance=0.0` during warmup — a much smaller,
transient window than the permanent pre-fix state, but the same underlying
conflation ("insufficient data" == "bot signature") still exists as a latent
design property of `_press_timing_jitter_variance()`. Whether to change the
"insufficient data" sentinel to something distinguishable (e.g., feed a
neutral prior into the Mahalanobis distance instead of a raw `0.0`, mirroring
how L2C's static-stick guard returns `None` rather than a measurement-shaped
value) is a deliberate design decision, not scoped or built in this
investigation.

## Status

**L4 exposure: one real, historical defect confirmed
(`press_timing_jitter_variance` permanently stuck at a bot-indistinguishable
value before real per-frame timestamps existed) — already silently repaired
by the previously-shipped C-fail-4 fix, confirmed by code trace and
empirical test, not assumed.** `inter_frame_us`-dependent features
(`trigger_onset_velocity_L2/R2`, tremor FFT sampling rate) were never
exposed, by construction. No new code change needed or made. One
independent, separate design question flagged for a future decision, not
acted on here. Not adversarially reviewed (grok credits exhausted).
