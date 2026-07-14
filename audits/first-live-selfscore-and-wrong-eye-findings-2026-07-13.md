# First live self-score + the wrong-eye findings — 2026-07-13

**Two matches through the `qortroller` product path tonight. One VOID, one scored. The scored one is
the first match ever closed by its own node's honest self-scorecard.**

## The scored match (session_1783982308, Resurgence Casual / Haven's Hollow)
```
RECALL : authored 0 [MEASURED] / reported 2 [OPERATOR-REPORTED]  = 0.0000 (unrounded)
PoSP   : SYNCHRONIZED (fusion_rows=72)     v3: PRESENT (5 conformant kill events)
KAS    : HYGIENE_FAIL authored=0           source: card #1, 1080p60 ACTUAL, content-verified pre-queue
```
- **The HARD-1 fresh-trigger pipeline WORKS:** 34 killfeed lines read across the match (T6.6b read ~2
  all match → 0/21). The witness read the feed continuously; 5 kill events reached the sink + v3.
- **Why 0/2 (stacked, both known):** (a) none of the 34 killer tokens exact-canon-matched
  `q0rtr01a30` — name-read fidelity is rough (`'sha dy'→'THURY'`-class reads) and the HARD-1 safe
  rule refuses non-exact matches (the disclosed tradeoff: miss you rather than credit a stranger);
  (b) `kf_bound_kills=0` — dual-connection HID blindness ⇒ no R2 onsets ⇒ full AUTHORED structurally
  unreachable this match regardless of names.
- **Zero-false-read HELD** (0 false authorship over 34 reads + 20 min pointed at a wall in the void
  session — an unplanned adversarial test, passed).

## The VOID match (session_1783980755, 11 kills — recall NOT measurable)
The witness watched the **webcam**, not the game. Root cause: `setup`'s card probe had persisted
**`uvc_index = 0`** (the webcam — likely probed while the PS5/card was off) into `node.toml`; both
sessions today obediently opened device #0. The log even confessed: *requested 1920x1080 →
**(actual 1280x720)**.* Verdict: VOID for recall (never 0/11); webcam frames are LOCAL-ONLY +
gitignored (ring + archive copies; deletion pending operator ack). KAS authored=0 on the wall =
zero-false-read validation.

## Findings (route to the next HARD/PKG rounds)
- **F-MATCH-2 (setup/play source gate):** `setup` persisted a webcam index without a content ack;
  `play` accepted requested≠actual resolution silently. FIX: play preflight fail-closes on
  actual≠1920x1080 + a first-crop content ack (the manual eye-check protocol used tonight,
  mechanized). The ROI overlay ceremony would also have caught it — make Stage 3 mandatory after
  any `uvc_index` change.
- **F-MATCH-3 (own-handle OCR fidelity):** 34 reads, 0 exact handle matches, operator scored 2.
  Desk-workable: mine this session's archive crops for the operator's kill rows → measure what OCR
  actually read for the handle → tune the confusable fold against real data (never reopening
  substring match).
- **F-MATCH-4 (sink noise):** garbage rows (`'1'→'三:'`) passed the sink filter — tighten the
  status-line/min-length gate on killer tokens.

## Protocol wins banked tonight
Eye-check protocol (content-verify the first ring crop pre-queue) caught the webcam TWICE before it
cost a third match. The self-scorecard rendered `0.0000 unrounded` — the product's honesty rail
survived its first contact with a disappointing number.
