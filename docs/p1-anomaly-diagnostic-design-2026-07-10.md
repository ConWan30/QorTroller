# P1 Anomaly Diagnostic Design (F-P0A-V2-1)

**Status:** DESIGN ONLY (2026-07-10). Loop sequence lane 1 after P0-A v2 SEPARATED.  
**Audience:** Claude (audit → offline harness) · operator (commits).  
**Does not change:** P0-A v2 SEPARATED, TAU_*/GAP_MIN, aim gate, or schema `p0a-presence-op-v2`.  
**Rails:** advisory · developer_self · offline only · zero capture-path · no FROZEN-v1 · PV-CI 182.

**Predecessor:** `docs/p0a-presence-separation-study-design.md` ·  
`audits/p0a-presence-op-v2-2026-07-09.{json,md}` · finding **F-P0A-V2-1**.

---

## 1. THE CLAIM (one sentence)

**This diagnostic classifies why labeled player P1 remains below TAU_HUMAN on aim-active sessions in the 3-player `sessions_l9` corpus (capture/protocol factors vs residual low coupling), and does NOT overturn the pooled v2 SEPARATED OP, establish identity FAR/FRR, or prove P1 is “bot-like.”**

---

## 2. Why this lane is next

P0-A v2 SEPARATED is **pooled** and honest, but:

| Player (aim-active) | n | median coupling | median aim_activity_std | Notes |
|---------------------|---|-----------------|-------------------------|-------|
| P1 | 7 | **0.09** | **14.8** | Below TAU_HUMAN=0.20; `players_below_tau_human` |
| P2 | 8 | 0.59 | 51.2 | Carries SEPARATED |
| P3 | 12 | 0.38 | 49.0 | Carries SEPARATED |
| untagged | 6 | 0.41 | 31.7 | Above TAU |

**F-P0A-V2-1:** SEPARATED is P2/P3-carried; P1 is a systematic low-coupling outlier even after the aim gate.

Without classification, the OP can be over-read as “works for every labeled player.” This diagnostic **pins the limit** and informs whether an optional v3 uniform claim is even plausible.

---

## 3. Pre-registered hypotheses (closed set)

Evaluate **in order**. First matching primary label wins; secondary tags may stack as notes.

| ID | Label | Meaning |
|----|-------|---------|
| **H1** | `MARGINAL_AIM` | P1 clears the aim gate but sits near the floor; low coupling is mostly **insufficient aim energy**, not a coupling-engine failure |
| **H2** | `HIGH_RESIDUAL` | P1 stick motion is material, but **decoupled_energy** is systematically high (camera not explained by stick — capture/optical/scene) |
| **H3** | `LAG_REGIME` | P1’s best-lag distribution sits in a different band than P2/P3 (stream delay / backend / search edge) |
| **H4** | `GENUINE_LOW_COUPLING` | After matching P1 to other players on aim intensity, coupling remains low — residual **player- or style-level** difference (not proven identity) |
| **H5** | `PROTOCOL_MIX` | P1 sessions differ on recordable protocol fields (backend, region, duration, label) vs peers |
| **H0** | `INCONCLUSIVE` | Insufficient n or conflicting signals |

**Non-labels (forbidden):** `BOT`, `CHEAT`, `FAIL_PRESENCE` — P1 is a labeled human in the developer corpus; low coupling ≠ automation class.

---

## 4. Metrics (all offline from existing `.npz`)

### 4.1 Reuse (must match P0-A harness)

| Metric | Definition | Source |
|--------|------------|--------|
| `coupling_score` | max \|causal Pearson r\| | `analyze_session_data` |
| `negative_control`, `neg_control_margin` | shuffle control | same |
| `decoupled_energy` | residual fraction | same |
| `lag_ms` | best causal lag | same |
| `aim_activity_std` | `max(std(sx−med), std(sy−med))` | same as v2 aim gate |
| `aim_active` | `coupling defined AND aim_activity_std ≥ AIM_ACTIVITY_MIN` (10.2) | v2 constants |

### 4.2 Diagnostic-only (new, pure functions)

