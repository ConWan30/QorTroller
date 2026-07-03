# G2' replay gate — OCR bootstrap wiring validation (2026-07-03)

Phase W.1 (OCR-verified bootstrap catch) driven through the REAL wired `_session_anchor_fold` over the
archived dense corpus (`retina_kf_crops`, 600 crops, ts-ordered), OCR-ON vs the feed_v1-template baseline.
Harness: `scripts/replay_session_anchor.py` (read-only; bare RetinaGameCapture, no daemon/live/chain). The
`--stride` knob mimics the LIVE sparse R2-gated classify rate — the load-bearing variable this gate surfaced.

## Result — three sampling regimes

| regime | crops | feed_v1 (OFF) | OCR (ON) |
|--------|-------|---------------|----------|
| dense (stride 1) | 600 | catch@271, promote@348, recall 13 | **identical** — feed_v1 caught first, OCR path never exercised |
| **sparse (stride 16 ≈ live ~37)** | 38 | **0 catches** → no anchor → 0 AUTHORED | **catch@32 via `ocr_row_v1`** (no promote — 6 crops left < K=3) |
| moderate (stride 8) | 75 | catch@61, promote@67, recall 2 | catch earlier@41, but that early row cut a weaker anchor → no promote (this realization) |

## Reading it honestly

**This is a diagnosis, not a clean pass.** feed_v1's killer-slot catch is *fragile* — only ~2/150 crops clear
the 0.55 catch floor this session (max 0.566). Consequences:

- **Dense replay MASKS the defect**: 600 samples hit those ~2 catchable crops, so feed_v1 catches (@271) and
  promotes — the OCR path never even fires (feed_v1 wins the first catch). A dense-only gate would have
  wrongly read "feed_v1 is fine."
- **Sparse replay EXPOSES it**: at the live ~37-classify rate, feed_v1 catches **zero** — it misses the ~2
  fragile crops entirely. **This reproduces the live 0/23 failure exactly**, and localizes it: the producer
  never even caught a bootstrap anchor live because the sparse classify never landed on feed_v1's rare
  catchable frame.
- **OCR is the robust cold-start**: 35/600 readable crops vs feed_v1's ~2 → at the same sparse rate OCR
  **catches** (`ocr_row_v1`@32) where feed_v1 gets nothing. That is W.1's validated value.

**But catch ≠ promote.** W.1 fixes the *catch* robustness; reliable *promotion* still depends on (a) the cut
anchor's quality (the earliest readable row OCR catches can be a weaker cut than feed_v1's rare high-score
row — stride-8 showed OCR catching earlier@41 yet not promoting) and (b) enough post-catch classify density to
accumulate K=3. Both are **W.2 (dense classify)'s** domain. So:

## Verdict

- **W.1 VALIDATED** as the robust bootstrap catch under live-like sparse sampling — it directly addresses the
  reproduced 0/23 root cause (feed_v1 catch-starvation).
- **W.1 alone is NOT sufficient for the live match**: promotion under sparsity needs W.2 (dense classify, the
  HOLD-2 fork). The match should run with **W.1 + W.2 together**, not W.1 alone — a W.1-only match risks
  catch-but-no-promote (stride-8 pattern).
- Open refinement (post-HOLD-2): OCR catches the EARLIEST readable row; a "cut the best row in a short window,
  not the first" tweak could raise cut quality. Tracked, not blocking.

**HOLD 3 impact:** the replay does its job — it proves W.1's catch value AND proves the match needs W.2 first.
So HOLD 2 (the B2/dense-classify fork) is the true gate before G3, not an optional parallel. Recommend:
resolve HOLD 2 → wire W.2 → re-run this replay at sparse stride (expect catch@ocr + promote) → then the match.
