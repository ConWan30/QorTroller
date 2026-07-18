# PoEP surprise latency report — 2026-07-16

**Report-only.** `poep_enabled=False`. Band **not frozen**. Band source: `REACTION_BAND_MS=80.0/450.0`.

- rows: **134** · policy `edge_operator_reflex_v1` · player_source: **column**

## Per-player (verify-pass proxy)

| player | n_all | n_verify | mean | median | p5 | p95 | min | max |
|--------|------:|---------:|-----:|-------:|---:|----:|----:|----:|
| P1 | 78 | 57 | 347.0 | 346.426 | 276.982 | 419.834 | 253.7 | 449.6 |
| P2 | 36 | 31 | 329.61 | 324.427 | 274.503 | 380.773 | 271.66 | 387.96 |
| P3 | 20 | 19 | 334.59 | 317.916 | 254.43 | 430.383 | 230.72 | 430.4 |

## Pooled verify-pass

- **N = 107** · mean **339.76** · median **341.166** · p5 **264.837** · p95 **423.331**

## Held-out (train-only draft ceiling)

- train N **73** p95 **427.822** → draft hi **443 ms**
- holdout N **34** (FRR@current band = 0 by construction on verify-pass holdout)

## Verdict

1. Report-only — does **not** authorize `poep_enabled=True` or freeze the band.
2. Prefer captures with `player` stamped (T1) for multi-op tables.
3. Next rig night: multi-day corpus + catch trials + adversarial FAR before any flip.

