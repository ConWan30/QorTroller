# A2A round 01 — OPEN/EXPAND: football-appropriate event<->response coupling (grok R4)

You are grok in an A2A collaborative loop. FORWARD round — attack the framing AND contribute before
Claude commits to a build. Repo: QorTroller, branch feat/l9-consistency-adversarial-harness. Rails:
228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator. Design+prototype
only, no flag flips.

## The problem

Prior arcs (docs/a2a/real-play-liveness/, docs/a2a/cfb-snap-extractor/, both grok PASS) measured:
1. A CFB27 down&distance-change proxy detector: P=0.76/R=0.81 @+/-8s (0.53/0.56 @+/-5s) vs 16
   machine-labeled ground truth (docs/a2a/cfb-snap-extractor/c1-ground-truth-eval.md).
2. Naive correlation "R2 press within 0.5-8s of a down&distance-change event" via
   l9_presence/optical_copresence.py: hit_rate=0.82 < null_q95=0.88 -> event_coupled=FALSE. A
   measured NEGATIVE — the design's own honest finding, not hidden.

**R4 (this loop's task):** design + build a coupling that CAN beat the null, using the real capture
(~/.vapi/u3_captures/run1_cfb27_20260721: 1139 frames, 7129 HID events).

## Claude's diagnosis + a pilot finding (attack this)

**Diagnosis:** down&distance CHANGES at the end of a play (post-play display), with a huddle/play-call
gap before the NEXT actual snap — so "input within 0.5-8s of the event" was measuring huddle input,
not snap-reaction input. The event timestamp itself may be the wrong proxy, not just the window.

**Pilot probe (field-region motion-onset, no OCR):** cropped the ON-FIELD area (excluding scoreboard/
crowd), computed frame-diff motion at ~5fps, and looked at the peak motion timing in [event, event+15s]
after each of the first 6 GT down&distance transitions:

```
after 'KICKOFF->1st&10'    @14s: peak+1.3s
after '1st&10->2nd&3'      @30s: peak+13.2s   <- outlier
after '2nd&3->3rd&2'       @42s: peak+1.2s
after '3rd&2->4th&inches'  @54s: peak+3.8s
after '4th&inches->1st&10' @78s: peak+2.8s
after '1st&10->2nd&9'      @90s: peak+3.3s
```

Most peaks land **1-4s after** the down&distance event, not a long huddle gap — this CONTRADICTS
Claude's own huddle-gap diagnosis (mostly). One 13.2s outlier exists.

## Candidate designs (pick/merge/refute — do not just approve)

- **D1 — field-motion-onset AS the event** (replacing down&distance-change): detect the motion spike
  itself as the snap-instant proxy, tighter than the down&distance text-change. Then correlate INPUT
  onset to THIS event.
- **D2 — lag-conditioned null**: keep down&distance events, but instead of a fixed 0.5-8s window,
  search for the input lag with peak density after each event (adaptive), and test whether that
  peak beats a shifted-null at the SAME adaptive-search procedure (avoid look-ahead-bias — a real
  adversarial risk: adaptive search without a matched null will always "find" a lag).
- **D3 — chain field-motion -> input** (defense-appropriate): field-motion-onset (D1) as event,
  input-onset (any trigger/stick burst, not just R2) as response — covers both offense (QB action)
  and defense (reaction to snap) without assuming which side the player is on.
- **Refute all three** if there's a better-grounded 4th option.

## What to return (write to docs/a2a/football-coupling/round-02-grok-expand.md)

1. Attack Claude's huddle-gap diagnosis given the pilot data contradicts it mostly.
2. Steer D1 vs D2 vs D3 vs merge vs refute, with reasoning grounded in the actual numbers above.
3. Name the #1 statistical risk in whichever design you steer toward (esp. D2's look-ahead-bias risk
   if adopted — must the null model use the SAME adaptive procedure, and how).
4. Given N=1 capture, 7129 HID events, 1139 frames, what's the honest ceiling this loop can prove
   today vs what needs a second capture session?
5. Ranked build order for Claude's r02.

Ground everything; this loop should end with a real number, positive OR negative, not a forced win.
