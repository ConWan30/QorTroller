# Recognition-engine bake-off — PP-OCRv5 (SVTR-class) vs Tesseract (2026-07-03)

**STATUS: PRE-REGISTRATION FROZEN (Phase 1). Scoring (Phase 2) has NOT run at freeze time.**
Archive-only, zero live-path footprint. Post-Increment-2 gap (L4 conjunction plan CLOSED `32dfa29d`).
This document's header (hypothesis, frozen pipelines, frozen thresholds, bars B1-B8) is written BEFORE any
evaluation-corpus scoring; the results sections below the freeze line are appended in Phase 2 without editing
anything above it.

## Hypothesis (falsifiable)

An off-the-shelf scene-text recognition head (PP-OCRv5_mobile_rec, SVTR-class) beats the incumbent
Tesseract row-reader on recall-per-rendering at equal-or-better precision, and exposes per-char confidence
the Tesseract path does not — the structural closure named in the A3 adjudication for canon() glyph-confusion
(o/0, i/l/1, case).

## Security standing (why this is not only a recall question)

OCR sits in a certificate evidence chain: `--kas` issuance rests partly on what the OCR bootstrap read (the
session anchor's provenance). So the engine question is a question about what a QORTROLLER-KAS-v0 commitment
stands on. Two consequences are pre-registered as first-class bars, not footnotes: the A3-closure probe (B7)
and the splice-read threat-model delta (B8).

## Frozen pipelines (recognition is the ONLY variable)

Both engines consume the SAME localization → crop → upscale → binarize path and pass through the SAME
`canon()` fuzzy-match + substring-extension boundary check (the A3 fix) + killer-slot x-frac gate. Only the
recognizer differs. Same abstain law: below the frozen confidence cutoff → UNRESOLVED, never a guess.

- **Incumbent — `tesseract_row_v1`:** pytesseract psm 7, upscale 4×, Otsu, both polarities, canon() vs
  `q0rtr01a30`. (The shipped `killfeed_ocr_bootstrap.tight_row_ocr` recipe.)
- **Challenger — `paddle_svtr_v1`:** `paddleocr 3.7.0` `TextRecognition(model_name="PP-OCRv5_mobile_rec")`
  on `paddlepaddle 3.3.1`, isolated venv `C:\Users\Contr\vbko` (repo untouched, no requirements.txt change),
  same upscale/crop, `rec_text` → the SAME canon()+boundary+slot gates.

**Model-selection provenance (R1 — keeps the deviation clean):** paddleocr 3.7 defaults to
PP-OCRv6_medium_rec (rejected: warm median 4823 ms, 19× the ≤250 ms budget) and offers en_PP-OCRv4_mobile_rec
(366 ms, over budget). PP-OCRv5_mobile_rec was selected on **B5 latency grounds ALONE (246 ms median,
under budget), against the pre-registered budget, BEFORE any B1/B2 accuracy measurement on the evaluation
corpus, and using a probe crop that is NOT part of the scored archive.** No accuracy signal from the
evaluation corpus informed model choice — the selection cannot contaminate the accuracy bars.

## Frozen thresholds

Each engine's confidence cutoff is tuned on a declared held-out slice — the FIRST 60 crops of the b2trace
ring tail (chronological) — then frozen, then everything is scored once. Tesseract: retains its shipped
canon-match discipline (no numeric conf cutoff; a full canon match is the accept). Paddle: `rec_score` cutoff
frozen from the held-out slice (recorded in Phase 2 before the full pass). A post-hoc defect → a NEW
documented pass, never silent re-tuning.

## Evaluation corpora (with pre-registered scope + denominator honesty)

| corpus | crops | role |
|---|---|---|
| b2trace ring tail | (of 600 ring) | POSITIVES — kills known from composite-AUTHORED; **denominator = rows present in archive** (R2) |
| seg3 archive (Jul 1) | 600 | POSITIVES — third rendering family, kills from the offline-59 work |
| a1spectate (in ring) | (of 600 ring) | HARD NEGATIVE — spectate-spam; own handle never killer-slot |
| splice archive | 600 | HARD NEGATIVE — recapture-degraded; Tesseract baseline 0/40 on sample |
| R4 anchors | 14 | Instrument-B coverage annotation for B6 |

**B2 scope (R2 — pre-registered so the conclusion cannot be quoted broader than its corpus):** the dense ring
is a 600-crop ROLLING buffer; the g3mp / g3wz2 / g3br_recut / g3br_gatedcut crops were overwritten by later
sessions. B2's claim is therefore **"2-3 rendering families as archived" (b2trace tail + seg3 [+ MP only if
any MP rows survive in-ring]), NOT "per-rendering across 5 matches."** **Recall denominator rule:** recall is
computed against kill rows **present in the archive**, and each match reports its **present/total ratio**
(e.g. b2trace present-in-ring / 10 composite-AUTHORED) so partial crop survival reads as a stated scope, never
as a silent recall understatement.

