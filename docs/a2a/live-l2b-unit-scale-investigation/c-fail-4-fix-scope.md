# C-fail-4 fix — scope (NOT built, NOT authorized to build)

**Status:** scoping only, produced solo (grok credits still exhausted — no
adversarial audit available). This document is more conservative than usual
for that reason: it recommends a HOLD point before implementation, not just
before the live verification step.

## What's being fixed

`dualshock_integration.py`'s `_session_loop` collects a batch of ~125
`InputSnapshot`s over a real ~1-second window via `_poll_frames()`, then feeds
that batch through `ImuPressCorrelationOracle.push_snapshot()` (and
`StickImuCorrelationOracle.push_snapshot()`) in a tight, synchronous
post-collection loop (`for snap in frames: oracle.push_snapshot(snap)`).
Because `InputSnapshot` has no `timestamp_ms` field, both oracles fall back to
`time.monotonic()*1000.0` on every call — and since the whole batch is
processed in under 2ms, every timestamp in that batch collapses to a tiny
cluster instead of spanning the true ~1000ms it was actually collected over.
This deterministically breaks L2B's 5-80ms precursor-window check regardless
of the underlying physical signal (confirmed empirically,
`c-fail-4-timing-repro-results.md`) and independently of the already-fixed
unit-scale threshold bug.

`_poll_frames()` already computes the correct per-frame collection time —
`collect_t_mono.append(_collected_at)` at `dualshock_integration.py:3536`,
comment: "stamped the instant the HID read returns, not later" — and stores
it 1:1-aligned with `frames` as `self._frame_collect_t_mono`. It is currently
consumed only by the L6B pre/post-buffer path (line ~2900). This fix wires
that already-correct data into the two oracles that already know how to use
it.

## Fix mechanism

Immediately after `frames = await asyncio.wait_for(loop.run_in_executor(...),
...)` succeeds in `_session_loop` (`dualshock_integration.py:~1809`), before
any of the L4/L5/L2B/L2C oracle-feeding loops run, stamp each collected snap
with its real collection time:

```python
# sketch, not final code
_ctm = getattr(self, "_frame_collect_t_mono", None)
if _ctm and len(_ctm) == len(frames):
    for _snap, _t_mono in zip(frames, _ctm):
        _snap.timestamp_ms = _t_mono * 1000.0   # monotonic seconds -> ms
```

`InputSnapshot` is a plain `@dataclass` (no `slots=True`, no `frozen=True` —
verified by reading the class definition), so setting an attribute it doesn't
formally declare works without error and is immediately visible to
`getattr(snap, "timestamp_ms", None)` in both oracles.

**Two implementation shapes, pick one:**

| Option | What | Diff footprint | Tradeoff |
|---|---|---|---|
| **A — dynamic attribute (recommended)** | Set `snap.timestamp_ms` directly in `dualshock_integration.py`, no change to `dualshock_emulator.py` | Smallest possible — one file, ~4 lines | "Magic" attribute not visible in the dataclass definition; a future reader of `InputSnapshot` wouldn't discover it exists without reading the integration layer |
| **B — formal dataclass field** | Add `timestamp_ms: float = 0.0` to `InputSnapshot` (append after `sensor_ts_ticks`, so existing positional-construction call sites stay backward-compatible — every field already has a default) | Two files | Self-documenting, matches how `sensor_ts_ticks` (a similarly-purposed field) is already declared; larger surface since `dualshock_emulator.py` is imported broadly |

Recommend **Option A** as the minimal, most isolated change — it fixes the
bug exactly where the bug lives (the integration layer's wiring), without
touching the reader/emulator module that many other things import.

## Scope boundary — what does NOT change

- **`l2b_imu_press_correlation.py`: zero changes.** Its existing
  `getattr(snap, "timestamp_ms", None)` fallback pattern already does the
  right thing the moment the attribute is populated — no oracle-side code
  needs to change for L2B.
- **`l2c_stick_imu_correlation.py`: zero changes**, same reasoning — L2C has
  the identical `getattr`-fallback pattern (verified this session), so it
  gets the same correctness improvement for free, as a side effect of fixing
  the upstream wiring, not as a separately-scoped fix. (Round-05's open
  question about L2C's exposure was framed around a *different* possible
  symptom — velocity blowup via `dt_s` clamping — which was never
  independently verified; this fix likely helps it regardless, since the
  same collapsed-timestamp mechanism would produce meaninglessly-tiny `dt_s`
  values, but that specific claim stays unverified and is not the basis for
  this scope.)
- **`temporal_rhythm_oracle.py` (L5): zero changes, explicitly out of scope.**
  L5 never checks for `timestamp_ms` at all — it unconditionally uses
  `monotonic()`. Populating `snap.timestamp_ms` upstream would not change
  L5's behavior at all (it doesn't read that attribute), so this fix is
  inherently a no-op for L5, not a partial fix. Whether L5 has a real,
  separate problem remains an open question for its own future-scoped
  investigation, per round-05's explicit framing.
