# Phase C — C-3.1: KAS Authorship Quality Measurement Plan

**Status: DRAFT — awaiting review/approval per C-3.1's own exit criteria before C-3.2 (session
capture) begins. No sessions run, no code changed by this document.**

## 1. Purpose and scope

Characterize the precision, recall, and failure modes of the current KAS authorship path — the
OCR bootstrap (`l9_presence/killfeed_ocr_bootstrap.py`) + session-anchor state machine
(`l9_presence/killfeed_session_anchor.py`) + dense-tail classify (Phase W.1/W.2, `d2eb8d9e`/
`9f7b0e0b`) + the D-CG-1/C1 hardening committed in `7d036b2f` — under realistic, varied rendering
conditions. This is NOT a re-run of G1' (`docs/ocr-bootstrap-precision-2026-07-04.md`): G1' is a
**read-only audit lane** that measures the false-read bar against the archived crop corpus using
two algorithmic instruments cross-checking each other. This plan measures **end-to-end session
outcomes** (did a real match's kills actually get authored, on the wired live path) with an
**independent, non-algorithmic ground truth**, which G1' explicitly does not have (its two
instruments are both algorithms; their agreement corroborates independence, but neither is
"what actually happened in the match").

## 2. Ground truth methodology

### 2.1 The gap G1' leaves open

G1's disagreement adjudication (7 candidate false reads, all resolved TRUE) was a human visually
inspecting a zoomed crop and judging "does this look like a real kill row." That is a reasonable
control against algorithmic false-reads, but it is still adjudication FROM THE SAME CROPS the
instruments read — it cannot catch a scenario where BOTH instruments miss a real kill entirely
(a false negative invisible to crop-level adjudication, since there's no crop to adjudicate).

### 2.2 Independent ground truth for this plan

Call of Duty: Warzone (the "WZ" sessions) shows a per-match summary screen with each player's
final kill count. This is an INDEPENDENT source — it derives from the game's own server-side
kill tracking, not from anything the killfeed OCR/template pipeline touches. For every C-3.2
session:

1. Capture the end-of-match summary screen (a still crop, same capture pipeline, different ROI)
   alongside the normal killfeed capture.
2. Record the summary screen's kill count as the session's ground-truth `N_true_kills`.
3. Separately, a human reviewer scrubs the session's video/crop timeline in real time (not
   crop-by-crop adjudication — a continuous watch-through) and timestamps each real kill event,
   producing a ground-truth kill-event list with approximate timestamps.

This gives two independent checks per session: an aggregate count (summary screen) and a
timestamped event list (reviewer watch-through) — if they disagree, that disagreement is itself
a finding about either capture completeness or reviewer error, and must be resolved before the
session's data is used, not silently averaged.

### 2.3 What ground truth is NOT, in this plan

Neither Instrument A (OCR) nor Instrument B (template) from G1' counts as ground truth here, even
though both are proven low-false-read tools. Using the system under test as its own ground truth
would make precision/recall circular. G1's instruments remain in the loop only as the THING BEING
MEASURED (via the live KAS records the session produces), never as the source of truth about what
happened.

## 3. Rendering families to test

### 3.1 Why "rendering family" needs a measured definition, not a session-name label

The load-bearing finding across G1'/D-PKG-1/D-CG-1 is that killfeed kill-highlight color is
per-match/per-team-assignment, not a fixed game-wide constant — this is WHY the static `feed_v1`
color anchor is marginal and WHY the OCR bootstrap exists at all. So far, "rendering family" has
only ever been named informally by session id (seg3, sess_ab, sess_hid, the WZ matches). That is
not a reproducible grouping — two sessions with the same session-name pattern could have
different team-color draws, and two differently-named sessions could share a color by chance.

### 3.2 Proposed measurable definition

For every session in this plan's corpus, extract the mean RGB of the killer-slot row background
at the moment of each confirmed kill (the same region `killer_slot_best`/`tight_row_ocr` already
crop), and cluster sessions by that measured color rather than by name. This reuses
`l9_presence.trigger_hud_coupling.center_roi_redness`'s general approach (sampling a fixed ROI's
color channel) but applied to the killfeed row region instead of the hitmarker ROI — no new
capture mechanism, just a new extraction point over crops already being saved.

### 3.3 Coverage target

At minimum, this plan's corpus should include:
- One session from each of the 3 rendering families already characterized in G1' (the
  seg3/sess_ab/sess_hid tesseract-era renderings) — reusable AS ARCHIVE for the precision side,
  but these have no independent ground truth (they predate this plan) and so can only inform the
  rendering-family taxonomy (§3.2), not the precision/recall numbers in §5.
- At least 2 NEW live sessions per distinct measured rendering family observed during C-3.2
  capture, so precision/recall is reported per family with N≥2, not a single point.
- Deliberately include the marginal-color case if it recurs (match3's `inline_bg_max ≈ 0.65`
  band) — this is the session type most likely to produce a genuine miss, and the plan should
  not avoid it by only capturing "easy" renderings.

## 4. Metrics

### 4.1 Precision — already strongly evidenced, re-confirm don't re-litigate

G1' already measured zero false own-handle reads across 3,091 crops / 5 sessions. This plan does
not need to re-run that measurement at the same scale; C-3.2's job on precision is a smaller
confirmatory check (any new false read is a finding requiring immediate escalation, not folded
quietly into an aggregate), not a fresh 3,000-crop sweep.

