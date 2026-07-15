# A2A-POEP-P2 · Round 09 · Grok Design
**Role:** model designer + data-quality adversary  
**Artifact:** `round-09-grok-design.md`  
**Model:** RBM-v0 (Reflex Baseline Model, population / single certified Edge)  
**Device:** registered DualShock Edge `581a836c…` only  
**Corpus (measured):** usable=68 · independent=52 (burst-dedup ≥5s) · campaign-nulls=22 · CCO-nulls=571  
**Rails (non-negotiable):** population model only · no identity · no liveness verdict shipped · `poep_enabled=False` · pure-Python + stdlib preferred

---

## Q1 · RBM-v0 definition

### Proposal Q1-A · Dual-channel score with hard floor + soft consistency

| Field | Content |
|-------|---------|
| **id** | `RBM-v0-DEF-01` |
| **design** | **Two layers, one scalar.** (1) **Hard membership floor** (fail-closed gate, boolean): `latency_ms ∈ [80, 300]` AND `peak_lsb ≥ 1000`. Floor is fixed from measured p5/p95 with a 5–10 ms / ~50 LSB margin off the empirical edges (observed p5_lat=86 → floor 80; p95_lat=298 → ceiling 300; p5_peak=1054 → floor 1000). Rows failing the floor get `score=0.0` and `band=OUT`. (2) **Soft consistency score** on floor-passers only: a pure-Python **2-feature z-distance** on `(latency_ms, peak_lsb)` against independent-positive population moments, optionally extended by **one** diagnostic feature if a pre-registered pilot proves lift (see Q1-B). Score maps to `[0,1]` via a clamped exponential of Mahalanobis-lite (diagonal covariance only — no full matrix, no sklearn). Default formula (stdlib `math` only): `d² = ((L−μ_L)/σ_L)² + ((P−μ_P)/σ_P)²`; `score = exp(−0.5 · d²)` clamped to `[0,1]`. Moments `(μ_L,σ_L,μ_P,σ_P)` are **frozen constants** computed once from the 52 independent positives and written into a JSON snapshot (`rbm_v0_params.json`), not recomputed at inference. |
| **rationale** | Latency band + peak floor already capture the physiology the gate was built for (in-band human reflex + strong IMU corroboration). On this corpus the latency distribution is tight (mean 173, sd 63; p5–p95 ≈ 86–298) and peaks are strong (med 1494). That is enough for a **calibrated population consistency** claim without identity features. Diagnostic fields (`precursor_gap_ms`, `pre_accel_mean`, `probe_r2_force`, `probe_hold_ms`, …) are **hypothesis candidates**, not free features — N=52 cannot honestly support an 11-dim model. Output is a **scalar score** so operators can set operating points (FAR ceilings); hard band alone cannot express “how central” a reflex is. Floor remains boolean so junk / out-of-band / CCO-physics never get a soft high score by accident. |
| **acceptance** | (a) Module `l9_presence/rbm_v0.py` exposes: `RBMV0Params` (frozen dataclass), `load_params(path)`, `hard_floor(latency_ms, peak_lsb) -> bool`, `score_row(features: dict, params) -> float` in `[0,1]`, `evaluate_batch(rows, params) -> list[float]`. (b) Zero numpy/sklearn imports. (c) Floor rejects 100% of rows with `latency_ms < 80 or > 300` or `peak_lsb < 1000`. (d) On the 52 independents, median score ≥ 0.5 and p5 score ≥ 0.15 (sanity: positives land mid-to-high, not all 1.0). (e) Params file is content-addressed (SHA-256 of canonical JSON) and logged; no silent retrain. |

### Proposal Q1-B · Diagnostic features: pilot, then at most +1

