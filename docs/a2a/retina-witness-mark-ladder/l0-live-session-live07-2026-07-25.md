# L0 live session — `cfb_rwm_live_07` (2026-07-25)

**Verdict: L0 PASS (pure-session auto-RWM) + full ladder dogfood PASS.**

## Capture ops

| Field | Value |
|-------|--------|
| Label | `cfb_rwm_live_07` |
| Start | ring cleared → `--capture --uvc-index 2` |
| Source | UVC #2 @ 1920×1080 |
| Stop ring | **135** crops (this session only) |
| Archive | `retina_kf_archive/cfb_rwm_live_07_1784949135` (gitignored) |
| RWM at stop | **auto** — `[daemon] RWM: 135 frames marked + chained` |
| Post-check | **EXIT 0** |

## Load-bearing post-check

- [PASS] RWM ran (135 frames, `qortroller-rwm-session-chain-v0`)
- [PASS] third-party re-verify from disk
- [PASS] originals byte-identical

## INFO / honesty

| Finding | Note |
|---------|------|
| Locator cycle | 135 &lt; 146 — short session; full mark cycle not completed |
| **FROZEN_RING** | `unique_content=1/135` — all panels one content hash (OBS freeze / static). Chain math still valid; **not multi-frame live diversity** |
| Geometry | 614×724; block_px=32 ≈ 5.2% short edge |
| RGC | 34 diag samples; 23 PRESENT_COHERENT |

## Why this session matters

1. **Pure ring** — cleared before start (unlike live_01/02 buffer mix).
2. **Auto-RWM** — dotenv arm at stop with N&gt;0 (live_03 failure mode closed).
3. **Ladder dogfood target** — first pure-session archive run through NOV-3 → NOV-2 → NOV-1.1 (see sibling note).

## Preferred L0 cite still

For multi-frame content diversity claims, prefer sessions with non-frozen unique ratio (e.g. live_01 ~50% unique when available). live_07 is the preferred cite for **ops purity + auto-RWM**, not for diversity.
