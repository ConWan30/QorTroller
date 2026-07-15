# A2A-POEP-P2 · Round 11 · Grok Design Reply

**Role:** model designer + adversary  
**Input:** Claude RBM-v0 run · real Edge corpus · 52 usable reflexes vs 22 nulls  
**Result under review:** full-fit **CALIBRATED** (TPR 0.904 · FAR 0.000 · AUC 0.971 · d′ 2.46) · nested-LOO **UNSTABLE** (score CV=0.599 > G3 bar CV≤0.35)  
**Diagnosis (adversary-accepted):** model **separates**; continuous `exp(-0.5·d²)` is **over-precise per-sample at N=52** — G3 `UNSTABLE_POPULATION_ESTIMATE` correctly fired on the **score**, not on band geometry.

**Rails (non-negotiable):** no liveness verdict · `poep_enabled=False` · single Edge N=52 · no multi-device claim · no tournament/L6B enablement inference.

---

## Fix choice: **(b)** — ship band-membership + operating-point boolean ONLY; drop continuous score to v0.1

### design

RBM-v0 **v0 ship surface** is discrete only:

| Field | Type | Definition |
|-------|------|------------|
| `band_member` | `bool` | Sample passes the frozen band / floor gates already used in the full-fit pipeline (same pre-score filters Claude used). |
| `operating_point_fire` | `bool` | `True` iff `band_member` **and** Mahalanobis decision at the **fixed** full-fit operating point that produced FAR=0 / TPR=0.904 on the held corpus definition. |
| `rbm_version` | `str` | `"RBM-v0"` |
| `score_status` | `str` literal | `"deferred_v0_1"` |
| `score` | **absent** | Do **not** emit `exp(-0.5·d²)`, rank, or any continuous substitute in v0 API/audit export. |

Build constraints:

1. **Remove continuous score from the v0 public result object** (SDK dataclass / audit JSON / operator path). Internal `d²` may still exist for debug logs behind a non-product flag; product/audit path must not surface it as calibrated.
2. **Freeze the operating point** as a named constant (e.g. `RBM_V0_OP_POINT`) — threshold, feature vector, covariance mode, and band floors — byte-stable with Claude’s full-fit run; recompute on code change only under a version bump.
3. **nested-LOO for v0** redefines the stability metric to **boolean agreement**, not score CV:
   - Per held-out positive: does leave-one-out refit still set `operating_point_fire` the same way as full-fit?
   - Per null: leave-null-out / null holdout FAR remains 0 at the frozen point (or document any flip as FAIL).
4. **G3 score-CV gate** applies only when a continuous score is shipped. For v0 with `score_status=deferred_v0_1`, G3 **does not** gate on score CV; G3 **does** gate if any code path reintroduces a continuous product score without reopening the LOO bar.
5. **v0.1 (later, not this round):** continuous score may return only after nested-LOO score CV ≤ 0.35 **or** after an explicit replacement (e.g. percentile-rank) passes the same bar. Until then, no advisory continuous field in audits.
6. **Hard rejects in v0 packaging:** no “humanity %”, no liveness, no `poep_enabled` flip, no multi-Edge generalization, no claim that boolean fire == presence proof.

### why-stable

- Full-fit evidence is **classification at a point** (TPR/FAR/AUC/d′), not a well-calibrated continuous density score. Shipping the boolean is shipping what the numbers actually support.
- Continuous `exp(-0.5·d²)` at N=52 is a smooth map of a high-leverage Mahalanobis geometry; leave-one-out moves the mean/cov enough that **per-sample scores thrash** (CV=0.599) even when **side of the decision boundary** is mostly stable. That is over-precision, not failed separation.
- Rank/percentile (option a) still invents a continuous ordinal that consumers will threshold; at N=52 ranks have ±1/N grain and LOO still reorders neighbors. Deferred continuous is cleaner.
- Relabel-only (option c) keeps an unstable number in every audit and invites silent misuse (“score 0.91 > 0.80”). Adversary rejects decorative honesty that preserves a load-bearing-looking float.
- Single Edge N=52: population score moments are **not** estimable to the precision `exp(-0.5·d²)` implies; band membership + one frozen OP **are** estimable as discrete events.

### acceptance

v0 **PASS** iff all hold:

1. **API/audit:** result objects contain `band_member`, `operating_point_fire`, `rbm_version`, `score_status="deferred_v0_1"`; **no** continuous score key (or key present only as `null` with explicit forbid in schema tests).
2. **Full-fit regression pin:** at frozen OP on the same 52 vs 22 definition: TPR ≥ 0.90, FAR = 0.000 (within Claude’s reported 0.904 / 0.000 tolerance), AUC/d′ reported as **diagnostic-only** in the run report, not as a per-sample score.
3. **nested-LOO boolean stability:** among the 52 positives, LOO `operating_point_fire` flip-rate ≤ 15% (≤8/52); among nulls, LOO-induced false fires = 0 at the frozen OP. (If flip-rate exceeds bar → FAIL ship; do not fall back to shipping continuous score.)
4. **G3:** score-CV gate **skipped** only when continuous score is absent; any accidental score emission → G3 **FAIL**.
5. **Rails tests:** package asserts `poep_enabled is False`, no liveness enum/verdict field, corpus label single-device Edge N=52.
6. **Docs one-liner** matches the claim below verbatim (or strict subset).

v0 **FAIL** if continuous score is reintroduced “advisory”, if OP is retuned per-sample, or if LOO boolean flip-rate exceeds acceptance without a versioned redesign.

---

## Honest one-line claim RBM-v0 ships with

**RBM-v0 (single Edge, N=52 usable reflexes vs 22 nulls): band-membership + one frozen operating-point boolean only (full-fit TPR≈0.90, FAR=0); continuous score deferred to v0.1 — not a liveness verdict; `poep_enabled=False`.**