| Field | Content |
|-------|---------|
| **id** | `RBM-v0-DEF-02` |
| **design** | **Do not ship multi-feature diagnostic scoring in v0.** Run a **pre-registered single-feature pilot** (offline, pure-Python): for each candidate `f ∈ {precursor_gap_ms, pre_accel_mean, probe_r2_force, probe_hold_ms, reflex_gap_ms}`, compute rank-biserial / Mann–Whitney U (stdlib implementation) between the 52 independents and the 22 campaign nulls (primary negative) + a stratified subsample of CCO (secondary negative; see Q2). **Promote at most one** feature into the soft score **iff** (i) U-test p-equivalent separation is stronger than latency alone on campaign-nulls, (ii) the feature is defined (non-null) on ≥90% of independents, (iii) adding it does not drop LOO d′ below latency+peak alone. Default RBM-v0 ships **latency+peak only**; diagnostic lift is a v0.1 amendment with a new params hash. |
| **rationale** | Against the real distribution, latency+peak already separate “human-ish in-band IMU event” from “no response” and from CCO device-physics (different mechanism). Extra dimensions on N=52 buy variance, not truth. Pilot prevents cargo-cult feature inclusion. |
| **acceptance** | Pilot script `scripts/rbm_v0_feature_pilot.py` prints a table: feature · n_defined · U-stat · separation vs latency-alone. Default merge path does **not** include diagnostics unless pilot report commits `PROMOTE: <feature>` with the three criteria above. |

**Q1 answer (normative):** Hard floor = latency ∈ [80, 300] ms + peak ≥ 1000 LSB. Soft output = **scalar reflex-consistency score** on `(latency, peak)` under frozen population moments. Diagnostic_json is **not** in the v0 score unless the pilot promotes exactly one feature under the acceptance bar.

---

## Q2 · Null class + acceptance metric

### Proposal Q2-A · Dual-null taxonomy + two-bar calibration

| Field | Content |
|-------|---------|
| **id** | `RBM-v0-NULL-01` |
| **design** | **Negatives are two strata, never pooled blindly.** (N1) **Campaign nulls** (n=22): same campaign, stimulus fired, `NO_RESPONSE` / `INCONCLUSIVE` — the honest hard negative for “would a reflex scorer fire when no usable reflex was observed?” (N2) **CCO device-physics** (n=571): IMU-live, different mechanism — the mechanism-confusion negative. Scoring: every null row is evaluated with the same floor+score path; CCO rows that fail the hard floor (expected for many) contribute to **floor FAR = 0** by design; CCO rows that **pass** the floor are the dangerous set (**mechanism-confusion candidates**) and must be scored soft. **Primary metric (campaign nulls):** empirical **false-accept rate at operating point τ\*** where true-accept rate on independents ≥ 0.90 (TPR≥0.90). Report `FAR_campaign(τ*)` and `AUC` via trapezoid on ROC built from the 52 scores vs 22 scores (pure-Python ROC: sort by score, walk). **Secondary metric (CCO pass-floor subset):** `FAR_cco_floorpass(τ*)` — must be reported even if N_floorpass is small. **d′ (optional, reported):** `d′ = (μ_pos − μ_neg) / sqrt(0.5(σ_pos²+σ_neg²))` on scores for campaign nulls. |
| **rationale** | 22 campaign nulls are scarce but distributionally matched (same campaign, same device, stimulus present). CCO is large but **not exchangeable** with campaign nulls — pooling would inflate “AUC” by easy mechanism differences and hide the real risk. Calibration honesty requires the operating-point FAR on N1, not only a global AUC. |
| **acceptance** | **Pass bar for “RBM-v0 calibrated” (all must hold):** (1) `TPR_indep(τ*) ≥ 0.90` on the 52 independents. (2) `FAR_campaign(τ*) ≤ 0.10` (≤2/22 accepts at τ\*). (3) ROC-AUC on (52 vs 22) ≥ **0.85**. (4) `d′_campaign ≥ 1.5` on scores (or explicit FAIL with numbers if not). (5) Report `n_cco_floorpass` and `FAR_cco_floorpass(τ*)` with no minimum (transparency); if `n_cco_floorpass ≥ 30`, require `FAR_cco_floorpass(τ*) ≤ 0.05`. (6) All metrics computed by `scripts/rbm_v0_calibrate.py` writing `audits/rbm_v0_calibration_<date>.json` with frozen params hash. **Not calibrated** if any of (1)–(4) fail. |

