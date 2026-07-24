# L5 (temporal_rhythm_oracle.py) timing exposure — investigation findings + fix

**Status: FIXED (2026-07-22, same session).** Original scope was read-only
investigation only; operator subsequently authorized scoping and building a
fix once the exposure was confirmed. Grok credits were already exhausted
before this investigation began (last confirmed state: `docs/a2a/
live-l2b-unit-scale-investigation/`), so both the investigation and the fix
proceeded solo — disclosed here, same as throughout the L2B investigation,
rather than presented as adversarially reviewed.

## Question

The L2B investigation flagged, but explicitly did not verify, whether L5
(`controller/temporal_rhythm_oracle.py`) shares the batch-timestamp-collapse
exposure found and fixed in L2B/L2C. This investigation answers that
question directly.

## Finding 1: L5 is structurally MORE exposed than L2B/L2C were, and the
## shipped C-fail-4 fix does nothing for it

L2B/L2C's `push_snapshot()` at least attempt
`getattr(snap, "timestamp_ms", None)` before falling back to
`time.monotonic()`. L5's `push_snapshot()` (`temporal_rhythm_oracle.py:222`)
**never checks for `timestamp_ms` at all** — every single call
unconditionally computes `now_wall = _time.monotonic() * 1000.0`.

This means the C-fail-4 fix already shipped (stamping
`snap.timestamp_ms` from `_poll_frames`' real per-frame collection time,
`dualshock_integration.py`) is a **structural no-op for L5** — it has zero
effect on L5's behavior, because L5 never reads that attribute. If L5 has a
real exposure, it is still fully present in production today, unaffected by
anything shipped in the L2B investigation.

`dualshock_integration.py:2312` confirmed: L5 is fed via the identical
`for snap in frames: self._temporal_oracle.push_snapshot(snap)` pattern as
L2B/L2C — the same ~1-second batch, collected via `_poll_frames()`, processed
in one tight post-collection loop.

## Finding 2: the mechanism is genuinely different from L2B's — interval
## computation across repeated presses, not a single precursor-window check

L2B's bug: a SINGLE press's precursor-window membership check
(`t` in `[now_ms-80, now_ms-5]`) fails when the whole batch's timestamps
collapse. L5's mechanism is different: it computes **inter-press intervals**
(`dt = now_wall - self._<button>_last_press_ts`) between CONSECUTIVE presses
of the *same* button, then derives three statistics over a rolling window of
those intervals — coefficient of variation (CV), Shannon entropy (50ms bins),
and a "quantization score" (fraction of intervals within ±5ms of a 60Hz tick
multiple, 16.6667ms). ≥2 of 3 signals crossing their bot-like threshold fires
`0x2B TEMPORAL_ANOMALY`.

This means the exposure is **conditional**, not universal like L2B's: it only
distorts intervals for presses of the *same button* that happen to land
within the same ~1s processing batch (collapsing their true gap toward ~0) or
straddle a batch boundary (rounding their true gap toward the ~1s batch
cadence instead of their real sub-second value) — not every interval, only
some, depending on real play timing relative to the batch boundary.

## Finding 3: empirically confirmed via a standalone repro (real oracle
## class, no hardware, no bridge)

`scripts/diag_l5_batch_timing_repro.py`: since L5 only appends an interval on
a rising edge (non-press frames are irrelevant to the computation), the repro
directly controls real-time gaps between rising-edge events rather than
simulating full raw-HID frame batches — a legitimate simplification of the
identical mechanism (verified: `push_snapshot` only touches `_cross_intervals`
etc. inside the `if cross_pressed and not self._cross_above:` block).

Two modes, same underlying seeded press schedule each time:
- **Mode B (realtime, ground truth):** `push_snapshot` called at real
  wall-clock instants matching each press's true intended time — no batching.
- **Mode A (bridge-style):** presses grouped into real 1-second batches;
  all rising edges within one batch pushed in a tight loop once that batch's
  real time window elapses — matching `dualshock_integration.py`'s exact
  processing pattern.

Four seeded trials, realistic (non-adversarial) press timing with a mix of
quick double-taps and normally-spaced presses:

| Seed | mash_prob | Realtime (cv / entropy / quant / signals) | Batched (cv / entropy / quant / signals) | `classify()` diverged? |
|---|---|---|---|---|
| 42 | 0.35 | 0.59 / 3.72 / 0.69 / **1** | 0.90 / 1.54 / 1.00 / **1** | No (both 1/3) |
| 7  | 0.55 | 1.00 / 2.65 / 0.63 / **1** | 1.41 / 1.17 / 1.00 / **1** | No (both 1/3) |
| 13 | 0.60 | 0.84 / 3.28 / 0.41 / **0** | 1.20 / 1.38 / 1.00 / **1** | **Yes — quant_score crossed 0.55 only under batching** |
| 21 | 0.75 | 1.16 / 2.54 / 0.64 / **1** | 1.41 / 1.24 / 1.00 / **1** | No (both 1/3) |

