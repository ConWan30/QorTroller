# RP-3 — OCR Precision on Remote-Play-Encoded Frames (2026-07-07)

Instrument-A scan (`ob.tight_row_ocr`, v6-only — the SAME shared engine the live
bootstrap uses) over both RP-era match archives, answering whether the zero-false-read
bar measured on HDMI-clean M13 frames (0 FP / 524 crops) survives Remote Play's codec.

## Results

| Archive | Topology | Crops | Matched | Suspect (false-read candidates) | ms/crop |
|---------|----------|-------|---------|--------------------------------|---------|
| match12_kas_validation | RP, codec-contended (94.9% CPU, ema_fps 3.76) | 35 | 0 | **0** | 1235 |
| match11_kas_validation | RP-era, WGC collapsed ~8fps (zombie process) | 116 | 5 | **0** | 1098 |
| **RP-era total** | | **151** | **5** | **0** | |
| M13 baseline (C-3.3) | direct HDMI, clean | 524 | 77 | 0 | 793 |

All 5 M11 matched reads contain the own handle verbatim and sit in the **killer slot**:
`Qortrola30`, `Qortrola30`, `Qortrola30Xx`, `Qortrola3011`, `Qortrola30` — the suffix
fusions are the same genuine-read victim-name-bleed pattern C-3.3 documented on M13.
This exactly **reproduces the prior ad-hoc fast scan** (5 confirmed OWN_KILL, 0 FP),
now with a committed, re-runnable script (`scripts/rp_ocr_precision_scan.py`).

## Verdicts

**Precision bar: HELD on RP-encoded frames.** 151 codec-degraded / contention-degraded
crops produced zero canon-matched hallucinations. The ABSTAIN discipline did its job on
compression noise — v6 abstained on 146/151 rather than guessing. This was the RP-specific
risk (a faster reader hallucinating handles out of macroblocking); it did not materialize.

**Readability through RP degradation: DEMONSTRATED but not RATE-MEASURED.** M11's 5 reads
prove v6 reads genuine kill rows through fps-collapsed RP-era capture. But both archives
are sampling-starved (M11 collapsed by the zombie process, M12 by codec contention), so
"what fraction of kills are readable under *healthy* RP capture" is unanswerable from
this data — the confound is sparse sampling, not glyph quality. That number is RP-2's
job (Match 14's denser RP archive).

**F-RP3-1:** M12's 35-crop archive cannot distinguish "codec degraded glyphs" from
"no kill rows sampled" — 0 matches with 0 suspects is precision-clean but
readability-silent. Do not cite M12 as evidence in either direction on readability.

## What this closes and what it doesn't

- CLOSES: the "v6 might hallucinate on RP codec artifacts" risk (the B8-class concern
  applied to RP). Zero false reads across every RP-era crop in the archive.
- DOES NOT CLOSE: the RP recall floor. That requires RP-2 (Match 14 under RP with a
  healthy-density archive), after which this same scan re-runs as the post-match audit.

## Files

- Raw scan: `audits/rp_ocr_precision_scan.json`
- Script: `scripts/rp_ocr_precision_scan.py` (read-only, re-runnable on any archive)
- HDMI baseline for comparison: `audits/c33_m13_recall_scan_report.md`