### Proposal Q2-A′ · Operating point freeze

| Field | Content |
|-------|---------|
| **id** | `RBM-v0-NULL-02` |
| **design** | Choose τ\* once on the calibration report as the **lowest** threshold achieving TPR≥0.90 on independents (prefer higher τ among ties to minimize FAR). Freeze τ\* in `rbm_v0_params.json` as `operating_threshold`. Inference API returns `{score, above_operating_point: bool}` but **never** maps that to LIVE/HUMAN/PASS for product surfaces. |
| **rationale** | Without a frozen τ\*, “calibrated” is unfalsifiable. |
| **acceptance** | Params include `operating_threshold`; recalibration requires new params hash + new audit file; no silent τ drift. |

---

## Q3 · Validation protocol

### Proposal Q3-A · LOO on 52 + burst integrity + single-player honesty

| Field | Content |
|-------|---------|
| **id** | `RBM-v0-VAL-01` |
| **design** | **Primary:** Leave-one-out on the **52 independent** positives only for estimating score stability under moment re-fit: for each i, recompute `(μ,σ)` on the 51, score row i, collect LOO scores. Report LOO mean/sd of score and LOO TPR at the frozen τ\* **refit rule** (τ\* re-chosen on the 51 with same TPR≥0.90 rule, then applied to left-out — nested LOO). **Negatives fixed** (22 campaign nulls + CCO): never LOO-out positives into the null set. **Held-out split is secondary only:** if used, 40 train / 12 hold on independents (seed fixed `seed=20260715`), moments from train only; one-shot report — not the headline number when N_hold=12. **Burst guard (already in corpus):** independence definition is burst-dedup ≥5s; validation **must refuse** any row not in the independent set when claiming “N=52.” **Overfit guards (single operator, single device):** (G1) Model capacity capped at 2 (or 3 if pilot-promoted) diagonal features — no trees, no NN, no per-session fine-tune. (G2) Moments frozen after calibration; production path has **no online update**. (G3) Report **coefficient of variation** of LOO scores; if CV > 0.35, flag `UNSTABLE_POPULATION_ESTIMATE`. (G4) Explicit claim tag in every audit: `scope=single_operator_single_edge_N52`. (G5) Optional bootstrap (200 resamples of 52 with replacement, stdlib `random`) for 90% CI on AUC — report only; do not pick features from bootstrap. |
| **rationale** | N=52 is small; a 12-row holdout is noisy for a single headline metric. Nested LOO on moments+τ is the honest stability check for a 2-feature frozen Gaussian score. Capacity + freeze + independence definition are the real anti-overfit controls for single-player/single-device data — not k-fold theater. |
| **acceptance** | (a) `scripts/rbm_v0_validate.py` emits LOO nested TPR/FAR/AUC and CV. (b) Pass if nested-LOO TPR median ≥ 0.85 **and** FAR_campaign at nested τ still ≤ 0.15 (slightly looser than full-fit 0.10 to account for LOO noise) **and** CV ≤ 0.35. (c) Fail closed with `UNSTABLE` if CV > 0.35 or nested FAR > 0.15. (d) Independent-set membership asserted; usable-but-not-independent rows may appear in a sensitivity table only. |

---

## Q4 · Honest scope + claim ceiling

### Proposal Q4-A · Claim lattice (must / may / must-not)

| Field | Content |
|-------|---------|
| **id** | `RBM-v0-SCOPE-01` |
| **design** | **RBM-v0 is a population reflex-consistency scorer for one certified Edge under one operator’s campaign.** |
| **rationale** | Gate MET (52 independent usable) authorizes a **device-local population baseline**, not a biometric identity model and not a shipped liveness product. |
| **acceptance** | Docs + module docstring + audit JSON include the lattice below verbatim-equivalent. |

