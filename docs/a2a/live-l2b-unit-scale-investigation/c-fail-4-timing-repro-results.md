# C-fail-4 root cause CONFIRMED — empirical repro, no grok audit available

**Context:** round-05 (`round-05-claude-open.md`) was posted and handed off to
grok for adversarial audit of the C-fail-3/C-fail-4 hypothesis. **Grok ran out
of usage credits before responding — no audit was obtained for this round.**
Per operator instruction, proceeding solo, leaning harder on empirical
verification in place of adversarial code review, and being explicit about
that gap rather than presenting this as equivalently vetted.

## Method

`scripts/diag_l2b_batch_timing_repro.py` (new, standalone, no hardware, no
bridge, no production file touched) directly tests round-05's C-fail-4
hypothesis using the real, unmodified `ImuPressCorrelationOracle` class from
`controller/l2b_imu_press_correlation.py`.

Builds ONE real batch of 125 synthetic snaps (matching `InputSnapshot`'s real
shape — no `timestamp_ms` attribute, exactly as verified this session), each
separated by a genuine `time.sleep(8ms)` to match `_poll_frames`' true ~120Hz
collection cadence (~1.00s real wall-clock for the full batch). 16
precursor+press cycles are deliberately embedded: a gyro spike (well above the
default adaptive threshold) exactly 32ms before each Cross rising edge —
squarely inside the oracle's 5-80ms precursor window, i.e. a textbook
physically-realistic human press.

The identical signal pattern (same press/spike frame indices) is then fed
through `push_snapshot()` two ways:

- **Mode A (bridge-style):** `for snap in frames: oracle.push_snapshot(snap)`
  — a tight loop over the already-collected batch, no delay — the exact
  pattern `dualshock_integration.py` uses at lines 2286-2287.
- **Mode B (realtime-style):** `push_snapshot()` called as each frame is
  produced, with the same real 8ms delay between calls — the pattern
  `scripts/diag_l2b_live_probe.py` (Step B / C-fail-2) uses.

## Result

```json
{
  "mode_a_bridge_style":   {"history_span_ms": 1.08,    "coupled_fraction": 0.0, "anomaly": true},
  "mode_b_realtime_style": {"history_span_ms": 1079.05, "coupled_fraction": 1.0, "anomaly": false}
}
```

**Mode A's recorded IMU-history timestamps collapse to a 1.08ms span** despite
representing a real ~1000ms collection window — exactly the predicted
mechanism: `push_snapshot`'s `time.monotonic()` fallback stamps every entry
with the wall-clock time the *processing loop* runs, not the time each frame
was *collected*, and a 125-iteration pure-Python loop with no I/O completes in
about a millisecond. The genuinely-embedded 32ms-earlier precursor spikes are
mathematically un-findable once their recorded timestamps and their
corresponding press timestamps both land within that same ~1ms cluster — the
`window_start <= t <= window_end` check (`[now_ms-80, now_ms-5]`) fails for
every entry, regardless of what the underlying signal actually looked like.
**`coupled_fraction=0.0000`, `anomaly=True`** — the exact numbers observed
live in Step C's bridge run.

**Mode B's history correctly spans 1079.05ms** (matching the true ~1000ms
collection window plus normal call overhead), and the identical precursor
pattern is detected perfectly: **`coupled_fraction=1.0000`, `anomaly=False`**
— matching Step A's and C-fail-2's clean recovery.

## What this settles

**C-fail-4 is confirmed as the root cause**, not merely hypothesized. This is
a pure timing/batching mechanism, fully independent of:
- the physical controller (no hardware involved in this repro),
- the bridge process (not started),
- the unit-scale threshold value (this repro used the unmodified default
  `_IMU_SPIKE_THRESH=30.0`, since the injected signal magnitudes were
  raw-LSB-scaled to match — the timing bug and the unit-scale bug are
  independent defects that happened to produce the identical symptom).

The single variable that flips a textbook-clean human press pattern from
100% detected to 0% detected is *whether `push_snapshot` is called in the
bridge's post-hoc batch-replay pattern or in a real-time call-as-collected
pattern*. Nothing else changed between Mode A and Mode B.

## Honest limits of this result

- **No adversarial audit.** Round-05 was scoped for grok to attack this exact
  hypothesis before treating it as settled; grok's credits ran out before any
  response landed. This repro substitutes empirical verification for that
  audit, but a second reviewer (human or model) has not checked this
  reasoning or this script for a flaw I can't see from the inside.
- **C-fail-3 remains unaudited too** — round-05's claim that button/Cross
  detection is "very likely not the bug" was reasoning from Step C's observed
  data (defined-not-None `coupled_fraction`), not independently re-verified
  this round. Still stands on its own merits, just not adversarially checked.
- **The open question about L5/L2C sharing this exposure remains
  unaddressed** — explicitly out of scope for this repro, which targeted only
  the specific mechanism round-05 hypothesized for L2B.
- **This confirms the mechanism, not yet a specific fix.** Round-05 Ask 4
  sketched a plausible fix shape (wire `self._frame_collect_t_mono`, already
  computed correctly by `_poll_frames`, into each snap's timing before the
  oracle-feeding loops) but that was explicitly flagged "do not build yet" and
  remains unbuilt — this is a diagnostic confirmation, not a production
  change, and no production file has been touched.

## Status

C-fail-3: reasoned-closed (not the bug), not independently audited.
C-fail-4: **empirically confirmed root cause**, not independently audited.
Production fix: not scoped, not built, not authorized. Next decision belongs
to the operator — whether to scope a fix now (informed by this confirmed
mechanism) or hold pending grok's credits restoring for a proper audit pass.
