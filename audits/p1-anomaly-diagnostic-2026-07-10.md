# P1 Anomaly Diagnostic (F-P0A-V2-1) — `p1-anomaly-diagnostic-v0`

**PRIMARY: MARGINAL_AIM** — first-True in pre-registered order (env/protocol before genuine); 2 test(s) True
secondaries: ['HIGH_RESIDUAL']
**p0a_v2_separated_unchanged: True** · advisory · developer_self · P1 is a labeled human (low coupling != automation)

- focus P1 aim-active n=7 · protocol fields available: ['label', 'duration_bin']

| player | n | med coupling | med aim | med lag | med dec |
|---|---|---|---|---|---|
| ? | 6 | 0.4128 | 31.73 | 41.7 | 0.8295 |
| P1 | 7 | 0.0908 | 14.75 | 216.7 | 0.9918 |
| P2 | 8 | 0.5929 | 51.18 | 33.3 | 0.648 |
| P3 | 12 | 0.3793 | 48.97 | 300.0 | 0.8561 |

| test | pass | detail |
|---|---|---|
| T-H1_MARGINAL_AIM | yes | P1 med_aim 14.8 < peers 50.0 and < 20.400000000000002 |
| T-H2_HIGH_RESIDUAL | yes | P1 med_dec 0.992 (>= 0.95) vs peers 0.838 |
| T-H3_LAG_REGIME | no | |P1 217 - peers 183| vs 100.0ms gap |
| T-H5_PROTOCOL_MIX | no | no discrete protocol field differs (only label/duration_bin available) |
| T-H4_GENUINE_LOW | — | no aim-matched comparator (P1 aim band [11.8,17.7] has 0 peer sessions — P1 aim does not overlap peers; genuine-low UNTESTABLE) |