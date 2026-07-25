# L0 live session — `cfb_rwm_live_08` (2026-07-25)

**Verdict: L0 load-bearing PASS · N≥146 + locator PASS · diversity FAIL (FROZEN_RING).**

Attempted “longer diverse capture” (operator pick #1). Count and locator goals met;
content diversity did not.

## Capture ops

| Field | Value |
|-------|--------|
| Label | `cfb_rwm_live_08` |
| Start | ring cleared → `--capture --uvc-index 2` |
| Source | UVC #2 @ 1920×1080 |
| Stop ring | **447** crops (pure session) |
| Archive | `retina_kf_archive/cfb_rwm_live_08_1784950873` (gitignored) |
| RWM at stop | **auto** — `447 frames marked + chained` |
| Post-check | **EXIT 0** |

## Goals vs result

| Goal | Target | Result |
|------|--------|--------|
| Frame count | N ≥ 146 | **447 — PASS** |
| Locator full cycle | N ≥ 146 + decode | **PASS** (decoded on all 447) |
| Auto-RWM at stop | yes | **PASS** |
| Pure ring | cleared before start | **PASS** |
| Content diversity | non-frozen unique ≫ 1 | **FAIL** — unique **1/447** (0.2%) FROZEN_RING |

## Load-bearing post-check

- [PASS] RWM ran (447 frames, `qortroller-rwm-session-chain-v0`)
- [PASS] third-party re-verify from disk
- [PASS] originals byte-identical
- [PASS] locator decoded on real frames (447 ≥ 146)

## INFO / honesty

- **FROZEN_RING:** all original panels share one content hash. Do **not** cite as multi-frame live play. Same class as live_07; larger N does not fix a frozen UVC/OBS feed.
- Geometry: 614×724; block_px=32 ≈ 5.2% short edge.
- RGC: 112 diag samples; PRESENT_COHERENT 23 / UNVERIFIABLE 84.

## Cite guidance

| Claim | Preferred evidence |
|-------|-------------------|
| Auto-RWM + pure session + N≥146 + locator | **live_08** (this note) |
| Multi-frame live content diversity | still need non-frozen session (live_01-class unique ratio when available) |
| Pipeline dogfood (escrow/stranger) | live_07 ladder dogfood still valid on frozen content |

## Root cause (ops, not RWM math)

UVC #2 delivered a stable still (or de-duped identical panel ROI) for the whole session.
RWM chain math is correct on that still. Next diverse attempt: eye-check **moving**
preview on index 2 before start; use `rwm_live_session_watch.py` mid-session for
`frozen_ring_alert`.