**MAY claim (RBM-v0):**
- On this registered Edge, under this capture campaign, in-band IMU-corroborated reflexes cluster in latency/peak space with measurable separation from same-campaign non-responses at the frozen operating point.
- A scalar score ∈ [0,1] ranks consistency with that frozen population snapshot.
- Calibration metrics (AUC, FAR@τ\*, d′, LOO stability) for the measured N=52 / N_null=22 (+ CCO reporting).

**MUST NOT claim:**
- **Identity** (who is holding the controller; cross-person ranking; enrollment; impostor rejection as person-ID).
- **Liveness verdict** as a product/gate outcome (`HUMAN` / `LIVE` / `BOT` / tournament PASS-FAIL). Score ≠ verdict; no API maps score→eligibility.
- **Cross-device transfer** (other Edges, DualSense non-Edge, Xbox, BT-only paths) without a new device-tagged corpus and new params hash.
- **Cross-operator / multi-player population** generalization.
- **PoEP authenticity / presence proof** completion — RBM-v0 is a baseline building block, not PoEP issuance.

**Config rail (explicit):**
- `poep_enabled` **stays `False`**.
- `L6B_ENABLED` remains false for product enforcement; RBM-v0 calibration scripts are offline / advisory.
- No bridge path auto-enables PoEP from RBM-v0 scores.

| Field | Content |
|-------|---------|
| **id** | `RBM-v0-SCOPE-02` |
| **design** | Ship surface: pure module + offline calibrate/validate scripts + audit JSON. Optional read-only status endpoint may expose `rbm_v0_calibrated: bool` and params hash **only if** wired behind operator read-key and labeled `advisory=true`. No FSCA rule, no tournament preflight P0, no mint gate. |
| **rationale** | Claim ceiling is enforced by non-wiring, not by prose alone. |
| **acceptance** | Grep guard in tests: `poep_enabled` default False unchanged; no import of `rbm_v0.score_row` from session_adjudicator / tournament preflight / VHP mint paths. |

---

## Build sketch (stdlib-only, concrete)

```
l9_presence/rbm_v0.py
  HARD_LAT_MS = (80.0, 300.0)
  HARD_PEAK_LSB = 1000.0
  @dataclass(frozen=True) class RBMV0Params:
      mu_lat, sd_lat, mu_peak, sd_peak, operating_threshold, params_hash, n_independent, created_ts
  def hard_floor(lat, peak) -> bool
  def score_row(lat, peak, params) -> float   # exp(-0.5 d²), 0.0 if not hard_floor
  def above_operating_point(score, params) -> bool

scripts/rbm_v0_calibrate.py   # fit moments on 52, pick τ*, write params + audit
scripts/rbm_v0_validate.py    # nested LOO + CV + null FAR
scripts/rbm_v0_feature_pilot.py  # optional +1 feature promotion gate
audits/rbm_v0_calibration_<date>.json
```

Data path: rows already carry `diagnostic_json` + usable/independent flags from the reflex gate; calibrator reads only `is_independent_usable` positives and the dual null strata.

---

## Red-team (adversary pass on this design)