## Bars (frozen)

- **B1 — zero false own-handle reads, archive-wide, per engine (HARD GATE).** Includes the adversarial
  corpora: a false read on a spectate or splice crop is a certificate-chain finding, weighted as such.
- **B2 — recall with canon(), per rendering/match** (scope + denominator per R2 above), + first-kill catch
  arithmetic `P(catch by kill n) = 1 - (1-r)^n` at measured recall r.
- **B3 — miss characterization:** clean-abstain vs plausible-misread; misread content; whether fuzzy-match
  would wrongly accept any.
- **B4 — UNRESOLVED rate per match/rendering** (drift-alarm continuity with the audit lane).
- **B5 — per-row latency distribution** vs the ≤250 ms/row budget (v5_mobile pre-cleared at 246 ms median).
- **B6 — disagreement table vs both existing instruments** (ocr_row_v1 + template_ensemble_v1), with the
  Instrument-B R4-anchor-coverage annotation so template-gap disagreements aren't misread as findings.
- **B7 — per-char confidence capability (A3-closure probe).** Does v5_mobile expose per-char confidences, and
  do they separate the documented confusion pairs (o/0, i/l/1, case) on real rows, scored against the six
  A3 boundary collisions? **Pre-registered branch (R4):** if the API surfaces NO char-level output,
  B7 resolves as **"sequence-confidence only — capability ABSENT"** — a valid finding that WEAKENS the
  off-the-shelf A3-closure case and correspondingly STRENGTHENS the `rec_wz_v1` fine-tune path (inherent CTC
  per-char confidence), routed to Phase 4's design section, NOT a gap discovered mid-scoring.
- **B8 — splice-read threat-model delta (explicit, framing fixed in advance).** Paddle's read rate on the
  same 40-crop splice sample Tesseract scored 0/40, and on the full 600-crop splice archive. **Framing
  (pre-registered verbatim):** "recapture degradation is demoted from defense layer to non-defense for this
  engine; the R2 window gates remain the structural defense; the composite-splice-FAR and A2 results are NOT
  invalidated but their degradation-dependent margin narrows." If Paddle reads splice rows, D-ENGINE-1's
  adoption criteria must weigh that the OCR bootstrap becomes reachable by higher-fidelity injection;
  mitigation options (bootstrap fresh-row differencing already required; add cut-time freshness attestation
  to the KAS evidence trail) are named design-only. **The Phase-0 probe read `Tre5ivex_notChloe` @ 0.90 from
  a spectate-era band — content Tesseract never surfaces — is the B8 threat-surface in miniature (recall and
  attack surface are the same coin); this observation belongs to B8, not the recall narrative.**

## D-ENGINE-1 (operator resolves at HOLD 2, criteria frozen here)

- **(a) ADOPT paddle_svtr_v1** — iff B1 zero-false held (adversarial corpora included) AND B2 ≥ Tesseract on
  every archived rendering (or strictly better pooled with no rendering regression) AND B5 within budget AND
  B8's threat-model delta explicitly accepted with named mitigations scoped. Wiring is a LATER increment
  behind the shared-engine contract (all three consumers green; provenance → paddle_svtr_v1; Tesseract →
  fallback; KAS evidence trail gains raw pre-canon read + exact|fuzzy + per-char-confidence fields).
- **(b) RETAIN tesseract_row_v1** — Paddle failed a bar, won marginally, or B8's delta is unacceptable at
  current mitigation cost. Evidence banks; the labeled corpus feeds rec_wz_v1 regardless.
- **(c) BLOCKED-ON-ENVIRONMENT** — banked with exact failure. (Not this run: environment VIABLE.)

---
<!-- ===== FREEZE LINE — nothing above this line is edited after Phase 1. Phase 2 appends below. ===== -->

