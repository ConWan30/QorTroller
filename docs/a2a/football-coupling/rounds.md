# ASM-Loop: football-appropriate event<->response coupling (grok R4) — 2026-07-21

## r01 scope

**Task:** Design + build the coupling feature the negative correlation (docs/a2a/real-play-liveness
+ cfb-snap-extractor arcs) shows is missing: a football-appropriate game-event <-> input-response
pairing that can beat the circular-shift null, using the real run1_cfb27 capture
(~/.vapi/u3_captures/run1_cfb27_20260721: 1139 frames, 7129 HID events, 17 detected + 16 GT
down&distance transitions, measured P=0.76/R=0.81 at +/-8s). grok collaborates FORWARD (steer before
build) then adversarially audits the build. Terminal bus, autonomous.

**Diagnosis of WHY the naive coupling failed (grounds the redesign):** down&distance CHANGES at the
END of a play / start of the post-play display — there is then a huddle/play-call gap before the
NEXT snap actually happens. So "R2 within 0.5-8s of a down&distance change" is measuring input
during huddle/play-call, not input at the snap. The event timestamp itself was the wrong proxy for
"snap," not just the window width.

**Candidate coupling redesigns (to pressure-test with grok, not yet chosen):**
- **D1 — field-motion-onset as event.** Crop the ON-FIELD region (not scoreboard) and detect a sharp
  motion-onset (frame-diff spike) as the actual snap instant — no OCR, no down&distance lag. Input
  response should cluster tightly AFTER this, not the down&distance change.
  Needs the raw frames (already captured) + a new field-crop.
- **D2 — lag-conditioned null on the existing down&distance events.** Keep the current event set but
  let the reaction window float (search the highest-density input lag AFTER each event instead of a
  fixed 0.5-8s), i.e. "is there SOME consistent input lag from event, even if not immediate."
- **D3 — defensive-reaction framing.** On defense, input (stick movement) reacts to the SNAP not the
  QB's own trigger; still needs an event proxy for "ball is live," so it depends on D1 or an
  equivalent.

**Definition of done:** a built + tested coupling module, run against the real capture, that either
(a) demonstrates event_coupled=True on real data via optical_copresence, or (b) produces another
honest, better-diagnosed negative with a clear next step — either is a valid outcome; the loop is
not chasing a win, it's chasing the correct measurement. grok PASS (or residual-accepted) required
before commit.

**Ceiling:** advisory/offline only. Does not flip calibrated=True, poep_enabled, L6B, no chain, no
FROZEN/PoAC edit. N=1 capture only — no claim of generalization beyond this session.

**A2A bus:** sealed envelopes via scripts/a2a_pkg_relay.py + deliver --fire grok
(PYTHONIOENCODING=utf-8), autonomous per operator directive.

## r02 status (2026-07-21/22)

| Round | Agent | File | Status |
|-------|-------|------|--------|
| r01 | claude | `round-01-claude-open.md` | OPEN delivered; body sha256 MATCH |
| r02 | grok | `round-02-grok-expand.md` | **EXPAND delivered** — huddle-gap partially refuted; steer D1+D3 merge; D2 secondary matched-null only; BUILD-NOW pure module green (11 tests) |

**Grok steer summary:** primary failure of naive coupling is **density + wide window vs circular-shift null** (reproduced hit≈0.81 < null_q95≈0.88), not a uniform long huddle gap. Pilot lags are **mixed/threshold-sensitive**. Claude r02: B1–B6 real-capture table, honest number either way.

## r02 grok EXPAND — shipped BUILD-NOW module + steered design

grok refuted the huddle-gap diagnosis as primary cause (density/window-saturation on the circular-
shift null is load-bearing, not long huddle gaps — pilot lag data was mixed, not "mostly short").
Steered: MERGE D1 (field-motion-onset as event) + D3 (multi-input response, not R2-only) as primary,
fixed-window first; D2 matched-adaptive-lag only as secondary (with the look-ahead-bias guard: null
must re-run the SAME adaptive search per circular shift). SHIPPED pure module +11 tests directly:
`l9_presence/football_event_coupling.py` + `l9_presence/tests/test_football_event_coupling.py`.
Verified on disk, 11/11 green. Own probe already showed D1+D3 fixed-window at-null (honest, not hidden).

## r03 build — B1-B6 executed against real capture; 1/20 exploratory positive self-flagged