| Metric | Definition | Rationale |
|--------|------------|-----------|
| `stick_range` | `max(max(sx)−min(sx), max(sy)−min(sy))` | Full deflection vs micro-fidget |
| `stick_p90_abs` | p90 of `max(\|sx−med\|, \|sy−med\|)` | Peak aim intensity |
| `duration_s` | `(in_ts[-1]−in_ts[0])/1000` | Protocol length |
| `n_samples_in`, `n_samples_mo` | stream lengths | Dropouts / asymmetry |
| `mo_energy` | `std(mo_yaw)+std(mo_pitch)` (or rms) | Camera motion present? |
| `backend` / metadata | if present in npz keys | H5 |

### 4.3 Pre-registered comparison rules (not outcome-tuned)

Use **aim-active sessions only** unless stated.

| Test | Pre-registered criterion | Supports |
|------|--------------------------|----------|
| **T-H1** | median(P1 `aim_activity_std`) < median(P2∪P3 `aim_activity_std`) **and** median(P1 aim) < `2 × AIM_ACTIVITY_MIN` (= **20.4**) | H1 MARGINAL_AIM |
| **T-H2** | median(P1 `decoupled_energy`) ≥ 0.95 **and** median(P2∪P3 `decoupled_energy`) ≤ median(P1) − 0.05 | H2 HIGH_RESIDUAL |
| **T-H3** | \|median(P1 `lag_ms`) − median(P2∪P3 `lag_ms`)\| ≥ **100 ms** | H3 LAG_REGIME |
| **T-H4** | Among sessions with `aim_activity_std` in the **global aim-active IQR** (or P1’s aim band expanded ±20%), median(P1 coupling) still < TAU_HUMAN **and** median(matched non-P1 coupling) ≥ TAU_HUMAN | H4 GENUINE_LOW_COUPLING |
| **T-H5** | Any protocol field (backend, region, duration bin, label) differs for ≥50% of P1 vs ≥50% of P2∪P3 with a single discrete value | H5 PROTOCOL_MIX |

**Primary assignment algorithm:**

```text
if n_P1_aim_active < 5:  -> H0 INCONCLUSIVE
else apply T-H1, T-H2, T-H3, T-H5, T-H4 in that order;
     first True -> that Hi
     if none True -> H0 INCONCLUSIVE
     if multiple True -> primary = first True; secondaries = rest (notes only)
```

Order preference: **prefer environmental/protocol explanations (H1–H3, H5) before genuine player difference (H4).**

---

## 5. N-plan / corpus

| Item | Plan |
|------|------|
| Corpus | `sessions_l9/*.npz` only (same as P0-A) |
| Focus set | Aim-active sessions (`aim_activity_std ≥ 10.2`, coupling defined) |
| Minimum for non-H0 | `n_P1_aim ≥ 5` (v2 has 7 — OK) |
| Comparators | P2∪P3 aim-active pooled; also report P2 and P3 separately |
| Untagged `?` | Report; **exclude** from P2∪P3 comparator pool (unknown label) |
| New captures | **Not required** for this diagnostic |

---

## 6. Closed-enum diagnostic verdicts

```text
MARGINAL_AIM          T-H1 first true
HIGH_RESIDUAL         T-H2 first true
LAG_REGIME            T-H3 first true
PROTOCOL_MIX          T-H5 first true
GENUINE_LOW_COUPLING  T-H4 first true
INCONCLUSIVE          n too small or no test true
UNVERIFIABLE          harness/IO failure
```

Report always includes:

- Full per-player table (all scored + aim-active subsets)  
- P1 session-level rows (path, coupling, aim, lag, dec, range) for audit  
- `secondaries: []`  
- Explicit: **`p0a_v2_separated_unchanged: true`**

---

## 7. Honest non-claims / limits

1. **Does not reopen or amend** P0-A v2 SEPARATED.  
2. **Does not** claim P1 is non-human or automation.  
3. **Does not** fix capture; offline classification only.  
4. **Does not** require min-per-player-n on the OP (v3 still optional).  
5. **Does not** establish population-certified multi-player presence.  
6. Small n (P1 aim-active n=7) → labels are **developer_self diagnostics**, not field science.  
7. H4 “genuine” means *residual after aim-matching*, not a biometric identity claim.

---

## 8. Design-level acceptance tests

