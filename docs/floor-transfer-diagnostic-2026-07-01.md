# Floor-Transfer Diagnostic — RESOLVED 2026-07-01

**Supersedes the "Remote Play softness / floor-doesn't-transfer" hypothesis asserted in
`15e2b487` (loop 1) and `9070a91e` (loop 2).**

## Correction

Commits `15e2b487` and `9070a91e` state that the calibrated `match_floor=0.66` "does not transfer to
this session's Remote Play capture — real kills scored ~0.645, ~0.2 lower than the calibration
session's 0.71–0.78." **That framing is WRONG.** It was asserted from a *single off-peak crop* (0.645)
before per-kill and config-parity verification. The archive-only diagnostic below overturns it.

## Confirmed cause — D-FLOOR-1 = branch (b): SAMPLING ARTIFACT

The capture and the floor are fine. The live inline's single-sample-per-classification scheme (min-gap
+ single-flight timing) captured **off-peak frames**; the peak frames *were* captured and saved to the
crop corpus but were never the panel the inline happened to classify. So `inline_authored=0` was a
**live-sampling miss, not a capture-condition shift.**

## Evidence (Phase 0, archive-only — `retina_kf_archive/seg3_*`, 600 crops)

| Check | Finding |
|---|---|
| Config parity (0.5) | Tonight AND both calibration sessions = `uint8(1080,1920,4)`, HDR-aware, 1920×1080. **Identical** — no capture-condition change. |
| Peaks (0.3) | Real `Qortrola30` kills score **0.702 / 0.736 / 0.843** — ABOVE the 0.66 floor. Verified genuine (`Qortrola30`→`Mr_Dank_34rth` double-kill; `→AWOLNoob`). Deaths captured up to **0.775 / 0.796**. |
| Score variance | Roster match ranges **0.079–0.902** crop-to-crop → a single sample is unreliable by construction. |
| False-positive (0.4) | The ONLY killer-position ≥0.66 matches across 600 crops are the 3 genuine kills → **0 false positives**. |
| Sharpness (0.6) | Tonight softer by Laplacian (717 vs 1212) but **scene-confounded** (different maps) and **irrelevant** — peaks reach 0.84 regardless. |
| JSONL sinks (0.1/0.2) | near-boundary + death logs **empty** — the off-peak live samples never landed in-band, and no victim-slot cleared the floor live (though deaths WERE captured in crops). |

## Fix (Phase 1 — not yet built)

**Max-over-window compositing:** take the MAX score over each R2 window's classifications, not each
sample independently; AUTHORED iff that max ≥ 0.66 at killer position. Archive-validated
false-positive-safe (0 FP on 600 crops). **No new gameplay needed to build/validate.**

`match_floor` (0.66), killer/victim boundary (0.28), and the y-gate (0.42) stay **FROZEN** — the floor
was never the problem; the single-sample scheme was.
