# L0 live session — `cfb_rwm_live_10` (2026-07-25)

**Verdict: DIVERSE L0 CITE CLOSED — full load-bearing PASS.**

First pure-session capture after OBS freeze was fixed. Meets the open goal from
operator pick #1 (longer diverse capture: N ≥ 146 + non-frozen).

## Capture ops

| Field | Value |
|-------|--------|
| Label | `cfb_rwm_live_10` |
| Start | ring cleared → `--capture --uvc-index 2` (post OBS fix) |
| Source | UVC #2 @ 1920×1080 (moving feed) |
| Early probe (~25s) | 12 panels / 12 unique |
| Stop ring | **367** crops |
| Archive | `retina_kf_archive/cfb_rwm_live_10_1784953588` (gitignored) |
| RWM at stop | **auto** — 367 frames marked + chained |
| Post-check | **EXIT 0** |

## Goals vs result

| Goal | Target | Result |
|------|--------|--------|
| Frame count | N ≥ 146 | **367 — PASS** |
| Locator full cycle | N ≥ 146 + decode | **PASS** (decoded on all 367) |
| Auto-RWM at stop | yes | **PASS** |
| Pure ring | cleared before start | **PASS** |
| Content diversity | non-frozen unique ≫ 1 | **PASS — unique 367/367 (100%)** |

## Load-bearing post-check

- [PASS] RWM ran (367 frames, `qortroller-rwm-session-chain-v0`)
- [PASS] third-party re-verify from disk
- [PASS] originals byte-identical
- [PASS] locator decoded on real frames
- [PASS] content diversity (not FROZEN_RING)

## Contrast with prior attempts

| Session | N | Unique | Cite as diverse? |
|---------|---|--------|------------------|
| live_07 | 135 | 1 (FROZEN) | No |
| live_08 | 447 | 1 (play-call menu / frozen OBS) | No |
| live_09 | 3 | 2 | No (too short; de-dup held) |
| **live_10** | **367** | **367** | **Yes** |

Root cause of earlier FROZEN_RING: OBS stuck on one frame (operator-confirmed) +
play-call menu stills. Content-hash de-dup (F-RWM-FROZEN-CONTENT) prevented
another 400-copy bloat on live_09; live_10 is the first clean diverse bank.

## Cite guidance

| Claim | Preferred evidence |
|-------|-------------------|
| Multi-frame live L0 + auto-RWM + locator + diversity | **`live_10` (this note)** |
| Pipeline dogfood (NOV-3/2/1) | still valid on live_07; re-dogfood on live_10 optional |

## Geometry / calibration

- Crop 614×724; block_px=32 ≈ 5.2% short edge (INFO)
- RGC path active during session (pre-stop status showed climbing diag samples)