Built `scripts/football_coupling_eval.py`: held-out threshold (trained on first-third only, not
whole-file percentile) + 4-baseline x 5-window table (GT+R2 / detector+R2 / field+R2 / field+multi)
+ matched-adaptive fallback. Real result on run1_cfb27: **steered primary (field+multi) at-null on
ALL 5 windows + matched-adaptive** (peak 0.31 < q95 0.33). One incidental positive elsewhere
(detector-downdist+R2, 200-2000ms, hit 0.588 vs null_q 0.471) — self-flagged as a likely
multiple-comparisons false positive (1 hit / 20 tests ~= the expected FP rate) rather than reported
as a discovery. Sent to grok for adversarial check of that reasoning, not asserted unilaterally.

## r04 audit (grok) — VERDICT: PASS

grok independently re-read the report (returncode 0, sha256 matched), re-ran the unit tests
(11 passed), and CONFIRMED C1/C2/C3/C5/C6. **C4 PARTIALLY CONFIRMED** — sharpened the reasoning:
the decision (don't claim coupling from B) is correct, but "independence of 20 tests" + "Bonferroni"
framing was sloppy (the tests are correlated, not independent; the real disqualifiers are the thin
0.118 margin on N=17, zero support at tighter windows, and a non-human-band 5750ms adaptive lag).
**Ruling: keep the B finding in the residual trail as `exploratory_cell_positive; weight=0`, do NOT
delete it** — erasing it would be the mirror-image mistake (post-hoc cleanup) of over-claiming it.

**Honest residual (machine-readable, grok r04):**
```
primary_design = D1_field_motion + D3_multi_input
primary_result = event_coupled_FALSE_all_fixed_windows_and_matched_adaptive
incidental_positive = B_detector_downdist_R2_200_2000ms (exploratory; weight=0)
honest_claim = controller_input_not_event_locked_to_optical_football_clocks_at_this_assurance_grade_on_this_capture
not_claimed = humanity | calibrated_optical_flag | multi_session_generalization | snap_label_P_R
```

**Next-capture plan (grok NC1-NC7, explicit):** run2 same setup; FREEZE crop+thr from run1 (no
re-fit — closes the thr-lookahead residual); PRE-REGISTER only 3 windows for the primary (not a
20-cell hunt) + 1 optional pre-registered B-cell; if operator can, label ~15 real snap instants for
a true D1 P/R; stratify offense/defense drives if possible. Decision rule: primary TRUE on run2 ->
replication candidate; primary FALSE again -> adopt "channel-negative for CFB optical clocks at this
grade," stop thrashing this design, fall back to Thesis B passive continuity.

**LOOP CONVERGED at PASS.** Definition-of-done met via option (b): honest primary negative + residual
+ concrete next-capture plan. No forced win. Nothing calibrated, no flags, no chain, no FROZEN/PoAC.

## Post-loop replication check on run3_cfb27_20260722 (2026-07-22, off-rig)

The steered PRIMARY design (D1 field-motion-onset + D3 multi-input, the same audited machinery
from this arc's PASS) was run against a SECOND, independent, longer real capture
(run3_cfb27_20260722: 300s, 66 field-motion events, 189 multi-input onsets — vs run1's 240s/42/112)
that didn't exist when this loop closed. This is an informal replication (not the exact frozen-
crop/pre-registered-3-window NC1-NC4 protocol grok specified — thresholds were not frozen from
run1, and the eval swept the same 5 windows as before rather than 3 pre-registered ones), but it
answers the same question grok's own NC7 decision rule anticipated.

**Result: the steered primary is at-null on ALL 5 windows again** (same as run1), and the matched-
adaptive D2 fallback ties exactly at the null threshold (real_peak=0.3788 vs null_q95=0.3788 — not
exceeding it, correctly still `event_coupled=False`).

**This is a genuine second negative on independent data — the earlier finding replicates.** Per
grok's own NC7 rule ("primary FALSE again -> adopt residual channel-negative... fall back Thesis B
passive continuity"), the honest conclusion stands: optical field-motion+input coupling for CFB at
this measurement grade does not beat chance across two independent sessions. This does NOT retract
anything — it strengthens the earlier honest negative from N=1 to N=2, and correctly redirects
confidence toward the passive-continuity design (Thesis B / Composite-B G1-G6), which — separately,
in the tremor-fft-real-data arc — just produced its first real PARTIAL_PRESENT verdicts on this
exact run3 capture. The two results are consistent: passive continuity works: optical coupling
(as designed so far) does not, on two real sessions.

**Script fix (committed):** `scripts/football_coupling_eval.py` required a manually-eyeballed
`ground_truth_transitions.jsonl` (baseline A only) unconditionally, which run3 doesn't have —
blocked the whole eval. Fixed to skip baseline A gracefully when that file is absent, still running
B/C/D (including the steered primary D, which needs no manual labels). Regression-verified against
run1 (baseline A still runs there, unchanged).