- **PoAC wire format / FROZEN commitments: untouched.** Walked through every
  consumer of `InputSnapshot` that touches the 228-byte record or any
  commitment hash: `serialize()` (the 50-byte firmware-mirroring pack)
  enumerates its fields explicitly and does not include `timestamp_ms`;
  `_make_record()` uses its own independent local `timestamp_ms =
  int(time.time()*1000)` variable for the on-chain record, never reading
  `snap.timestamp_ms`; `_build_ewc_session_vec()`'s `_ATTRS` list is an
  explicit enumeration that doesn't include it; `AntiCheatClassifier.
  extract_features(snap, dt_ms)` takes `dt_ms` as a caller-supplied parameter
  and doesn't read any snap timestamp. Adding this attribute is invisible to
  all four of those paths by construction, not by care taken to avoid them.

## Why existing tests never caught this

`bridge/tests/test_l2b_imu_press_correlation.py`'s own snap factories
(`_snap()` and `_load_session_snaps()`) always explicitly set `timestamp_ms`
on every synthetic snap they construct. The test suite has never exercised
the fallback-and-batch-collapse path at all — it always fed the oracle
snaps that already had the attribute the bug's fallback exists to compensate
for. This isn't a gap in test *quality*, it's that the tests (correctly)
model the oracle's documented interface, and the bug is entirely in whether
the *caller* (the bridge's integration layer) satisfies that interface —
which no existing test exercises because none of them go through
`dualshock_integration.py`'s actual `_session_loop`/`_poll_frames` path.

## Test plan for the fix

1. Extract the wiring as a small, named, pure-ish helper (e.g.
   `_stamp_frame_collection_times(frames, collect_t_mono)`) rather than an
   inline anonymous loop, so it's directly unit-testable without mocking the
   whole session loop or a live controller.
2. Unit test the helper directly: given a list of bare snap-like objects (no
   `timestamp_ms`) and a matching `collect_t_mono` list, assert every snap
   gets the correct `timestamp_ms` (converted ms, correct 1:1 alignment);
   assert it's a no-op (doesn't raise) on length mismatch, matching the
   existing fail-open discipline used elsewhere in this file.
3. Port `scripts/diag_l2b_batch_timing_repro.py`'s Mode A/Mode B comparison
   into a committed regression test — feed the SAME injected precursor+press
   pattern through the oracle with the helper applied vs. not applied, and
   pin that the fixed path recovers `coupled_fraction` correctly. This is
   the test that would have caught this class of bug and should prevent a
   silent regression of the fix itself.

## Verification plan (after build, before calling this done)

Per this investigation's own established discipline (empirical verification
at every step, not just code review): after implementing, re-run a Step-C-style
live probe against the actual bridge — real Edge, real presses, default
threshold this time (the unit-scale fix from earlier in this investigation is
already the correct default recommendation separately) — and confirm
`coupled_fraction` now recovers through the **full bridge integration path**,
closing the loop that C-fail-2 opened. Anything short of a live re-confirmation
would mean shipping a fix whose only evidence is a standalone repro script,
not the actual production path it's meant to repair.

## Open questions for the operator

1. **Option A vs B** (dynamic attribute vs. formal dataclass field) — leaning
   A, but this is a style/discoverability judgment call, not a correctness
   one.
2. **No grok audit available.** Recommend holding this scope here — not
   proceeding to implementation — until either grok's credits return for a
   proper adversarial pass, or you explicitly decide the empirical repro
   (Mode A/B, `c-fail-4-timing-repro-results.md`) is sufficient confidence to
   proceed solo. This is a genuinely different risk class than the last four
   diagnostic-only commits: it's the first change in this investigation that
   touches a live production file.
3. **L5's open question** — explicitly not part of this fix. Worth a
   deliberate decision on whether/when to open that as its own investigation,
   separate from authorizing this fix.

## Ceiling

This document only. No code written. No file touched. No FROZEN/PoAC/chain
edit. Not authorized to build without further operator direction.