### 4.2 Recall — the actually open question, defined at the EVENT level

G1' reported CROP-level catch rates (e.g., Instrument A OWN_KILL on ~5–15% of crops depending on
session), but a real kill event spans several crops during its feed dwell time (a few seconds),
so per-crop catch rate understates true per-KILL recall. This plan defines the metric that
matters for the session-anchor bootstrap (which only needs ONE catch per kill to seed/confirm a
candidate):

`event_recall = (kills where >=1 crop in the kill's dwell window was correctly read as OWN_KILL) / N_true_kills`

computed against the §2.2 ground-truth event list, per rendering family (§3.2), separately for:
- the OCR bootstrap catch (pre-promotion, BOOTSTRAP/CANDIDATE regime)
- the post-promotion dense-tail classify (PROMOTED regime, Phase W.2)

so a report can distinguish "the bootstrap struggled but promotion recall was fine" from "the
whole path is weak on this rendering" — these have different fixes (bootstrap ordering vs.
classify density) and conflating them would misdirect any future hardening.

### 4.3 Failure mode taxonomy (grounded in findings already on record, not invented fresh)

| Failure mode | Source finding | What this plan measures |
|---|---|---|
| Weak-cut stall | D-CG-1 (`7d036b2f`) — candidate self-scores sub-floor, stall-demote trigger also keyed on the same marginal signal, doubly stuck | Rate of `candidate_demoted_stall` events per session; whether the D-CG-1 witness fix actually fires in a LIVE session (the doc's own honest limit: "the live starvation shape did NOT reproduce offline... its live validation is the next corpus session") — **this plan is that live validation** |
| Freeze-frame transition | C1 (`7d036b2f`) — a single-frame freeze can seed a spurious CANDIDATE | Whether any session produces a `candidate_cut` that the 5s persist-timer then demotes (confirms the containment works live, not just in the synthetic test) |
| Marginal-color rendering | match3, `inline_bg_max ≈ 0.65` | Recall specifically on sessions in the marginal-color band (§3.3) vs. sessions with a clearly-separated color |
| B-instrument off-fit anchor (candidate false read) | G1' — all 7 candidates were this, zero real false reads | Not re-measured directly here (that's G1's job); noted as context for why this plan's OWN false-read escalation threshold is "any single instance," not a rate |
| **Handle collision** (new — not yet tested in this corpus) | Named in the Phase C task breakdown, not yet a finding in this repo | No natural occurrence has appeared in any session captured to date. Two options, NOT decided by this plan: (a) wait for a natural occurrence (an opponent handle textually close to `q0rtr01a30`, e.g. a lookalike with a 0/O or 1/l substitution) and flag it if one appears in the C-3.2 corpus, or (b) synthetically inject a lookalike-handle crop into the offline audit lane as a targeted test. Recommend (a) for this plan (keeps the corpus honest/unmanipulated) with (b) flagged as a future finding if C-3.2 produces zero natural instances — **this is one of this plan's open questions for review (§6)**. |

## 5. What this plan deliberately does not attempt

- **Not** a claim that the failure-mode taxonomy above is exhaustive — it is the set of failure
  modes already on record from G1'/D-CG-1/C1. New modes found during C-3.2 get added, not
  squeezed into an existing row.
- **Not** a re-tuning of any threshold (`match_floor=0.66`, `killer_max_frac=0.28`,
  `bootstrap_floor=0.55`, `stall_limit=3`) — this plan measures the CURRENT wired path as-is;
  threshold changes are a separate future decision informed by this plan's numbers, not made by it.
- **Not** a chain/on-chain measurement — KAS is `QORTROLLER-KAS-v0` CANDIDATE, off-chain; nothing
  here touches PV-CI, FROZEN-v1, or any deploy.

## 6. Open questions for review (do not resolve unilaterally)

- Handle-collision testing: natural occurrence only (§4.3 option a) or also synthetic injection
  (option b) if none appears?
- Is 2 new live sessions per rendering family (§3.3) enough for a first pass, or should the
  target be higher given how much D-CG-1/C1 hinges on live (not offline-replay) validation?
- Should the end-of-match summary-screen ground truth (§2.2) be captured via a NEW small capture
  hook, or is a manual screenshot per session sufficient for this first pass (lower engineering
  cost, same evidentiary value for N this small)?
- Do the marginal-color sessions (§3.3, deliberately-included hard case) count toward this plan's
  minimum corpus, or are they explicitly EXTRA — i.e., is the plan's core recall number reported
  only on "typical" renderings with the marginal case broken out separately, so one hard session
  doesn't dominate an aggregate the way a single 0-recall outlier could?

## 7. Deliverables (this plan's own exit criteria)

1. This document, reviewed and approved before C-3.2 begins.
2. On approval, C-3.2 runs the live-captured sessions (hardware-gated, needs operator "ready?"
   per standing rig discipline) with the §2.2 dual ground-truth capture.
3. C-3.3 consumes the resulting corpus + G1's existing archive and produces the precision
   confirmation, the per-rendering-family event-recall table (§4.2, bootstrap vs. post-promotion
   split), and the failure-mode taxonomy with live (not just offline-replay) evidence for D-CG-1
   and C1.