| # | Attack / failure mode | Severity | Mitigation in this design | Residual risk |
|---|----------------------|----------|---------------------------|---------------|
| R1 | **N=52 is one human, one Edge** — “population” is a euphemism for single-operator physiology. Moments overfit grip, posture, session fatigue. | HIGH | Explicit claim lattice; freeze + no online update; LOO CV guard; scope tag in every audit. | Residual: any claim sounding multi-user is still false. Docs must say **operator-local population**, not “human population.” |
| R2 | **Latency+peak alone may not beat CCO** if some CCO rows land in-band with high peaks (device-physics can mimic magnitude). | HIGH | Dual-null reporting; secondary FAR on floor-pass CCO; do not claim mechanism immunity. | If many CCO pass floor, soft score may need pilot feature or **fail calibration** rather than lower the bar. |
| R3 | **Campaign null n=22** → FAR≤0.10 is only ≤2 false accepts; binomial noise is large (CI wide). | MED | Nested LOO loosens FAR to 0.15; report exact counts not just rates; AUC≥0.85 as second bar. | Still underpowered; “calibrated” is **provisional** — label audits `PROVISIONAL_N22_NULLS`. |
| R4 | **Hard floor [80,300]/1000 cherry-picked** from same data used for scoring (double-dip). | MED | Floor taken from gate physiology + rounded margins; moments fit only on independents; document floor as **gate-aligned constants**, not MLE. | Mild leakage remains; future v0.1 should freeze floor on a prior campaign if a second capture exists. |
| R5 | **Burst-dedup ≥5s** may still leave within-session correlation (same posture block). LOO independence assumption violated → optimistic AUC. | MED | Sensitivity table on usable=68 vs independent=52; refuse non-independent in headline N. | Cannot fully de-correlate single sessions without multi-day multi-block design. |
| R6 | **Scalar score → product pressure** to ship liveness (“just threshold it”). | HIGH | No verdict mapping; wiring ban from preflight/mint/adjudicator; `poep_enabled=False` test. | Organizational residual only — enforce in PR review. |
| R7 | **Diagonal Gaussian score** is wrong if latency/peak are heavily skewed or correlated. | LOW–MED | Report skew of residuals; if LOO CV fails, do not ship; optional rank-transform (percentile within frozen train set) as v0.1 without sklearn. | Acceptable for v0 if pass bars hold empirically. |
| R8 | **Feature pilot data-snooping** if all diagnostics are peeked then one is “promoted.” | MED | Pre-register pilot criteria; default ship without diagnostics; promotion = new params hash + re-run full Q2/Q3 bars. | Operator discipline required. |
| R9 | **Null-route / artifact rows** mislabeled usable would poison moments (historical junk peak=0). | HIGH | Calibrator asserts gate predicate `is_usable_reflex` (B1+B2) + independent; unit test rejects peak=0 / out-of-band. | Trust gate correctness; RBM does not re-litigate B1+B2. |
| R10 | **stdlib ROC/AUC bugs** (ties, constant scores) silently pass. | LOW | Tests: separated toy sets → AUC=1; identical scores → AUC=0.5; ties handled. | — |

**Red-team verdict:** Design is **buildable and rail-compliant** if and only if audits stay provisional on n=22 nulls, CCO is never used to inflate a single pooled AUC, and no path converts score→liveness. The largest scientific risk is **R1+R2**: a well-calibrated single-operator Edge baseline can look “strong” while remaining non-transferable and mechanism-confused on CCO floor-passers. RBM-v0 should be named and sold as **Reflex Consistency Snapshot (device-local)**, not as a population biometric.

---

## Normative summary (one screen)

| Item | RBM-v0 |
|------|--------|
| Floor | latency ∈ [80, 300] ms ∧ peak ≥ 1000 LSB |
| Score | scalar ∈ [0,1] from frozen 2-feature diagonal z-distance (latency, peak) |
| Diagnostics | pilot-only; ≤1 promotion; default off |
| Nulls | 22 campaign (primary FAR/AUC/d′) + 571 CCO (floor-pass FAR report) |
| Pass bar | TPR≥0.90 @ τ\*; FAR_campaign≤0.10; AUC≥0.85; d′≥1.5; LOO CV≤0.35 |
| Validation | nested LOO on 52 independents; capacity freeze; no online retrain |
| Claims | device-local reflex consistency only |
| Forbidden | identity · shipped liveness verdict · cross-device · PoEP enable |
| Config | **`poep_enabled=False`** (unchanged) |
| Stack | pure Python + stdlib; no numpy/sklearn required |

**End of round-09-grok-design.md**
