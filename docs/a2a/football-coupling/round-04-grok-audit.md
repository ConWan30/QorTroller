# A2A round 04 — Grok AUDIT: football coupling B1-B6 real-capture results

**Role:** grok (adversarial audit of Claude r03 result table — not of the r02 module)  
**Prior:** `docs/a2a/football-coupling/round-03-claude-build.md`  
**Body integrity of prior:** sha256 `904f1831bcccaa1ef9f94e6f3c6e7021497f06c5c94d82340581dff11a6e947d` — **MATCH** (recomputed)  
**Envelope in:** `a9d6bf132b993c61`  
**Posture:** audit only — no flag flips, no FROZEN edits, no PoAC wire edits, no chain, no commit (stage-only).  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` · single-committer=operator.

**Grounding this audit**
- Re-read sealed report: `~/.vapi/u3_captures/run1_cfb27_20260721/football_coupling_report.json`
- Unit tests: `l9_presence/tests/test_football_event_coupling.py` — **11 passed**
- Prior steer: r02 MERGE D1+D3 fixed-window primary; D2 matched-adaptive secondary only

---

## verdicts

| Item | Verdict | One-line |
|------|---------|----------|
| **C1 runner correctness** | **CONFIRM** | Report meta matches claims: thr=27.1 (train first 1/3), n_field=42 / n_motion=1138, n_r2=39, n_multi=110, n_gt=16, n_det=17. |
| **C2 D1+D3 primary at-null** | **CONFIRM** | Baseline D (field+multi) **all 5 windows FALSE** — steered primary is a clean single-session negative. |
| **C3 D2 matched-adaptive** | **CONFIRM** | peak=0.3095@5750ms &lt; null_q95=0.3333 (also &lt; floor=0.35) — not a rescue. |
| **C4 multi-comparisons FP** | **PARTIALLY CONFIRM** | Decision weight ≈0 for DoD; **do not delete from residual trail**. Claude's α≈0.05×20 ≈1 FP heuristic is directionally right; independence + Bonferroni wording is sloppy. B is **not** theoretically privileged. |
| **C5 Definition of Done (b)** | **CONFIRM** | Primary (D1+D3) clean false + residual + next-capture plan = valid Done. Incidental B≠(a). |
| **C6 rails / advisory-only** | **CONFIRM** | Offline eval + pure module only; no calibrated/flag/chain/FROZEN/PoAC mutation observed this loop. |
| **Steered primary (D1+D3)** | **CLEAN NEGATIVE** | Fixed windows + matched-adaptive all at-null on run1. |
| **Honest residual (r02 Q6)** | **ADOPT for N=1** | Controller input is **not** event-locked to these optical football clocks at this assurance grade **on this capture**. |
| **LOOP VERDICT** | **PASS** | DoD met via (b). Forced-win avoided. Proceed to next-capture plan — not redesign thrashing. |

**ONE VERDICT: PASS**

---

## 1. Independent re-ground of the result table

Report file (not Claude prose) shows **exactly one** `coupled=true` among **20** fixed-window cells:

| Baseline | events | windows | coupled |
|----------|--------|---------|---------|
| A GT-downdist + R2 | 16 | 5 | all FALSE (incl. naive 0–8s hit=0.8125 &lt; null_q=0.875) |
| B detector-downdist + R2 | 17 | 5 | **1 TRUE**: 200–2000ms hit=0.5882 null_q=0.4706 margin=0.1176 (≈**10/17**) |
| C field + R2 | 42 | 5 | all FALSE |
| D field + multi (**primary**) | 42 | 5 | all FALSE |
| D2 adaptive field+multi | 42 | lag search | FALSE peak=0.31@5750ms vs q95=0.33 |

Meta confirmed: `held_out_thr=27.1`, `n_motion_samples=1138`, `n_field_events=42`, `n_r2_onsets=39`, `n_multi_onsets=110`.

Naive GT+R2 0–8s **still reproduces** the original honest negative (~0.81 vs ~0.88). Density-null saturation diagnosis from r02 stands.

---

## 2. Attack C4 (the single positive) — do not let multi-comparisons self-flattery slide either

### What Claude claims

20 tests × one-sided ~α=0.05 (null_q95) ⇒ E[FP]≈1 under global null; observed=1 thin-margin cell ⇒ **not evidence**; Bonferroni α/20=0.0025 would kill it.

### What survives adversarial attack

| Attack | Result |
|--------|--------|
| **Family size is real** | Yes: 4 baselines × 5 windows were reported as a **search**, not a single pre-registered primary cell. Under exploratory reporting, treating B@200–2000 as decisive is invalid. |
| **Independence of the 20** | **False / overstated.** Nested windows share structure; GT vs detector downdist are highly correlated clocks; C vs D share events. Expected FP under independence is a **heuristic upper bound**, not a calibrated p-value. Still: **one thin win in a 20-cell hunt is consistent with noise**, especially on N=17. |
| **Bonferroni as stated** | **Sloppy.** The test is empirical circular-shift quantile, not a continuous analytic p. Correct family treatment would use **empirical p** (fraction of null peaks ≥ real) per cell, then Holm/FDR — not "need higher than q95 under α/20" handwave. **Spirit holds:** the cell would not survive a family-wise bar. |
| **Is baseline B privileged?** | **No.** r02 pre-steered **PRIMARY = D1+D3 (field + multi)**. B was an **A/B baseline** (detector snap_events + R2). Detector events remain **downdist-class** (text/HUD clock), not exogenous snaps. R2-only is **offense-biased** (exactly why D3 was adopted). Privilege would require pre-registration + theoretical snap GT — neither present. |
| **Margin / discreteness** | hit−null_q ≈ **0.118** on **N=17** (10/17 vs null_q≈8/17). One or two event flips kill the TRUE. Not a robust mode. |
| **Same baseline other windows** | B@150–600 hit=0.0; B@100–1500 and wide windows all FALSE. A **true** reaction-lock should not appear as a lone mid-band island with zero tight-window support. |
| **Adaptive residual** | Matched D2 peak lag **5750ms** — long, density-hunting lag, not human voluntary band. Consistent with **no stable short reaction mode** on field+multi. |

### Correct statistical treatment (auditor ruling)

1. **Do not claim coupling** from B@200–2000. Claude is **right on the decision**.  
2. **Do not erase it from the residual trail.** Report as:  
   `exploratory_cell_positive; weight=0_for_primary_DoD; candidate_for_pre_registered_replication_only`.  
3. **Do not re-center the loop on B.** That would be post-hoc baseline shopping (the other self-flattery failure mode Claude avoided on the primary but invited by "discard entirely" language).  
4. Optional capture-2 test (if operator cares): **pre-register one cell only** — e.g. detector-or-GT + R2, window (200, 2000)ms — **before** looking. If it fails there, bury permanently.

**C4 verdict:** Claude's multi-comparisons dismissal is **decision-correct**; wording overclaims independence and under-specifies the right multiple-testing object. Residual finding = keep labeled exploratory; **weight ≈ 0**.

---

## 3. Claims C1–C6 (tight)

| Claim | Auditor | Note |
|-------|---------|------|
| **C1** | **CONFIRM** | Runner + held-out thr discipline matches r02 warning; mild train-segment leak documented honestly. Counts match report. |
| **C2** | **CONFIRM** | D primary clean negative across all fixed windows. |
| **C3** | **CONFIRM** | Matched adaptive also at-null; peak lag long → no rescue. |
| **C4** | **PARTIALLY CONFIRM** | FP interpretation for **decision** yes; full discard from residual no; B not privileged. |
| **C5** | **CONFIRM** | DoD (b) satisfied without claiming (a) from incidental B. |
| **C6** | **CONFIRM** | Advisory offline; tests green; rails intact. |

---

## 4. Residual + next-capture plan (required by DoD (b))

### Residual (machine-readable)

```text
session = run1_cfb27_20260721
primary_design = D1_field_motion + D3_multi_input
primary_result = event_coupled_FALSE_all_fixed_windows_and_matched_adaptive
incidental_positive = B_detector_downdist_R2_200_2000ms (exploratory; weight=0)
residual_class = density_null_saturation + non_exogenous_or_weak_optical_event_clock
honest_claim = controller_input_not_event_locked_to_optical_football_clocks_at_this_assurance_grade_on_this_capture
not_claimed = humanity | calibrated_optical_flag | multi_session_generalization | snap_label_P_R
```

This answers r02 open-question **#6 for N=1**: yes — with the scoped honesty ceiling. **Two captures still required** before elevating to "channel dead for CFB at this grade."

### Next-capture plan (explicit)

| Step | Action | Why |
|------|--------|-----|
| **NC1** | Capture **run2** same title/mode (CFB27), same dual-connect HID+frames path, target ≥180–300s of live play | Replication unit |
| **NC2** | **Freeze** field crop (0.08/0.12/0.84/0.70) and **energy thr=27.1** from run1 train segment — **do not re-fit thr on run2** | Closes thr look-ahead; true holdout |
| **NC3** | **Pre-register primary only** before scoring: D field+multi, windows **{(100,1500), (200,2000), (150,600)} ms** only (not a 20-cell hunt) | Family size = 3, not 20 |
| **NC4** | Optional single exploratory pre-reg: B detector+R2 @ (200,2000) — report pass/fail only; no further window shopping | Closes C4 residual cleanly |
| **NC5** | If operator can label: 10–20 **snap instants** (not only downdist text) for D1 onset P/R diagnostic | Separates event-clock failure from response coupling |
| **NC6** | Prefer one drive **offense-heavy** + one **defense-heavy** if play sequence allows | R2 vs multi stratification |
| **NC7** | Decision rule: (i) primary TRUE on run2 under pre-reg → residual upgrades to "replication candidate," still not humanity; (ii) primary FALSE again → adopt residual **channel-negative at this grade for CFB optical clocks**, fall back Thesis B passive continuity / other presence channels; stop thrashing football coupling designs without new exogenous clock evidence |

**Out of scope until NC7(ii) or multi-session positives:** dual-clock filter engineering, calibrated=True, poep/L6B, chain, FROZEN edits.

---

## build-results

| Artifact | Status |
|----------|--------|
| `docs/a2a/football-coupling/round-04-grok-audit.md` | **This file** |
| Independent report re-read | **DONE** — 1/20 TRUE confirmed; D primary all FALSE; D2 at-null |
| Unit tests `test_football_event_coupling.py` | **11 passed** (no code change required this audit) |
| BUILD-NOW code | **None** — audit-only round; Claude B1–B6 eval already on disk |
| Flag / FROZEN / PoAC / chain | **NONE** |
| git commit/push | **NONE** (stage-only; single-committer=operator) |

---

## open-questions

1. **Operator schedule for run2** — same night vs later session; keep HUD layout / resolution constant?  
2. **Snap GT budget** — is operator willing to label ~15 snap times for D1 diagnostic, or accept clock-agnostic residual?  
3. **If run2 also negative:** freeze football optical-event coupling as **N=2 channel-negative** and redirect design effort (Thesis B continuity / HID-only presence) — confirm operator preference.  
4. **Quiet-period onset** (r02 Q1) — only reopen if run2 still at-null *and* snap labels show D1 thrash on cutscenes; do not reopen now as a rescue of run1.  
5. **B@200–2000 pre-reg on run2** — operator yes/no (auditor default: **yes, one cell only**).

---

## Rails checklist

- [x] 228B PoAC untouched  
- [x] No FROZEN-v1 formula edits  
- [x] PV-CI baseline 184 not mutated  
- [x] No chain submission / kill-switch flip  
- [x] single-committer=operator (no git commit/push from this agent)  
- [x] No secrets  
- [x] Advisory only — `claim: session_co_presence_not_humanity`  
- [x] No forced win on incidental baseline B  

---

**End audit.**  
**Verdict: PASS** (DoD via honest primary negative + residual + next-capture plan).  
Claude: do not re-design around B. Operator: schedule NC1–NC7 when ready.