## Phase 2 — Results (appended post-freeze; the header above is UNEDITED)

Process isolation (REQUIRED, discovered mid-run): loading paddlepaddle in-process breaks pytesseract (8/8
False on a crop the shipped reader reads True). Each engine ran in its own process — tesseract in the clean
repo env, paddle in the isolated vbko venv — writing separate JSONLs joined by (corpus, crop). A startup
self-check aborts the tesseract pass if it can't read a known crop (this failure mode bit twice: paddle
contamination + missing tesseract_cmd). Frozen paddle cutoff 0.50 (held-out first-60 b2trace: 13 handle-reads,
min score 0.857 — cutoff well below, recall-preserving). Raw: audits/rbo_{tesseract,paddle}_2026-07-03_r2.jsonl.

| bar | tesseract_row_v1 | paddle_svtr_v1 |
|-----|------------------|----------------|
| B2 recall b2trace (crop) | 8 / 91 located | **18 / 91** |
| B2 recall b2trace (kill-event, R2 denom present=5/10) | caught 3/5 | **caught 4/5** |
| B2 recall seg3 (Jul-1 rendering) | 6 / 267 located | **8 / 267** (no regression) |
| B5 latency median / p95 | 2540 / 4075 ms | **122 / 232 ms** (≤250 budget) |
| B1 false reads a1spectate | 0 | 0 (the 1 paddle read is a GENUINE own-kill row, eyeballed) |
| B1 false reads splice | 0 (0/579 FINAL — completely blind; 0/40 prior) | 0 (the 80 reads are GENUINE recaptured own-kills) |
| B7 per-char confidence | n/a | **ABSENT** — keys rec_text/rec_score only |
| B8 splice-read count | 0 / 579 (blind — degraded glyphs) | **80 / 600** |

- **B1 (hard gate) HELD for BOTH.** Neither engine hallucinates the handle where absent. Every extra Paddle
  read is a CORRECT read of a genuinely-present own-handle killer-slot row (adjudicated by eye:
  `Qortrola30 -> mamahefen1234` on a1spectate; `Qortrola30 -> 1Crazydog` on splice). Paddle out-reads
  Tesseract; it does not out-false-read it.
