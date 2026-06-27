# Consistency Experiment — SYNTHETIC (provisional) — 2026-06-21

**Provenance:** synthetic, parameterised model of per-class oracle behaviour. This is a SENSITIVITY ANALYSIS over the retina-axis unknowns, NOT real capture. Real values (esp. `retina_fpr_proskill`) require Phase 2.

## Parameters (the load-bearing unknowns are the first two)

| param | value |
|---|---|
| `retina_tpr_cheat` | 0.85 |
| `retina_fpr_proskill` | 0.15 |
| `retina_fpr_clean` | 0.03 |
| `bot_implausible_rate` | 0.9 |
| `relay_presence_rate` | 0.4 |
| `human_presence_pass` | 0.97 |

## Headline metrics

- **Machine-assist catch rate** (HUMAN_INPUT_MACRO → security): **0.8275**
- **False-accusation rate** (genuine humans → any security verdict):
  - HUMAN_CLEAN: **0.06**
  - PRO_SKILL: **0.1625** *(PROVISIONAL — synthetic pro-skill is the weakest proxy; needs real capture)*

## 5×6 confusion matrix (per window)

| class \ verdict | CONSISTENT_HUMAN | CONSISTENT_INACTIVE | INC_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY | INC_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE | INDETERMINATE | UNVERIFIABLE |
|---|---|---|---|---|---|---|
| HUMAN_CLEAN | 376 | 0 | 15 | 9 | 0 | 0 |
| BOT_FULL | 0 | 363 | 0 | 37 | 0 | 0 |
| HUMAN_INPUT_MACRO | 60 | 8 | 331 | 1 | 0 | 0 |
| HUMAN_RELAY | 13 | 0 | 162 | 0 | 225 | 0 |
| PRO_SKILL | 333 | 2 | 53 | 12 | 0 | 0 |

## Contextual lift — security-accusation rate by detector

| class | fusion | retina-alone | presence-alone |
|---|---|---|---|
| HUMAN_CLEAN | 0.06 | 0.0375 | 0.0225 |
| BOT_FULL | 0.0925 | 0.9075 | 1.0 |
| HUMAN_INPUT_MACRO | 0.83 | 0.8475 | 0.0225 |
| HUMAN_RELAY | 0.405 | 0.92 | 0.5625 |
| PRO_SKILL | 0.1625 | 0.1375 | 0.035 |

## Honest reading

- The fusion's **value is contextual disambiguation**: it separates no-human (BOT/relay → `*_WITHOUT_PRESENCE` / INDETERMINATE) from genuine human+anomaly (`*_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY`) — a distinction retina-alone (flags any implausible) and presence-alone (misses any PRESENT cheat) cannot make.
- The fusion does **NOT** rescue the cheat-vs-pro-skill boundary: both are PRESENT × (retina-judged) IMPLAUSIBLE, so the false-accusation rate on PRO_SKILL EQUALS `retina_fpr_proskill` by construction. The whole question reduces to retina's trajectory ROC on elite play — measurable only in Phase 2.
- **Decision rule status:** the disagreement signal separates the *contextual* classes here; whether it separates the cheat from real pro-skill is **[UNVALIDATED]** and gated on real `PRO_SKILL` capture.
