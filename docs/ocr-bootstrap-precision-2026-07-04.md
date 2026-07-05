# G1' — OCR bootstrap precision characterization (dual-instrument) — 2026-07-04

**Status: FINAL — Tesseract-era archive runs (2026-07-04) PLUS v6-engine WZ live-match addendum
(2026-07-05). Zero false own-handle reads held across BOTH engine eras, 3,091 crops total. See the
ADDENDUM section near the end for the WZ live-match results — read that first if you only care about the
newest captures; the body above it is the original three-archive-session characterization.**

Gate document for **HOLD 1** of the Fusion Arc Increment 1 plan: operator confirms the zero-false-read bar
held across BOTH instruments before any further wiring rides on `ocr_row_v1`.

## What was measured

`scripts/killfeed_audit_lane.py` (read-only, dual-instrument) over the full historical crop corpus:

| Corpus | Crops | Provenance | Run |
|---|---|---|---|
| `retina_kf_crops` (rolling buffer at 2026-07-03) | 611 | mixed-era dense crops | 2026-07-03 (prior) |
| `retina_kf_archive/seg3_20260701_052921` | 600 | seg3 match archive (permanent) | 2026-07-04 |
| `retina_kf_archive/sess_ab_1783138825` | 600 | sess_ab match archive (permanent) | 2026-07-04 |
| `retina_kf_archive/sess_hid_v1_1783174566` | 600 | sess_hid_v1 match archive (permanent) | 2026-07-04 |

Instruments (independent at the VERDICT MECHANISM — glyph read vs template score):
- **A `ocr_row_v1`** — `killfeed_ocr_bootstrap.tight_row_ocr`: locate via loose feed_v1 (≥0.40), tight-crop,
  upscale+Otsu+psm-7 both polarities, strict `canon()` match. Engine chain default = `tesseract_row_v1`
  (this document characterizes the TESSERACT era; the v6 parity recheck is D-PKG-1, separate gate).
- **B `template_ensemble_v1`** — max-over-anchors `killer_slot_best` at the frozen 0.66 floor over
  feed_v1 + roster_v1 + the 16-anchor R4 session library; non-kill refined via `classify_panel`.

2026-07-04 runs used the new `--workers` process pool (scheduling-only parallelism; 12-crop probe verified
byte-identical to sequential output before use).

## Zero-false-read bar (the hard gate)

### Prior 611-crop run (2026-07-03): 3 candidate false reads → pre-adjudicated DIFFERENT-ROW, evidence evicted

| Crop (ts) | A read (verbatim) | A x | B verdict | B x | B score |
|---|---|---|---|---|---|
| …5400551178000 | `\| Qortrola30 =~ Ant` | 0.20 | OTHER_ROW (roster) | 0.92 | 0.534 |
| …6241933226900 | `Qortrola30 "Tt` | 0.16 | OWN_DEATH (feed) | 0.55 | 0.519 |
| …6326328232800 | `\| Qortrola30 —r~~ =` | 0.16 | OTHER_ROW (roster) | 0.21 | 0.629 |

Pre-adjudication (textual — see caveat below):
1. **A and B are reading DIFFERENT ROWS of the same frame.** B reports its best-scoring row anywhere in the
   panel; the killfeed holds several rows at once and the squad roster is always present. In all 3 cases B's
   location is far from A's read (Δx 0.05–0.72) and B's score is sub-floor (< 0.66) — B never scored A's row.
2. The exact handle `Qortrola30` appears **verbatim** in every A text, flanked by kill-row garnish (leading
   `|` row edge, victim-name fragment `Ant…`). A Tesseract hallucination producing the exact 10-char handle
   is a far lower-likelihood event than a genuine row B lacked an anchor for.
3. A `CONFLICT_*` category therefore over-triggers on multi-row frames: it flags *which-row* disagreement,
   not *read-content* contradiction. A true false-read control would require B to contradict A **at A's
   location**.

**Caveat — evidence evicted:** `retina_kf_crops` is a bounded rolling buffer; the 3 crops were evicted
before visual adjudication. The argument above is textual, not settled. Mitigations: (a) the three
2026-07-04 runs cover the SAME eras from **permanent** archive dirs, so any real false-read mode re-surfaces
with preserved evidence; (b) tooling follow-up F-G1P-1 (below).

### Archive runs (2026-07-04) — 5 candidates surfaced at ~766/1800 crops, ALL ADJUDICATED TRUE READS

This time the crops persist (permanent archive dirs) and the conflicts were adjudicated VISUALLY
(3× feed-region zooms preserved in `audits/g1prime_evidence_2026_07_04/`):

