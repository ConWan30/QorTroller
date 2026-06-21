# Fusion v2 Calibration — synthetic self-adversarial run

**UNCALIBRATED — provisional read on synthetic + real-derived data.** N=1 falsifies, does not validate. Thresholds proposed here require real labelled co-capture before promotion.

- provenance: synthetic  seed: 0  n_per_class: 10

## Confusion — class_label x fusion_verdict

| class \ verdict | DECOUPLED_REVIEW | INSUFFICIENT | LIVE_COHERENT | REPLAY_OR_RELAY |
|---|---|---|---|---|
| BOT_FULL | 0 | 10 | 0 | 0 |
| HUMAN_CLEAN | 0 | 0 | 10 | 0 |
| HUMAN_INPUT_MACRO | 0 | 0 | 10 | 0 |
| HUMAN_RELAY | 10 | 0 | 0 | 10 |

## Honest read
- HUMAN_CLEAN should concentrate on LIVE_COHERENT.
- HUMAN_RELAY (replay/relay) should concentrate on REPLAY_OR_RELAY.
- HUMAN_INPUT_MACRO (injection) should lift INJECTION_SUSPECT as residual passes threshold.
- BOT_FULL (headless) has no rendered channel — coupling None; coherence INSUFFICIENT/ORPHAN_INPUT.
- Off-diagonal mass is the measured separation gap the real experiment must close.
