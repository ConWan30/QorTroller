# ASM-Loop: CFB snap-event extractor against the U3 capture — 2026-07-21

## r01 scope

**Task (operator, autonomous grok loop):** Build a CFB27 snap-event extractor that processes the
first U3 raw capture (`~/.vapi/u3_captures/run1_cfb27_20260721`: 1139 frames @~5fps + 7129 HID
input events, from the certified Edge during live play) and emits candidate **snap-event
timestamps**. Those game-event times are the missing half of the U3 correlation — feed them to the
optical co-presence checker (`l9_presence/optical_copresence.py`) + a reaction-lag measurement, so
the CANDIDATE thresholds start becoming measured. grok adversarially audits over the terminal bus.

**Definition of done (this loop):** a pure, tested extractor module + a runner that, against the real
capture, produces a `snap_events.jsonl` (timestamps + method + confidence), plus a first correlation
report (do input events align to snaps above the empirical null?). Grounded in what the frames
actually show (I will look at real frames before choosing the detection method). Converges under grok
PASS (or residual-accepted).

**Ceiling — will NOT claim:**
- NOT ground-truth snap detection. v0 is a CANDIDATE **proxy** (motion-onset / scoreboard-region
  signal), validated against this ONE N=1 session, not label-verified frame-by-frame.
- Frame rate is ~5fps → snap timing precision is **±200ms** — stated, not hidden. Fine for the
  optical session-binding (150-600ms window, seconds-apart events); marginal for fine reaction-lag.
- Does NOT flip `calibrated=True` or any protocol flag. Producing measurement data ≠ calibrating the
  live verdict — that stays a separate, earned step.
- No chain, no FROZEN, no PoAC edit, advisory/offline-analysis only.

**Assumptions:** the capture frames are legible CFB27 (verified — scoreboard bottom-center, play-call
screens, live-field views); a "snap" is the pre-snap-formation → live-play motion transition, and/or
the play-clock disappearing. Both are detectable from frames but imperfectly (replays, cuts,
celebrations = false-positive risk).

**A2A bus:** sealed envelopes via `scripts/a2a_pkg_relay.py` + `deliver --fire grok`
(PYTHONIOENCODING=utf-8). Builder builds; grok audits; no self-audit.

Operator pre-confirmed "proceed + push forward" → moving to r02 build.

## r02 build + fired to grok

Artifacts: `l9_presence/cfb_snap_extractor.py` (OCR-free binarized down&distance change detector,
pure `detect_play_events` core) + `scripts/cfb_extract_snaps.py` (runner → 17 events) +
`bridge/tests/test_cfb_snap_extractor.py` (7 pure-core tests green). PV-CI 184.

Validated vs an eyeballed filmstrip (~16 plays) → 17 detected, times align. **Found + fixed a real
r02 bug: initial ROI sat too low (black area below the text) → 4-6 events; corrected ROI + binarized
signature → 17.** First correlation is a MEASURED NEGATIVE: naive R2↔play-transition (0.5-8s window)
does NOT beat the circular-shift null (0.82<0.88) — frequent R2 + wide window makes chance too high;
honestly a negative, not a session-binding win.

Claims C1-C6 (17-vs-16 validation / ROI-bug-fixed / correlation-is-negative / proxy±200ms/N=1 /
pure-core-tested / advisory-no-flags). Envelope `95357f4c01c8de5f` → `round-03-grok-audit.md`.

## r03 grok audit — PASS (residual WARN)

**ONE VERDICT: PASS.** C3–C6 hold under attack (negative correlation reproduced 0.82<0.88;
proxy ceilings honest; pure-core tested vs frame-I/O untested correctly split; advisory/no live
path). Soft spots: **C1 informal GT** (no machine-readable labels; 17 includes admitted 191.6s
quarter-break false-fire, change_score=113.99) and **C2 ROI-bug narrative** (plausible, no
before/after artifact) — WARN residual-accepted, not BLOCK.

BUILD-NOW by auditor: drop unused `field` import; pin continuous-present HUD false-fire class
test (`test_continuous_present_hud_change_fires`) → 8 pure-core tests green. Stage only.

Artifact: `docs/a2a/cfb-snap-extractor/round-03-grok-audit.md`. Residuals R1–R4 (GT labels,
ROI proof, synthetic image tests, tighter football coupling) remain builder/operator.
Does **not** unlock optical `calibrated=True`.

## r03 grok audit — PASS (residual WARNs)

Envelope `95357f4c01c8de5f` audited. **ONE VERDICT: PASS.**

- C1: times real/reproducible (17 events re-run match); GT alignment informal (no labels); 191.6s
  quarter-break false-fire included in the 17 (change_score 113.99 outlier) — WARN soft.
- C2: ROI-bug narrative plausible, no before/after artifact — WARN unverifiable.
- C3: correlation **reproduced** hit_rate=0.82 < null_q95=0.88 → event_coupled=False — honest NEGATIVE.
- C4–C6: ceilings, pure-core test split, advisory/no-live-path all hold.
- BUILD-NOW: unused import removed; `test_continuous_present_hud_change_fires` pins C4 false-fire class;
  tests 8/8 green. Stage-only, no commit/push.
- Artifact: `docs/a2a/cfb-snap-extractor/round-03-grok-audit.md`.

## r03 audit (grok) — VERDICT: PASS (residual-accepted)

grok r03 (`round-03-grok-audit.md`, returncode 0, sha256 matched, independently re-ran the extractor
+ reproduced the correlation). **PASS.** grok did BUILD-NOW: removed unused `field` import + added
`test_continuous_present_hud_change_fires` (8 tests green, PV-CI 184).

Per-claim: C3/C4/C5/C6 PASS (reproduced). C1 WARN (times real+reproducible but GT is informal
eyeball not machine labels; 1 of 17 = 191.6s quarter-break false-fire, score 113.99 vs peers ~25-31).
C2 WARN (ROI-bug narrative plausible but no committed before/after artifact). F7 INFO (grok got 39
R2 onsets vs my 37 — edge-def diff, same regime). Both WARNs residual-accepted for offline CANDIDATE.

Open residuals (grok R1-R4, none BLOCK): R1 export machine-readable GT labels (graduates C1 WARN→P/R);
R2 before/after ROI note; R3 synthetic-image tests for frame helpers; **R4 (substantive) tighter
football coupling feature — C3 correctly negative for the naive wide window; the real next design
question is the intended football event↔response pairing + window.**

Loop converged at PASS. Extractor works (17 reproducible play-transition events, N=1); correlation is
an honest NEGATIVE that surfaces the real next question.
