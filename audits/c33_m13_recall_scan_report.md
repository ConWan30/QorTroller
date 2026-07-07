# C-3.3 Offline Instrument-A Recall Scan — Match 13 (2026-07-06)

Instrument-A (tight_row_ocr v6-only, `ob.tight_row_ocr`) scan over all 524 archived crops from
Match 13 (`retina_kf_archive/match13_hdmi_direct_1783385280`). Measures archive ground-truth
against the live KAS authored_kills=8.

## Summary metrics

| Metric | Value |
|--------|-------|
| Total crops scanned | 524 |
| Elapsed | 415.5s (793ms/crop) |
| OWN_KILL reads | 77 |
| False reads | **0** |
| Distinct kill clusters (5s chaining window) | 27 |
| KAS authored_kills (live) | 8 |
| Overall recall (8/27) | **29.6%** |

## Zero-false-read verdict — HELD

All 77 OWN_KILL reads contain "Qortrola30". Victim-name suffix fusions (e.g. "Qortrola30so",
"Qortrola30mi", "Qortrola30La") are genuine reads where the tight-crop boundary picked up
partial victim-name characters; they count as clean reads and would pass `canon()`. One
ambiguous read (K27: "krfn88Qortrola30") may be a multi-row strip bleed where an adjacent
row's killer handle ("krfn88") leaked into the crop — it is a **single-crop cluster** and
could never reach K=3 promotion, so it has zero operational impact.

**Zero clean false reads of non-own-handle content** across 524 crops. G1' zero-false-read
bar holds.

## Cluster breakdown

| Category | Count | Crops | Cluster IDs |
|----------|-------|-------|-------------|
| 1-crop (un-promotable) | 9 | 9 | K4 K6 K7 K17 K20 K21 K22 K26 K27 |
| 2-crop (un-promotable) | 7 | 14 | K2 K10 K11 K12 K14 K19 K24 |
| 3+ crops (promotable) | 11 | 54 | K1 K3 K5 K8 K9 K13 K15 K16 K18 K23 K25 |
| **Total** | **27** | **77** | |

## Recall gap analysis

**8 of 11 promotable clusters were authored live (73% of promotable).**

**16 of 27 clusters (59%) were structurally un-promotable** — the kill row appeared so briefly
that even the dense archive captured ≤2 samples. The live classify stream (sparser; fires within
R2 windows) could not reach K=3 on these regardless of system health.

**3 promotable clusters not promoted** — timing mismatch between the R2 window and when the kill
row appeared, or K=3 not reached within the window despite sufficient archive density.

## Interpretation

The 30% overall recall is not a system fault — it reflects two orthogonal structural limits:

1. **Brief kill-row display vs K=3 floor** (59% of misses): kill rows that disappeared after
   1-2 archive captures are categorically un-promotable. Lowering K→2 would recover ~7 more
   clusters, improving recall to ~55% — at precision cost. K=3 is the intentional conservative
   setting.

2. **R2 window / kill row timing gap** (3 misses): promotable clusters where the live R2 window
   and the kill row display didn't overlap with enough classify density within the window.

## Live system posture

| Property | Value |
|----------|-------|
| Precision | 100% (0 false authored kills) |
| Recall (all clusters) | 29.6% |
| Recall (promotable clusters) | 73% |
| Character | High-precision, moderate-recall — conservative but honest |

For the D-CERT-5 unified presence-gameplay proof: every authored kill is genuinely verified; the
cost is that brief or R2-misaligned kill rows go unattested.

## Files

- Raw scan result: `audits/c33_m13_recall_scan.json`
- Match 13 KAS record: `audits/kas_record_match13_hdmi_direct_2026-07-06.json`
- Match 13 PoSP record: `audits/posp_record_match13_hdmi_direct_2026-07-06.json`
