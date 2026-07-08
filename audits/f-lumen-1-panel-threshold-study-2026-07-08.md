# F-LUMEN-1 — Panel-Scale Scene-Change Threshold Study (2026-07-08)

**Question:** the 6.0 fresh-diff threshold (killer-slot-tuned, `_SESSION_ANCHOR_FRESH_DIFF`)
made panel-scale scene streams read ~92% SCENE_CHANGE (M14: 381/412). What threshold makes
panel-scale segmentation legible, and does it survive topology changes?

## Delta distributions (mean-abs-gray, consecutive archived panel crops)

| Percentile | M14 (Remote Play, n=412) | M13 (HDMI, n=523) |
|---|---|---|
| p50 | 47.4 | 47.2 |
| p75 | 64.2 | 62.0 |
| p90 | 87.8 | 80.1 |
| p95 | 106.8 | 99.2 |
| max | 175.7 | 166.8 |

**Finding 1 — cross-topology stability:** RP-codec and HDMI-clean distributions are nearly
identical at every percentile. The panel's ambient change energy is a property of the game's
HUD, not the capture path. One calibrated constant serves both topologies.

**Finding 2 — the 6.0 explanation:** the killer-slot threshold is ~8x below the panel-scale
MEDIAN. It was never wrong — it was scoped to a small, mostly-static row region; the panel
is a living HUD.

**Finding 3 — kill onsets sit at ~p75-p80:** median max-delta within 3s of a kill-cluster
onset = 68.1 (M14) / 71.9 (M13), vs ambient median ~47. Kill-row appearances are visible in
the delta stream but not extreme outliers.

## Threshold sweep (ambient change rate vs kill-onset sensitivity)

| thr | M14 changes | M14 kills≥thr near onset | M13 changes | M13 kills≥thr |
|---|---|---|---|---|
| 55 | 37.9% | 9/15 | 36.5% | 22/27 |
| **63** | **26.7%** | **9/15** | **23.7%** | **17/27** |
| 70 | 19.4% | 7/15 | 16.4% | 14/27 |
| 80 | 13.1% | 4/15 | 10.1% | 10/27 |

## Decision — `PANEL_FRESH_DIFF = 63.0` (the cross-topology p75)

~25% ambient change rate (stable segments exist: M14 re-run produced 36 SCENE_STABLE_SEGMENT
events vs 0 before) while retaining ~60% kill-onset sensitivity. Rationale rail: SCENE_CHANGE
is generic structure for the meaning plane, **NOT a kill detector** — OCR owns kills at
precision 1.0; nothing downstream may treat scene-changes as kill evidence. Consumers wanting
a different operating point read this sweep; the runner takes `--fresh-diff`.

**Effect (M14 re-run at 63.0):** 403 events (381 change / 0 stable) → **168 events
(110 change / 36 stable / 15 clusters / 7 windows)**, joins OK.

## Files
- Stats: `audits/f_lumen1_delta_stats.json`
- Constant: `l9_presence/game_state_buffer.py::PANEL_FRESH_DIFF`
- Recalibrated stream: `audits/scene_stream_match14_rp_option_b_1783475385.jsonl`
