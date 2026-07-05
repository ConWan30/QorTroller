# D-PKG-1 — v6 parity recheck: PASSED, default ADOPTED (2026-07-04)

**Decision:** `engine_chain()` default flipped to **v6 primary (`rapidocr_ppocrv6_small`) + Tesseract
fallback**, per the operator's standing directive ("if v6 is better than tesseract I want to adopt it")
now backed by full-archive evidence. `RETINA_OCR_ENGINE=tesseract` remains the legacy escape hatch.

## Method

`scripts/killfeed_audit_lane.py` (dual-instrument, `--workers 4`, `--resume`) with
`RETINA_OCR_ENGINE=rapidocr_v6` over the SAME 1,800 permanent archive crops as the Tesseract G1' run
(`audits/g1prime_*`), same Instrument B ensemble, same thresholds. Taxonomy version note: the v6 run used
the newer location-gated adjudication (`A_KILL_B_ELSEWHERE` + y_frac + auto evidence-copy); the Tesseract
run predates it — recall comparisons are unaffected; conflict-class counts are not directly comparable
across the two runs.

## Recall (Instrument A OWN_KILL, deduped per session)

| Session | v6 | Tesseract | Δ | A-UNRESOLVED v6 vs Tess |
|---|---|---|---|---|
| seg3 | **13** | 5 | **+160%** | 97.8% vs 99.2% |
| sess_ab | **141** | 134 | +5% | 76.5% vs 77.7% |
| sess_hid | **110** | 100 | +10% | 81.7% vs 83.3% |

seg3 is the decider: the rendering Tesseract was near-blind to (99.2% UNRESOLVED — the pre-registered
drift-alarm ceiling) is exactly where v6's advantage is starkest, as the adoption benchmark predicted.

## Zero-false-read bar — HELD for v6

2 same-row conflict candidates archive-wide (both sess_hid, adjacent frames 0.5 s apart = one persisting
feed). Visually adjudicated **TRUE READS** from the auto-preserved full-gate evidence
(`audits/dpkg1_v6_sess_hid_2026_07_04.evidence/`): the frame holds FOUR feed rows including TWO
simultaneous own-kill rows (`Qortrola30 → …` and `Qortrola30 → sks_bale`); A read the genuine killer-slot
handle; B mis-slotted sub-floor (0.581) on the same row. The F-G1P-2 location gate auto-classified the 9
different-row cases as `A_KILL_B_ELSEWHERE` — only genuine same-row cases reached the contact sheet, and
the F-G1P-1 evidence-copy preserved them without operator intervention. The new tooling's first live use
worked end-to-end.

## Engine attribution — 100% clean

Every one of the **264** v6-run kill reads carries `engine: rapidocr_ppocrv6_small` in its JSONL record —
zero Tesseract-fallback contamination in the aggregates. (Per-record attribution was added to the lane for
exactly this check.)

## B8 splice posture (the accepted risk, re-verified)

v6 CAN read recaptured splice content Tesseract was blind to (known delta, operator-accepted with
mitigations at the bake-off). The wall remains the live gate chain (fresh-row diff + cut-quality gate +
K=3 promotion + R2 gating), plus the C1 freeze-frame containment (persist-timer demote) and the D-CG-1
witness path being structurally demote-only. Insurance run over the 600-crop adversarial splice archive
(`audits/dpkg1_v6_splice_2026_07_04.*`) launched with the flipped default — its reads are EXPECTED
(recaptured own-kill rows); the result quantifies the read-rate the gates must hold against.

## Downstream

- C3 provenance already threads the actual engine id into cut events → KAS trails; no downstream change
  needed for the flip.
- First live session on the flipped default doubles as v6 live validation (bootstrap-via-v6 with the
  D-CG-1 stall witness active) — scheduled as part of the PoSP U2c live gate.