**Consistent pattern across all 4 trials, same direction every time:**
entropy drops substantially under batching (in all 4 cases, moving noticeably
closer to the `<1.0` bot threshold — as low as 1.17-1.54 bits vs. 2.54-3.72
realtime), and quantization score rises sharply (reaching a perfect **1.00**
in 3 of 4 trials under batching, vs. 0.41-0.69 realtime). CV moved in the
*opposite* direction than L2B's precursor-window bug did — CV went UP under
batching in every trial, not down, likely because collapsed near-zero
intervals mixed with batch-cadence-scale (~1000ms) intervals create a
bimodal distribution with higher relative spread, not a "too-steady" one.

**Seed 13 is a clean, reproducible confirmation**: identical underlying press
timing, zero anomaly signals in the ground-truth realtime case, one signal
firing (`quant_score` crossing its threshold) *only* when the identical
schedule is processed through the batch-replay pattern instead.

## What this does NOT show

`classify()` itself (which requires ≥2/3 signals) did not flip from "no fire"
to "fire" in any of the 4 trials run. Getting a genuine 0→2-signal (or
1→2-signal) flip would be the fullest possible demonstration and I did not
hit it in this limited sampling — CV's unexpected upward drift under batching
appears to provide some (untested, not fully understood) protection against
a full flip in the specific scenarios tried. This does not mean a full
`classify()` flip is impossible on a longer or differently-shaped real
session — only that it wasn't observed in these 4 runs, and I'm not claiming
more than what was actually seen.

## Separate, independent finding surfaced along the way (NOT part of this
## investigation's scope — flagging honestly, not folding in)

The quantization signal's tolerance band (`deviations < 5.0` against a
`_TICK_MS=16.6667` period) covers **exactly 10 of every 16.6667 ms** —
`10/16.6667 ≈ 60%` of the full cycle. For any continuously-distributed
real-valued timing data (bot or human, batched or not), roughly 60% of
samples would land "close to a tick" by pure chance. This was directly
observed in the **ground-truth realtime** measurements above: `quant_score`
ranged 0.41-0.69 across the 4 trials with zero batching involved, already
close to or exceeding the `_QUANT_THRESHOLD=0.55` cutoff in 2 of 4 trials —
a real signal-design concern independent of anything to do with batching.

Separately, there is a clean structural reason the batching bug hits
`quant_score` particularly hard: **1000ms (the batch processing cadence) is
exactly 60 ticks of 16.6667ms** — so any interval that gets rounded toward
the batch-to-batch cadence (rather than its true sub-second value) is
*deterministically*, not just probabilistically, near-perfectly quantized to
the 60Hz reference. This is a coincidence of `_interval=1.0s` colliding
exactly with a 60-tick multiple, not a general property of all batching
cadences.

Neither of these is scoped or investigated further here — flagged for a
future, separately-scoped decision.

## Fix (same session, operator-authorized after this investigation)

`controller/temporal_rhythm_oracle.py`'s `push_snapshot()` now mirrors
L2B/L2C's own pattern exactly: `getattr(snap, "timestamp_ms", None)`,
falling back to `monotonic()` only when absent. Since the C-fail-4 fix
already stamps that attribute on every live snap
(`dualshock_integration.py::_stamp_frame_collection_times`), L5 now benefits
from the existing wiring with zero changes needed outside this one file —
exactly as anticipated below.

**Regression risk confirmed low before building**: the one production call
site (`dualshock_integration.py:2312`) and the existing test suite's `_Snap`
factory (which never sets `timestamp_ms`) were checked — since the fallback
path is what those tests already exercise, the fix is behavior-identical for
all of them. Confirmed: all 32 pre-existing L5 tests pass unchanged.

**New tests** (`bridge/tests/test_temporal_rhythm_oracle.py`,
`TestL5TimingExposureFix`) pin the mechanism directly rather than
re-deriving the full statistical divergence already demonstrated above:
`timestamp_ms` wins over a mocked, collapsed `monotonic()` when present
(proves the fix); the `monotonic()` fallback is unchanged when
`timestamp_ms` is absent (proves backward compatibility with the existing
test suite's own snap factory, which never sets it).

135 tests green across every L5/L2B/L2C/dualshock_integration file touched
by either investigation; PV-CI 184 unchanged. Live verification was
considered and explicitly declined (operator choice) in favor of the
directly-proven mechanism — L5's live verification would need several
minutes of realistic, batch-boundary-straddling play to be meaningful,
unlike L2B's quick-burst probe.

## Status

**L5 exposure: CONFIRMED and FIXED.** Same fix shape as L2B/L2C, same
C-fail-4 wiring already in place, zero additional bridge-side changes
needed. Not adversarially reviewed (grok credits exhausted) — disclosed, not
hidden. Not live-verified against the real bridge (operator choice,
tests-only confidence accepted for this one).
