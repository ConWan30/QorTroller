# P0-A Presence-Oracle Separation OP

**VERDICT: INCONCLUSIVE** — N met, causality held, but failed ['M3_human_floor', 'M5_gap']

*human-vs-**modeled**-automation · developer_self · advisory · population_certified=False · NOT real-cheat / identity / host-trustless (design §7)*

- schema: `p0a-presence-op-v1`  seed: 0
- N: human_scored=44 (skipped 15 of 59) · auto_scored=132
- median coupling: human=0.1949 · auto=0.0688 · **gap=0.1261** (GAP_MIN=0.15)
- causality: median NC=0.0252 (<= 0.1) · median margin=0.1651 (>= 0.15)

| gate | pass |
|---|---|
| M1_n_pos | yes |
| M2_n_neg | yes |
| M3_human_floor | **NO** |
| M4_auto_ceiling | yes |
| M5_gap | **NO** |
| M6_causality | yes |

- per-mode auto median: static=0.0643 snap=0.0637 track=0.094
- separation_ratio (diagnostic): 2.834
- human p25/p75=(0.0905, 0.4231) · auto p25/p75=(0.0545, 0.0918)