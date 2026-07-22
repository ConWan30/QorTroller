# C1 tightening — machine-readable ground truth + measured precision/recall (grok r03 R1)

grok r03 residual **R1**: "filmstrip-every-8s read by eye" is too coarse to make ±200ms claims about
*which* transition. This graduates C1 from informal-eyeball to a measured number.

## Ground truth (machine-readable)

Labeled by reading **4s-interval** scoreboard filmstrips of the run1_cfb27 capture (0-120s and
120-240s halves). Persisted to `~/.vapi/u3_captures/run1_cfb27_20260721/ground_truth_transitions.jsonl`
(kept with the capture, not committed — capture-adjacent data). 16 real down-&-distance **text
changes** + 1 known HUD non-play (quarter break):

```
14  KICKOFF->1st&10     90  1st&10->2nd&9      158  2nd&18->FLAG      210  2nd&11->1st&10
30  1st&10->2nd&3      102  2nd&9->3rd&9       166  FLAG->2nd&18      222  1st&10->2nd&12
42  2nd&3->3rd&2       118  3rd&9->4th&5       170  2nd&18->1st&10
54  3rd&2->4th&inches  130  4th&5->1st&10      182  1st&10->2nd&11
78  4th&inches->1st&10 146  1st&10->2nd&18    (192  quarter_break_hud_gap = NON-play)
```

Still operator/agent-eyeball labels (not a third independent labeler), but now **explicit,
machine-readable, and reproducible** via `scripts/cfb_eval_pr.py`.

## Measured precision / recall (greedy nearest-unmatched match)

| Tolerance | Precision | Recall | TP | False positives | Missed GT |
|---|---|---|---|---|---|
| **±8s** | **0.76** | **0.81** | 13/17 | 69.1, 108.0, **191.6 (quarter-break)**, 235.2 | 78, 158, 166 |
| **±5s** | **0.53** | **0.56** | 9/17 | 8 events | 7 |

## Honest read (this is the point of tightening C1)

- The detector is a **mediocre v0 proxy**, not a validated snap detector: ~0.76/0.81 at a *generous*
  ±8s and it collapses to ~0.53/0.56 at ±5s. The tight-tolerance drop reflects ~5fps (±200ms) + the
  4s-grid GT labeling + real offset between when the text starts changing vs the label.
- The **191.6s quarter-break false-fire is confirmed** as a FP against GT (grok F1/F4 — pinned).
- The 158/166 penalty-FLAG flips are **missed** (FN) — small/fast text changes the threshold+debounce
  don't catch. 78 (4th&inches→1st&10) also missed.
- So C1's original "17 aligns with ~16 plays" is now correctly stated as: **17 detected events,
  precision 0.76 / recall 0.81 at ±8s (0.53/0.56 at ±5s) vs 16 machine-labeled transitions, including
  1 confirmed false-fire and 3 misses.** No longer an informal alignment claim.

## Residual (does NOT block; honest)

- Labels are single-labeler (me), not independent — a true P/R would want a second labeler or an OCR
  cross-check (no tesseract on this box). Stated, not hidden.
- N=1 session, one HUD layout / resolution (grok open-Q #4). Cross-session untested.
- The mediocre P/R + the earlier negative correlation together say: this v0 proxy needs both better
  precision AND a football-appropriate event↔response coupling (grok R4) before it's measurement-grade.
