# L2C velocity-blowup hypothesis — investigation findings: REFUTED

**Scope:** read-only investigation, per operator instruction. No fix needed
or built — the hypothesis being tested was refuted, not confirmed. No
production code touched. Grok credits remain exhausted; proceeds solo,
disclosed as such rather than presented as adversarially reviewed.

## Question

Round-05 (`docs/a2a/live-l2b-unit-scale-investigation/round-05-claude-open.md`)
flagged, but explicitly did not verify, a hypothesis about L2C
(`controller/l2c_stick_imu_correlation.py`): its `push_snapshot()` has the
same `getattr(snap, "timestamp_ms", None)` → `monotonic()` fallback pattern
L2B had before its fix, and its velocity computation
(`dt_s = max(dt_ms/1000, 1e-4); vx = Δrx/32768/dt_s`) divides by a time
delta — if that delta collapses toward the `1e-4` floor under
batch-timestamp-clustering, `vx` could be driven toward extreme values. This
would be a **different failure signature than L2B's** ("always decoupled")
— potentially velocity blowup corrupting the correlation in either
direction. Never verified until now.

Context: L2C already benefits from the already-shipped C-fail-4 fix
(`dualshock_integration.py::_stamp_frame_collection_times`) automatically,
since it already had the same `getattr`-first pattern L2B needed added. So
this investigation answers both the historical question (was the pre-fix
concern ever real?) and the current one (is there any residual exposure now?).

## Method

`scripts/diag_l2c_velocity_blowup_repro.py`: real, unmodified
`StickImuCorrelationOracle`, no hardware, no bridge. A genuine
causally-coupled signal (stick velocity with `gyro_z` responding at a
15-frame lag, mirroring the oracle's own test suite's synthetic-human
pattern) fed through `push_snapshot()` two ways:

- **Mode A (batch-collapsed, pre-fix reproduction):** tight loop, no
  `timestamp_ms`, real `monotonic()` calls with no artificial delay —
  exactly what `dualshock_integration.py`'s `for snap in frames:` loop
  looked like for L2C before frames carried real timestamps.
- **Mode B (current, fixed state):** identical underlying signal, each snap
  carrying a realistic ~8ms-spaced `timestamp_ms`, matching what the
  already-shipped fix now actually provides in production.

## Result

**The velocity blowup is real** — Mode A's `dt_s` values: min=5μs,
max=17μs, **100% of 119 samples clamped to the exact `1e-4` floor**
(the raw elapsed time between consecutive `push_snapshot` calls in a tight
loop is consistently *below* the floor, not just close to it). Resulting
`vx` magnitudes reached ~9860 in Mode A vs. ~123 in Mode B on the identical
underlying stick data — an ~80x blowup, confirming round-05's premise that
velocity really does spike under batch-collapsed timing.

**But it doesn't corrupt classification — across 4 independent seeded
trials, `max_causal_corr` was numerically identical to 6+ decimal places
between Mode A and Mode B every single time, and `classify()` agreed in
all 4:**

| Seed | Mode A `max_causal_corr` | Mode B `max_causal_corr` | Difference |
|---|---|---|---|
| 99 (default) | 0.2179 | 0.2179 | 0.000000 |
| 1 | -0.3869 | -0.3869 | 0.000000 |
| 55 | 0.2159 | 0.2159 | 0.000000 |
| 777 | 0.9997 | 0.9997 | 0.000000 |

## Why — the mathematical reason, not just the empirical result

Since **every** sample in Mode A hits the *exact same* `1e-4` floor (not a
range of different tiny values), `dt_s` is a **constant** across the whole
batch, not a randomly-varying one. That means `vx = Δrx/32768/dt_s` is
`Δrx/32768` uniformly rescaled by the same constant factor (`1/1e-4 =
10000`) for every sample. Pearson correlation is invariant to a constant
positive rescaling of one of its two input variables — the same property
that made L2C immune to the *original* unit-scale bug (raw-vs-`/1000`-scaled
gyro) earlier in this investigation arc. A uniform blowup changes the
*magnitude* of `vx` dramatically but not its *shape relative to itself*, and
correlation only cares about shape.

This is a fundamentally different situation from L2B's bug: L2B compared an
absolute magnitude (`gyro_mag`) against an absolute threshold constant — any
uniform rescaling of the compared quantity changes whether it clears the
threshold. L2C never compares anything to an absolute constant; both of its
mechanisms (unit-scale invariance and this timing-scale invariance) reduce
to the same underlying reason: **correlation-based statistics are blind to
uniform rescaling, threshold-based statistics are not.**

## Honest limits

- This confirms the *uniform*-clamping case specifically, because that's
  what was actually observed (100% of samples hit the identical floor value
  in a simple, low-overhead script). It does not prove floor-clamping is
  *always* perfectly uniform in the real bridge process — if the real
  `_session_loop`'s per-iteration cost for L2C's own loop were irregular
  enough that some `push_snapshot` calls take longer than others (varying
  which side of the `1e-4` floor they land on), the uniform-rescaling
  argument would weaken. This wasn't tested against the live bridge, only a
  standalone script — a genuine gap, smaller than it might first appear
  since `dualshock_integration.py`'s L2C loop is its own separate,
  simple `for snap in frames:` pass (not interleaved with L4/L5/L2B's
  per-frame work in the same iteration), making irregular per-iteration cost
  less likely, but not something directly measured here.
- Only one causal-signal shape (a single lag value, Gaussian velocity) was
  tested, across 4 random seeds varying only the noise draw — not a
  systematic sweep of every lag/coupling-strength combination the oracle
  supports.
- No adversarial (grok) review of this reasoning or script.

## Status

**Round-05's L2C velocity-blowup hypothesis: REFUTED for the tested
scenario, with a sound mathematical explanation for *why* it generalizes**
(correlation's invariance to uniform rescaling, not a coincidence of the
specific trial). No fix needed — L2C required no code change, unlike L2B
and L5, which both did. This closes the last open question from round-05.
