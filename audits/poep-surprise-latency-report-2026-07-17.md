# PoEP surprise latency report — 2026-07-17

**Report-only.** `poep_enabled=False`. Band **not frozen**. Band source: `REACTION_BAND_MS=80.0/450.0`.

- rows: **32** · policy `edge_operator_reflex_v1` · player_source: **column**

## Per-player (verify-pass proxy)

| player | n_all | n_verify | mean | median | p5 | p95 | min | max |
|--------|------:|---------:|-----:|-------:|---:|----:|----:|----:|
| P1 | 8 | 6 | 353.14 | 348.565 | 294.301 | 424.073 | 283.63 | 442.27 |
| P2 | 8 | 7 | 348.31 | 352.38 | 324.016 | 367.441 | 321.22 | 368.07 |
| P3 | 16 | 13 | 339.44 | 346.4 | 273.367 | 392.182 | 255.28 | 402.22 |

## Pooled verify-pass

- **N = 26** · mean **344.99** · median **349.39** · p5 **284.078** · p95 **398.036**

## Held-out (train-only draft ceiling)

- train N **17** p95 **410.228** → draft hi **426 ms**
- holdout N **9** (FRR@current band = 0 by construction on verify-pass holdout)

## Verdict

1. Report-only — does **not** authorize `poep_enabled=True` or freeze the band.
2. Prefer captures with `player` stamped (T1) for multi-op tables.
3. Next rig night: multi-day corpus + catch trials + adversarial FAR before any flip.

