# P0-A Presence-Oracle Separation OP

**VERDICT: SEPARATED** — M1-M6 all hold under pre-registered constants

*human-vs-**modeled**-automation on aim-active sessions · developer_self · advisory · population_certified=False · NOT real-cheat / identity / host-trustless (design §7)*

- schema: `p0a-presence-op-v2`  seed: 0  ·  aim-gate: `max(std(sx-med),std(sy-med)) LSB` >= 10.2 LSB
- N: human_scored=33 (aim_inactive excluded 26, skipped 0 of 59) · auto_scored=99
- median coupling: human=0.3738 · auto=0.0666 · **gap=0.3072** (GAP_MIN=0.15)
- causality: median NC=0.0255 (<= 0.1) · median margin=0.3466 (>= 0.15)

| gate | pass |
|---|---|
| M1_n_pos | yes |
| M2_n_neg | yes |
| M3_human_floor | yes |
| M4_auto_ceiling | yes |
| M5_gap | yes |
| M6_causality | yes |

- per-mode auto median: static=0.0573 snap=0.0825 track=0.0761
- separation_ratio (diagnostic): 5.611
- human p25/p75=(0.0917, 0.4416) · auto p25/p75=(0.0439, 0.0909)

**Per-player (D-P0A-10):**
- players below TAU_HUMAN (F-P0A-V2-1 heterogeneity): ['P1'] — pooled SEPARATED is carried by the rest

| player | n | median coupling | median aim |
|---|---|---|---|
| ? | 6 | 0.4128 | 31.7 |
| P1 ⚠️ | 7 | 0.0908 | 14.8 |
| P2 | 8 | 0.593 | 51.2 |
| P3 | 12 | 0.3793 | 49.0 |