| # | Crop | A read | Visual adjudication |
|---|---|---|---|
| c1 | sess_ab `…892267151100` | `- Qortrola30 cme` @0.16 | **TRUE** — `Qortrola30 →(weapon) xX_Kabaligan…` kill row, below `Master MO 83 → Payne-red80` |
| c2 | sess_ab `…898575213200` | same | **TRUE** — same feed 6 s later (row persistence) |
| c3 | sess_ab `…139233250619100` | `Qortrola30 �` @0.16 | **TRUE** — 3 rows coexist: `Qortrola30 → [VON]Manla` (own kill) AND `User17783651 → Qortrola30` (own death) |
| c4 | sess_hid `…174855994519600` | `\| Qortrola30 �Tey` @0.16 | **TRUE** — `Qortrola30 → grettontMoose`, 3rd feed row |
| c5 | sess_hid `…175000974448300` | `[�Qortrola30` @0.16 | **TRUE** — `Qortrola30 → 3x_perfectvelez…`; B's OWN_DEATH was a mis-slot at x=0.44 |

Every candidate false read on the archive is Instrument-B blindness or mis-slot (B x-frac 0.21–0.44 vs
A's 0.16; B killer scores all sub-floor 0.53–0.65), never an A hallucination — the same different-row
signature the prior run's 3 evicted candidates carried textually. c3 directly demonstrates the multi-row
coexistence mechanism (kill + death rows simultaneously in feed). This empirically validates the F-G1P-2
location-gate refinement: all 5 would classify `A_KILL_B_ELSEWHERE` under it.

### FINAL per-session results (all 1,800 archive crops; sess_hid deduped 619→600, 19 double-resume
### duplicates ALL identically labeled — a free determinism confirmation)

| Session | A OWN_KILL | A UNRESOLVED (rate) | B OWN_KILL | B_KILL_A_MISS | AGREE | Conflicts |
|---|---|---|---|---|---|---|
| seg3 (600) | 5 | 595 (99.2%) | 185 | 181 | 130 | 1 — TRUE (c6) |
| sess_ab (600) | 134 | 466 (77.7%) | 228 | 98 | 191 | 4 — TRUE (c1,c2,c3,c7) |
| sess_hid (600) | 100 | 500 (83.3%) | 190 | 92 | 205 | 2 — TRUE (c4,c5) |
| **Total (1,800)** | **239** | **1,561** | **603** | **371** | **526** | **7 — ALL TRUE** |

Two late-run additions to the adjudication table (evidence in `audits/g1prime_evidence_2026_07_04/`):
- **c6** seg3 `…901039467778500`: `cd Qortrola30 == Wr` → visual: `Qortrola30 (teal) → Wryx_9thion`, third
  feed row below two `lheartzhlio → yolanda` rows. TRUE.
- **c7** sess_ab `…139577336648000`: `-Qortrola30 7` → the first zoom (y<0.35) showed only a MOST WANTED
  banner; a deeper zoom (y<0.55) revealed the genuine `Qortrola30 → <victim>` row at the y≈0.42 seam above
  two Disconnected rows. TRUE — and a caution for future adjudication: always zoom the FULL y-gate range.

**Multi-row lower bound (per the SCOPE NOTE):** 1 crop of 1,800 with A=OWN_KILL ∩ B=OWN_DEATH (c5). True
multi-row rate is higher (same-verdict multi-row crops invisible to this proxy; c3 and c6 are visually
multi-row but same-proxy-blind).

**Per-rendering recall (honest read):** A's recall varies enormously by rendering — seg3 5 vs sess_ab 134
vs sess_hid 100 against B's 185/228/190 (B armed with 17 R4 anchors, i.e., post-hoc rendering-specific
coverage A doesn't get). A is the rendering-independent COLD-START catch instrument, not the recall
instrument; that division of labor is the design. seg3's A-UNRESOLVED 99.2% is the standing drift-alarm
ceiling for a rendering Tesseract reads poorly.

## VERDICT FOR HOLD 1

**ZERO false own-handle reads across 2,411 crops (611 prior + 1,800 archive). All 7 archive conflict
candidates visually adjudicated TRUE READS with preserved evidence; the 3 prior (2026-07-03) candidates
remain textually-argued only (crops evicted — F-G1P-1) but carry the same different-row signature the 7
adjudicated ones proved.** Subject to the multi-row SCOPE NOTE (crop granularity; claim covers A's
positives being genuine).

**Engine-attribution confirmation (re the `python3.13.exe` gotcha):** the gotcha was a MONITORING-filter
artifact only (`Name='python.exe'` CIM queries miss the Store interpreter's `python3.13.exe` image name);
process creation always used the single explicit shim path, so one interpreter ran all workers. Engine
selection is env-gated (`RETINA_OCR_ENGINE`), verified unset at user/machine/process scope before every
launch and inherited by workers — the v6 chain cannot load without it. Every Instrument-A read in every
JSONL in this report is `tesseract_row_v1`. No cross-engine misattribution is possible in this data.

## SCOPE NOTE — verdicts are per-CROP, rows are the underlying population (multi-row undercount)

c3 exposed a structural fact about the measurement, not just one conflict: a single crop can legitimately
contain BOTH an own-kill row and an own-death row (the feed holds ~3-4 rows at once), and the taxonomy has
no both-verdict category — each instrument emits ONE verdict per crop by construction. Consequences for how
the final table must be read:

1. **All per-class counts and UNRESOLVED rates in this report are CROP-level** — the denominator is crops,
   not rows. A crop labeled OWN_KILL may also contain an unreported death row and vice versa; multi-row
   crops are systematically single-counted.
2. **Measurable lower bound:** crops where A=OWN_KILL and B=OWN_DEATH are definite multi-row crops (both
   signals independently real) — computed from the final JSONLs in the results section. The true multi-row
   rate is higher (same-verdict multi-row crops are invisible to this proxy).
3. **The zero-false-read bar is UNAFFECTED** — it is a claim about A's positive reads being genuine (each
   adjudicated read is a real row regardless of what else shares the crop), not about class-count
   completeness.
4. **Lane v2 item:** per-ROW taxonomy (enumerate rows per crop, verdict each) if row-level denominators
   ever become load-bearing — e.g., for recall-per-kill arithmetic, which currently inherits the crop-level
   approximation.

## Recall / miss characterization

`B_KILL_A_MISS` (B scored ≥0.66 with an anchor, A abstained): seg3 181 / sess_ab 98 / sess_hid 92 = 371
total. These are A recall gaps, expected by design — B carries 17 R4 session anchors (rendering-specific,
cut AFTER a session's first catch), so B's recall ceiling is structurally higher wherever R4 coverage
exists. Per-session B-coverage annotations (which anchors carried B's OWN_KILLs) are in each
`audits/g1prime_*_2026_07_04.report.md`. A's abstentions are clean (no plausible-misread acceptance
surfaced: every A positive contains the verbatim handle).

## UNRESOLVED rate (standing drift alarm) — baselines now set per rendering

A: seg3 **99.2%** / sess_ab **77.7%** / sess_hid **83.3%** (prior mixed-era 611-crop: 94.3%).
B: seg3 21.0% / sess_ab ~10% / sess_hid ~18%. Pre-registered as the rendering-drift alarm: a future UI
patch or rendering variant spikes the A rate above its per-rendering baseline BEFORE recall silently
collapses.

## Findings

- **F-G1P-1 (tooling):** the audit lane's contact sheet references crops by filename in a rolling buffer;
  conflict evidence can be evicted before operator adjudication (happened to all 3 prior candidates).
  Fix queued: `_write_contact_sheet` copies conflict + sample-UNRESOLVED crops into `<out>.evidence/` at
  report time. (Deferred until the in-flight runs finish — no mid-run module edits.)
- **F-G1P-2 (taxonomy):** `CONFLICT_A_KILL_B_*` conflates different-row disagreement with read-content
  contradiction. Candidate refinement: require B's locating x_frac within a slot-width of A's x_frac to call
  it a CONFLICT; else emit `A_KILL_B_ELSEWHERE` (B-blindness class). Operator decision at HOLD 1 — now
  empirically supported: all 5 archive candidates were exactly this class.
- **F-CG-1 (live wiring, from the 2026-07-04 corpus-growth session) → escalated to D-CG-1 below.** The
  session-anchor cut a candidate at 13:20 (`static_feed_v1`, sha `f973615d`) and sat in CANDIDATE for the
  remaining ~35 min — never promoted, never stall-demoted — so 6 inline AUTHORED classifications produced
  ZERO composite AUTHORED and KAS honestly issued `INSUFFICIENT_KILLS`.

## D-CG-1 — CANDIDATE escape-hatch signal (SEPARATE decision, NOT part of the precision verdict)

Two different questions must not be adjudicated in the same breath: HOLD 1 asks *are the archived reads
real*; D-CG-1 asks *is the promotion machinery using the right signal*. This block is the latter.

**Precise seam (one layer finer than the first write-up):** promotion itself (K=3 consistency) gates on the
CANDIDATE ANCHOR'S OWN killer-slot score ≥0.66 — a good cut promotes fine in BR (proven live: gated-cut
match 4, PROMOTED in 19 s). What gates on `feed_v1 raw ≥0.66` is the ESCAPE HATCH: `observe_candidate`'s
stall counter only increments when the caller passes `raw_killer_authored=True`, currently derived from
feed_v1's raw verdict on the same crop. A WEAK cut in BR is therefore doubly stuck: (a) its own sub-floor
scores never accumulate K, and (b) the demote trigger never fires because feed_v1 raw is precisely the
marginal signal in this rendering. The original marginality bug, resurfaced at the weak-cut escape hatch —
NOT at the catch (OCR fixed that) and NOT at the promotion bar (candidate-self-scoring is rendering-local).

**Candidate fix direction:** let the rendering-independent signals — an OCR killer-slot read and/or the
inline AUTHORED verdict — ALSO count as `raw_killer_authored` in CANDIDATE regime, so witnessed misses
accumulate and weak cuts demote-and-recut instead of starving the match.

**IMPLEMENTED 2026-07-04 (operator-approved with the FP-check condition kept firm). FP-check RUN, both
halves:**

1. *Structural (mechanical):* `raw_killer_authored` feeds `observe_candidate`'s stall counter and NOTHING
   else — it never increments `_consistent`, never folds AUTHORED, never touches R3's fp-fire path. The
   only reachable outcome from witness pressure is `candidate_demoted_stall` → BOOTSTRAP (self-healing
   recut). Pinned by `bridge/tests/test_dcg1_ocr_stall_witness.py`: the BR starvation scenario now demotes;
   an endless witness stream never promotes/authors; abstains never stall; the three cost gates
   (fresh-row ∧ sub-floor ∧ flag-ON) verified by call-counting. A false/spliced witness is an availability
   nuisance (recut), never an integrity break — and the read itself measured 0 FP / 2,411 crops (G1').
2. *Empirical (corpus-growth archive replay, real Tesseract, OCR-OFF vs ON at stride 1/8/16):*
   `fp_fires=0` and `demotions=0` in every leg — no spurious demote, no R3 interaction, no regression.
   OCR-ON strictly improves bootstrap (dense: catch crop 16 vs 55, promote 19 vs 59, recall 48 vs 40,
   kills-before-promotion 0 vs 1). HONEST LIMIT: the live starvation shape did NOT reproduce offline —
   replay's crop stream hands the gated cut better frames than the live classify-timing did, so the
   demote-under-starvation transition is pinned synthetically (real fold + real state machine, scripted
   scores), not on this archive. Its live validation is the next corpus session: a weak cut, if it recurs,
   now demotes within `stall_limit` witnessed misses instead of starving the match.

## Related, completed alongside

- **C1 for Tesseract (narrow) — a TWO-LAYER finding, not a clean pass:**
  `bridge/tests/test_c1_freeze_frame_transition.py`, real `_killer_fresh_row`. Layer 1 (the exposure): a
  single-frame freeze TRANSITION legitimately reads as "fresh" (the detector sees the transition edge
  itself) and CAN seed a CANDIDATE — real, structural, pinned honestly. Layer 2 (the containment): what
  prevents AUTHORED is the **demote-on-persist timer** (`_SESSION_ANCHOR_ROW_PERSIST_MS` = 5 s) flipping
  the frozen content to background so the candidate self-fires → R3 demote. **The security guarantee rests
  on the persist window, NOT on fresh-row differencing alone.**

## PATTERN — "just a timing parameter" keeps turning out load-bearing for security (3rd instance)

1. **R2 window width** (50,5000 ms): widened for a classify-cadence bug → became the dominant splice-FAR
   term (`docs/composite-splice-far-2026-07-01.md`).
2. **Escape-hatch witness signal** (`raw_killer_authored` ← feed_v1 raw ≥0.66): chosen as the available
   signal → became the BR stall deadlock (D-CG-1).
3. **Demote-persist duration** (5 s): set as row-persistence tuning → is now the actual freeze-frame
   containment boundary (C1).

Standing rule going forward: any operational parameter on the killer-slot/AUTHORED path gets a security
review by default at introduction — not as an afterthought when it surfaces in a finding.

---

## ADDENDUM 2026-07-05 — WZ live-match sessions (v6 engine era)

Everything above this line was measured with `RETINA_OCR_ENGINE=tesseract` (the pre-flip legacy chain).
This addendum runs the same audit lane, unmodified, over the two most recent WZ live-match captures using
the **current default engine chain** (`rapidocr_ppocrv6_small` primary → `tesseract_row_v1` fallback, per
the D-PKG-1 flip). Every Instrument-A record in this addendum shows `"engine": "rapidocr_ppocrv6_small"`.

### What was measured

| Session | Crops audited | Coverage | Note |
|---|---|---|---|
| `u2c_wz_20260704_1783212934` / `u2c2_wz_20260704_1783214824` | 324 | 54% of 600 | **byte-identical duplicate archive — see finding below, counted once** |
| `u2c3_wz_20260704_1783220750` (18 real kills, 0 KAS authored live) | 356 | 59% of 600 | the production-failure session |

Coverage is partial (audit-lane throughput was contention-bound by other CPU load on the machine —
`RemotePlay.exe` and this Claude session itself — during this run; operator chose a faster partial sample
over a ~3-hour full run). Both sessions clear >50% coverage, which is enough to hold the zero-false-read
gate and to name the match3 mechanism below. Remaining crops can be added later via the lane's `--resume`
flag without re-processing what's here.

### Finding — `u2c_wz` and `u2c2_wz` are one duplicated capture, not two independent matches

The two archive directories are byte-identical: same 600 filenames, and MD5 hashes match at every spot
checked (1st, 150th, 300th, 450th, 600th file in sorted order). This is one underlying capture archived
twice under two session names, not two independent matches. Reported once below rather than double-counted
— counting it twice would have inflated the crop total and overstated how independently-replicated the
zero-conflict result is.

### Zero-false-read bar — HELD, no adjudication needed

| Session | A OWN_KILL | A UNRESOLVED | B: OWN_KILL/OWN_DEATH/OTHER_ROW/UNRESOLVED | Candidate false reads |
|---|---|---|---|---|
| WZ match (deduped) | 15 | 309 | 89 / 101 / 71 / 63 | **0** |
| WZ match3 | 50 | 306 | 86 / 63 / 114 / 93 | **0** |

Disagreement categories present: `B_KILL_A_MISS` (A recall gap, expected), `A_KILL_B_ELSEWHERE` (11 total,
geometry-gated different-row disagreements — spot-checked all 11, every one has B's `y_frac` clearly in a
different region: roster `y≈0.55–0.94` vs A's feed-row `y≈0.30–0.37`, or a distinct feed row), and
`A_KILL_B_GAP` (2, match3 only — see below). **Zero `CONFLICT_A_KILL_B_ROSTER`/`_B_DEATH` candidates in
either session** — the bar held cleanly on the newest captures without requiring any visual adjudication.

### Match3 — the production-failure session — has the smoking-gun evidence for the OCR fix

`u2c3_wz_20260704_1783220750` is the session with 18 real kills / 0 KAS-authored in production, root-caused
to `inline_bg_max: 0.6491` sitting just under Instrument B's 0.66 authored floor. Two crops in this audit
(`panel_1783220807349308700.png`, `panel_1783220807812093700.png`) land in `A_KILL_B_GAP`:

- **Instrument A**: reads `'Qortrola30'` cleanly at `x_frac=0.1596` (killer slot) via
  `rapidocr_ppocrv6_small` — clean OWN_KILL.
- **Instrument B**: `UNRESOLVED`, `killer_score=0.649` — matches the known production `inline_bg_max
  0.6491` almost exactly. This is very likely the same kill row that stalled the live pipeline.

This is direct empirical confirmation of this plan's central thesis: on this session's rendering, the
color-based bootstrap (B / `feed_v1`) is marginal and stuck sub-floor, while the spelling-based OCR
bootstrap (A) reads it cleanly. This is exactly the case the OCR-first bootstrap ordering in Phase W is
designed to fix — now demonstrated on the actual session that failed live, not just in the abstract.

### Combined verdict — all eras, HOLD 1

**Zero false own-handle reads across every session audited to date: 3,091 crops across 5 distinct sessions
(2,411 tesseract-era + 680 v6-era).** All 7 candidate false reads found (tesseract-era only) were adjudicated
TRUE OWN_KILL — Instrument-B blindness on an off-fit anchor, never an Instrument-A hallucination. Zero
candidates surfaced in the v6-era WZ sessions at all. Match3's `A_KILL_B_GAP` finding independently confirms
the OCR-bootstrap-fix thesis against the session that actually failed in production.

**Recommend:** proceed past HOLD 1 into Phase W wiring (OCR bootstrap into `_session_anchor_fold`), subject
to operator go-ahead and HOLD 2 (G0 — B2 premise check, already resolved NEEDS-CAPTURE; fork between an
instrumented capture segment and dense-tail-now is an open operator decision, not a blocker on HOLD 1).
