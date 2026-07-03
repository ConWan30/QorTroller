# G3 live-match results — full producer, 2 matches (2026-07-03)

Producer under test: `--capture --killfeed-inline --session-anchor --ocr-bootstrap --dense-classify` +
`KILLFEED_CV_FEED_MAX_YFRAC=0.75` (rendering profile, see finding 1). Real controller (no simulation),
Remote Play WGC capture, frames healthy both matches (0 stalls, ~40-52 fps, governor stable).

## Match 1 — COD multiplayer (daemon `g3mp`): ✅ FULL CHAIN, FIRST LIVE AUTHORED

```
13:20:58 candidate_cut  sha=c7dd3b58  (anchor archived to retina_kf_anchors/)
13:22:02 PROMOTED       (K=3 consistency, 0 FP fires, 0 demotions)
13:22:08+ 5 live AUTHORED_PRESENT  scores 0.80-0.93  anchor=session_20260703_131828@0.66
```

**bootstrap → cut → promote → live AUTHORED @0.66** — the first live AUTHORED ever produced by the
auto-generated per-session anchor (3 prior matches / 23 kills produced 0). Every AUTHORED record carries the
promoted session regime tag (carry-forward 1 live-proven). Dense classify folded 3-5 members per window.

### Finding 1 (blocking, fixed live): MP renders the feed LARGER + LOWER than the Warzone calibration

First 20 minutes of MP produced zero catches despite kills. Live crop inspection showed the own-kill row
(`Qortrola30 -> GR1MR34P3R4161`) clearly visible at panel y≈0.58 — **above the Warzone-calibrated y-gate
0.42**, so geometry rejected every row before OCR/template ever scored it. With the gate at 0.75, OCR read
10/30 live ring crops (vs 0/30 at 0.42). Fixes:
- `KILLFEED_CV_FEED_MAX_YFRAC=0.75` (the designed env override — a RENDERING PROFILE, superset that still
  excludes the roster at y≈0.97; the 0.66 match floor and 0.28 killer gate untouched).
- Seam fix (committed): `_ocr_bootstrap_read` now takes geometry from the monitor (single source, env-honoring)
  instead of the OCR engine's hardcoded Warzone default — the engine default silently re-imposed 0.42.
- The pre-fix hour also ran without `--killfeed-inline` (operator launch had producer off) — flag documented.

## Match 2 — Warzone BR (daemon `g3wz2`): cut but STUCK CANDIDATE — the pre-registered cut-quality gap

```
13:34:33 raw AUTHORED (feed_v1 per-sample) 0.720 @killer x=0.16
13:34:38 candidate_cut sha=0fe74490          (5s after the first kill — catch latency excellent)
13:40-13:42 3 more raw feed_v1 AUTHORED (0.705 / 0.851 / 0.768)
NEVER PROMOTED (K=3 unmet), 0 FP fires, 0 demotions -> composite AUTHORED = 0
75 in-window classifies / 45 windows (dense classify working; bg_p95 0.535 well under floor)
```

Two honest readings:
- **The R1 promoted-only fold did its job**: an unpromoted candidate never authored a composite — no
  false-confidence records. The 4 kills live as raw per-sample AUTHORED telemetry (feed_v1 cleared 0.66 on
  them — THIS match's kill rendering happened to be feed_v1-compatible), not as composite verdicts.
- **The cut-quality gap is real** (pre-registered in the G2' doc): the bootstrap cuts the FIRST readable row;
  that cut scored subsequent kill rows sub-0.66, so `_consistent` never reached 3. The stride-8 replay showed
  the same shape offline (OCR caught earlier@41 yet the early cut didn't promote).

## Refinement queue (next increment, in leverage order)

1. **Best-row cut**: during a short window after the first catch, re-cut if a stronger candidate row appears
   (replace-while-CANDIDATE; promotion gates unchanged). Directly targets match 2's stuck-CANDIDATE.
2. **Candidate re-cut on stall**: if CANDIDATE sees N killer-slot raw-AUTHORED (feed_v1/OCR) that the candidate
   itself scores sub-floor, the cut is evidently weak — demote-and-recut from the next catch (logged, R3-style).
3. Composite double-write dedup (cosmetic; each resolution writes 2 identical jsonl lines).

## Verdict

G3 **green on the producer thesis**: the full chain works live (match 1), the catch is rendering-robust
(OCR/geometry finding fixed), density is fixed (75 classifies vs the starved ~37), and the failure mode that
remains (match 2) is the narrow, pre-registered cut-quality gap with a clear mechanical fix — not an unknown.
The B2 instrumented capture stays a clean follow-on (dense-tail alone reached AUTHORED in match 1).

## Match 3 — Warzone BR stall-recut validation (daemon `g3br_recut`, 14:21-14:30)

```
14:21:40 candidate_cut sha=8e65da13
14:22-14:27 5 raw feed_v1 AUTHORED (0.71-0.79) the candidate scored sub-floor
14:27:19 candidate_demoted_stall (3rd witnessed miss -> demote, logged)   <- THE FIX FIRING LIVE
14:28:25 next kill -> 14:28:30 candidate_cut sha=5ec25956 (recut, 71s after demotion)
```

**Stall-recut VALIDATED**: the weak cut absorbed exactly stall_limit=3 witnessed kills and was replaced —
the match-2 stuck-all-match shape is gone. Composite AUTHORED remained 0 this match only because it ended
~2 min after the recut (second candidate never saw K=3 kills) — a match-length artifact, not a stall.

**New finding (drives queue #1)**: both BR cuts have been weak while the MP cut promoted instantly. The
fixed +/-72x14 px cut box was implicitly sized for MP's larger rows; BR's smaller feed rows likely mis-frame
it. Next refinement = scale-aware / best-row cut sizing, validated offline against the BR crop archive before
the next match.

## Match 4 — Warzone BR gated-cut validation (daemon `g3br_gatedcut`, 15:55-16:04): ✅ ARC CLOSED

```
15:55:23 candidate_cut sha=b46bd348   (first catch PASSED the quality gate)
15:55:42 PROMOTED                     (19s cut-to-promote; 0 stalls, 0 FP, 0 demotions)
15:55-16:04  13 composite AUTHORED_PRESENT @0.756-0.957 (session anchor; 1-10 members/window)
```

**Gated cut VALIDATED live — first composite AUTHORED in BR.** The decisive counter: `inline_authored: 0` —
static feed_v1 NEVER cleared 0.66 raw in this match's rendering. All 13 AUTHORED came from the auto-generated
session anchor: the exact scenario the producer exists for (a rendering where the static anchor yields zero).
Cut-to-promote latency collapsed from stuck-all-match (match 2) / stall-churn (match 3) to 19 seconds.

## Arc summary (4 live matches, one afternoon)

| match | rendering | result |
|-------|-----------|--------|
| 1 MP  | large feed | first-ever live AUTHORED (5 @0.80-0.93) after y-gate rendering profile |
| 2 BR  | small feed | stuck CANDIDATE -> stall-recut built |
| 3 BR  | small feed | stall-recut fired live (demote@3 -> recut 71s) -> cut-box finding |
| 4 BR  | small feed | gated cut: promote in 19s, **13 AUTHORED @0.76-0.96, feed_v1 raw = 0** |

Producer status: bootstrap (OCR + template + gate) -> cut -> promote -> composite AUTHORED works live across
BOTH rendering families with zero false positives across all 4 matches. Remaining queue: composite jsonl
double-write dedup (cosmetic) + the B2 instrumented-capture session (conjunction leg, own session).