- **B3/B6:** Paddle's read set is a SUPERSET of Tesseract's (every disagreement is "Paddle reads, Tesseract
  clean-abstains" — a recall gap, never a conflicting read). No fuzzy-accept of a wrong string by either.
- **B4:** UNRESOLVED high on non-kill crops for both (expected); lower for Paddle where it reads more.
- **B7 (R4 branch taken):** capability ABSENT — v5_mobile exposes sequence confidence only. Off-the-shelf
  adoption does NOT close the A3 glyph-confusion boundary; that closure routes to rec_wz_v1 (Phase 4.1).
- **B8 (framing per freeze, verbatim):** "recapture degradation is demoted from defense layer to non-defense
  for this engine; the R2 window gates remain the structural defense; the composite-splice-FAR and A2 results
  are NOT invalidated but their degradation-dependent margin narrows." The Phase-0 spectate probe
  (`Tre5ivex_notChloe`@0.90) and the 80 splice reads are the same coin as the recall win.

## Phase 3 — D-ENGINE-1: (a) ADOPT paddle_svtr_v1 [RESOLVED — operator accepted B8, 2026-07-03]

Three of the four frozen (a)-criteria objectively MET: B1 zero-false held (both) · B2 >= Tesseract on EVERY
archived rendering with no regression (b2trace 18>8 & 4>3 windows; seg3 8>6) · B5 within budget (122ms). The
fourth — explicit acceptance of the B8 splice-read threat delta — is **ACCEPTED by the operator** on the
recorded basis that the STRUCTURAL splice defense was never Tesseract's blindness but the R2 window gate +
fresh-row differencing (G4 A2 held on those; blindness was an accidental bonus layer), with two mitigations
tracked: (1) bootstrap fresh-row differencing already required; (2) ADD cut-time freshness attestation to the
KAS evidence trail so a non-fresh (spliced) row cannot seed a certificate. Adoption is "Paddle as the recall
engine"; the A3 glyph-confusion closure remains on rec_wz_v1 (B7 absent).

**Wiring is a LATER increment (NOT this commit), behind the shared-engine contract:** all three consumers
(live bootstrap + audit lane + KAS issuance) green; provenance flips to paddle_svtr_v1; tesseract_row_v1
demotes to fallback in the chain; the KAS evidence trail gains raw pre-canon read + exact|fuzzy + (when a
per-char engine exists) confidence fields. Dependency: paddle install is Windows-long-path-sensitive
(needs a short venv root) — a packaging decision for the wiring increment (bundled model vs ONNX export).

## Phase 4 — Design-only forward scope (NO build in this increment)

1. **rec_wz_v1 (the A3 closure the bake-off could NOT deliver off-the-shelf):** fine-tune an SVTR/CTC head on
   a synthetic feed-font renderer + the audit lane's accumulating labeled rows; inherent per-char CTC
   confidence separates the o/0, i/l/1, case confusion pairs canon() collides. These frozen B1-B8 bars become
   its promotion gate. Engine chain: rec_wz_v1 -> paddle_svtr_v1 -> tesseract_row_v1 -> human_oracle, one
   contract. B7's absent-capability finding is precisely why this path is load-bearing, not optional.
2. **Retina fusion consumers:** full-row parse (killer, victim, weapon) -> attribution graph on the ROI
   clock; multi-kill temporal compounding; others' rows as free negatives. Recognition NEVER triggers — it
   reads what input-gated windows captured; R2^B2 + KAS structural gating stay upstream.
3. **WMP interop:** labeled-row corpus as a provenance-anchored data product via the existing CORPUS-SNAPSHOT
   family (no new domain tag, no ceremony); labeler + anchor SHAs per record; W1-D consent before any
   external byte; LISTING/Curator the deferred downstream lane.
4. **Boundary line (stated):** recognition output never enters a verdict path without the live-input
   conjunction, never enters the cert path beyond the bootstrap-provenance role it already holds while
   D-CERT-5 is open, and never weakens the anti-cheat core — every consumer is downstream of verified capture.
5. **QUEUED ONE-LINE FIX (R3, second archive-loss now):** archive the dense ring at daemon `stop` before the
   next session overwrites it — the rolling ring cost the g3mp/g3wz2/recut/gatedcut renderings (why B2 is
   "2-3 families as archived"). Lands before the next capture, or a third rendering family is lost too.

## Live-path confirmation

NO live-path change in this increment. The shipped `killfeed_ocr_bootstrap` / audit lane / KAS issuance are
byte-unchanged; the bake-off is scoring scripts + evidence only. Paddle lives ONLY in the isolated vbko venv.

## D-PKG-1(b′) parity re-check — PRE-REGISTRATION (frozen before scoring, 2026-07-03)

D-PKG-1(b) via paddle2onnx export is BLOCKED on this rig (onnx no-3.13-wheel; paddle2onnx C++ DLL/ABI
mismatch vs paddlepaddle 3.3.1 — version-pin spiral declined per the no-workaround rail). (b′)
rapidocr-onnxruntime is the clean ONNX+onnxruntime realization (64ms, bridge-native 3.13, NO paddlepaddle so
Tesseract-fallback stays uncontaminated) BUT bundles `ch_PP-OCRv3_rec_infer.onnx` (sha 897a3ededb38fee0) — 2
generations older than the D-ENGINE-1-validated PP-OCRv5_mobile_rec. A different rec head has a different
recall AND hallucination AND splice-read profile; NONE transfer from the bake-off. So (b′) is NOT adoptable
until rapidocr's model reproduces the frozen bake-off numbers on the SAME corpora.

**Parity = PASS iff ALL of (frozen NOW, before scoring):**
- **B2 recall ≥ v5_mobile on EVERY rendering, no regression:** b2trace ≥ 18/91 crop AND ≥ 4/5 kill-events;
  seg3 ≥ 8/267. A regression on any rendering = FAIL.
- **B1 zero-false HELD on BOTH negatives:** no HALLUCINATED handle read on a1spectate or splice (genuine
  own-kill rows present in the capture don't count — same adjudication rule as the bake-off).
- **B5 ≤ 250ms/row:** (64ms already clears; re-confirmed on the corpus).
- **B8 splice-read count MEASURED (property, not pass/fail):** rapidocr-v3's reads on the 600-crop splice vs
  v5_mobile's 80/600 — fewer = smaller C1 attack surface, more = harder C1. Reported, not gated.

PASS -> (b′) adopted (strictly better than (c): faster, no subprocess, no permanent paddle env). FAIL any bar
-> (c) sidecar with the EXACT v5_mobile model (managed-subprocess cost = the price of not re-opening
D-ENGINE-1). Provenance: whichever wins, the C3 engine id records the ACTUAL live model
(rapidocr_ppocrv3 sha 897a3ede... | paddle_svtr_v1/v5_mobile) + SHA — model identity is provenance.

## D-PKG-1 RESOLVED (2026-07-03): PP-OCRv6_rec_small via rapidocr/onnxruntime — parity PASS

The (b) paddle2onnx export being blocked forced a hunt for a pre-exported ONNX; it found something BETTER than
the target: the newer `rapidocr` package bundles **PP-OCRv6_rec_small.onnx** (sha 6f327246b50388f3) — NEWER than the
D-ENGINE-1-validated v5_mobile — running on onnxruntime (bridge-native 3.13, NO paddlepaddle, so the Tesseract
fallback stays uncontaminated; NO subprocess). Parity re-check (frozen threshold above) vs the v5 numbers:

| bar | v5_mobile (validated) | PP-OCRv6_rec_small |
|-----|-----------------------|--------------------|
| B2 b2trace (crop) | 18/91 | **28/91** (+55%, no regression) |
| B2 b2trace (kill-event) | 4/5 | **5/5** (catches all present) |
| B2 seg3 | 8/267 | **13/267** (+62%) |
| B5 latency median | 122 ms | **21 ms** (6× faster) |
| B1 a1spectate false reads | 0 (1 genuine) | **0** (2 reads, BOTH adjudicated GENUINE own-kill rows by eye) |
| B8 splice-read surface | 80/600 | **80/600** (IDENTICAL — C1 stakes unchanged) |

PARITY = **PASS on every pre-registered bar** (B2 no-regression — in fact improved on every rendering; B1
zero-hallucination held on both negatives; B5 within budget). B8 identical (same 80 recaptured own-kill rows;
same C1 gate stakes). **DECISION: adopt PP-OCRv6_rec_small** — strictly better than both v5-sidecar (faster,
newer, no subprocess, no permanent paddle env, no fallback contamination) and rapidocr-v3 (which regressed,
dropping the leading Q). Bridge deps: `rapidocr` + `onnxruntime` (both pip, 3.13-native, no paddle). C3
engine id = `rapidocr_ppocrv6_small` + sha 6f327246b50388f3. The paddle2onnx-export spiral declined was the right call —
the pre-exported v6 ONNX is cleaner than anything that toolchain would have produced.

## C1 gate result (2026-07-03) — GREEN, with the honest fresh-row finding

The wired producer (v6 live, RETINA_OCR_ENGINE=rapidocr_v6 + OCR bootstrap) replayed the 600-crop splice
corpus. **KAS verdict INSUFFICIENT_KILLS, 0 authored, 0 promotions -> ZERO adversarial certificates (bar
HELD).** Mechanism, reported explicitly per the pre-registration:
- v6 READS the spliced own-kill rows (B8: 80/600). One coincided with fresh_row=True -> **FRESH-ROW DID NOT
  BLOCK IT.** Recaptured video frames change frame-to-frame, so a spliced row DOES present as "fresh." Fresh-
  row differencing is NOT the splice wall.
- The one bootstrap catch attempt was rejected by the CUT-QUALITY gate (`cut_failed` — the recapture-degraded
  row failed the scale-aware cut's vertical-isolation/width gate). No anchor cut -> no promotion -> no cert.
- **Load-bearing splice defense = cut-quality gate + K=3 promotion, NOT fresh-row.** The R2 window keeps
  classification input-gated throughout.
- **Caveat (standing B8, sharpened):** held on WGC-recapture-degraded splice; the cut-quality rejection leaned
  partly on that degradation. A native-res HDMI-splice (untested) could present a clean row that passes the
  cut gate — thinner margin there. This is where Increment B's freshness-evidence field (D-TRIO-2) matters.

**B8 acceptance was CONDITIONAL-ON-C1** (correcting the earlier "accepted-with-tracked-mitigations" phrasing in
ee9b01b3): C1 GREEN MEETS the condition, so B8 acceptance now stands as measured. Increment A commits;
Increment B (Trio-Retina alignment) proceeds.