| ID | Pin |
|----|-----|
| T1 | Uses same `analyze_session_data` + aim_activity_std as P0-A v2 |
| T2 | AIM_ACTIVITY_MIN / TAU_HUMAN imported or duplicated as frozen equals of P0-A constants |
| T3 | Primary label is one of the closed enum; no free-text verdict |
| T4 | Never writes `verdict: SEPARATED` for this study (different schema) |
| T5 | Untagged `?` excluded from P2∪P3 comparator |
| T6 | Session-level P1 table present in JSON |
| T7 | Offline-only |
| T8 | Schema string `p1-anomaly-diagnostic-v0` |

---

## 9. Operator-decisions table

| ID | Decision | Default | Operator |
|----|----------|---------|----------|
| **D-P1A-1** | Run offline diagnostic on `sessions_l9` only | Yes | ☐ accept ☐ amend |
| **D-P1A-2** | Hypothesis order H1→H2→H3→H5→H4; H0 if none | Yes | ☐ accept ☐ amend |
| **D-P1A-3** | T-H1 marginal aim band: median P1 aim < 2×AIM_ACTIVITY_MIN (20.4) | Yes | ☐ accept ☐ amend |
| **D-P1A-4** | T-H2 residual: P1 median dec ≥ 0.95 and ≥0.05 above P2∪P3 | Yes | ☐ accept ☐ amend |
| **D-P1A-5** | T-H3 lag gap ≥ 100 ms | Yes | ☐ accept ☐ amend |
| **D-P1A-6** | No min-per-player-n on P0-A; this study is diagnostic only | Yes | ☐ accept ☐ amend |
| **D-P1A-7** | Proceed Claude audit → build → run | Hold for GO | ☐ GO ☐ hold |

---

## 10. CODE-TRUTH

| Item | Location |
|------|----------|
| Load/score | `l9_presence/session_recorder.py` — `load_session`, `analyze_session_data`, `SessionData.player` |
| Oracle / abstain | `l9_presence/coupling.py` — `MIN_STICK_STD`, `extract_features` activity gate `MIN_STICK_STD * 255` |
| Aim gate constants | `l9_presence/presence_separation_study.py` (v2) — reuse `AIM_ACTIVITY_MIN` / measure |
| P0-A v2 result | `audits/p0a-presence-op-v2-2026-07-09.json` — `player_histogram`, `players_below_tau_human: ["P1"]` |
| Design parent | `docs/p0a-presence-separation-study-design.md` §5.1.4 F-P0A-V2-1 |
| Corpus | `sessions_l9/*.npz` — 59 files; player field on npz when present |

**Empirical kill-check (2026-07-10, designer, not the harness verdict):**

| Player | n_aim | med_c | med_aim | med_lag_ms | med_dec |
|--------|-------|-------|---------|------------|---------|
| P1 | 7 | 0.091 | 14.8 | 217 | 0.992 |
| P2 | 8 | 0.593 | 51.2 | 33 | 0.648 |
| P3 | 12 | 0.379 | 49.0 | 300 | 0.856 |

These numbers **motivate** the hypothesis set; the harness must recompute and apply T-H* rules, not hard-code this table as the verdict.

**Suggested implementation (Claude):**

- `l9_presence/p1_anomaly_diagnostic.py` (pure)  
- `scripts/run_p1_anomaly_diagnostic.py`  
- `l9_presence/tests/test_p1_anomaly_diagnostic.py`  
- Output: `audits/p1-anomaly-diagnostic-2026-07-10.{json,md}`

---

## 11. Sequence after this lane

| Next | When |
|------|------|
| **P0-B thin wedge thesis** | After diagnostic is on the record (cites SEPARATED + F-P0A-V2-1 + this label) |
| **RP-4** | When operator is at the rig |
| **Optional P0-A v3** | Only if diagnostic + operator want uniform-across-players claim |

---

## 12. What success looks like

A one-page audit artifact:

```text
PRIMARY: MARGINAL_AIM | HIGH_RESIDUAL | ...
secondaries: [...]
p0a_v2_separated_unchanged: true
P1 aim-active n=7, medians {...}
T-H1..T-H5: pass/fail table
```

No OP re-run required. No constant changes.

---

*End of P1 anomaly diagnostic design v0 — 2026-07-10. Awaiting Claude audit + operator §9.*
