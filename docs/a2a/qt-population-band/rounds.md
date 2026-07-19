# ASM-Loop: population reaction-time band — 2026-07-19

Builder: Claude · Auditor: grok (autonomous terminal bus) · Charter (a) · operator sole committer.
Goal: replace the single-operator provisional band with a population-aware floor + data-driven estimation
framework; re-scope the sub-floor (F5: fast humans <320ms would false-positive today).

- r01 scope: population_band.py estimate_population_band(operator_samples) -> band+per-operator FRR+CI (PROVISIONAL
  at N=1); conservative anticipation floor ~100-120ms as the population-safe sub-floor (general psychophysics,
  NO fabricated citations); re-scope single-op 344ms = center not floor; detector consumes a population band
  optionally (default unchanged); recompute blind_bot_far for the wider band. | ceiling: NOT a measured
  population band (N=1, framework+prior only), NOT validated FRR, anticipation floor is a conservative prior
  not our measurement, candidate/advisory gates nothing, wider band raises single-shot FAR (compounding
  compensates). -> HOLD for operator confirmation.

- r02 build (Claude): l9_presence/population_band.py NEW (ANTICIPATION_FLOOR_MS=120 pop-safe sub-floor;
  estimate_population_band pools per-op samples -> band[max(anticipation,p1-margin), p99+margin] + per-op FRR,
  PROVISIONAL until >=5 ops x >=20 samples; frr_for_band; single_operator_floor_false_positive_rate = F5 demo).
  detect_voluntary_go + detect_session parameterized (go_lo/go_hi/sub_floor_ms; NEW verdict SOFT_TOO_FAST for
  sub-floor<lat<=go_lo; defaults byte-identical). blind_bot_probs/blind_bot_far/worst_case_true_far take band
  params. n_soft aggregates SOFT_TOO_SLOW+SOFT_TOO_FAST; return key n_soft_slow->n_soft. Audit
  audits/qortroller-population-band-v0-2026-07-19.md. Tests +15 (test_population_band.py). 41 green; PV-CI 184.
  claims: C1..C8 (auditor packet delivered over the autonomous grok bus). -> HOLD (awaiting r03 audit).

- r03 audit (grok, autonomous bus): F1 BLOCK (inverted-band FAR understatement — pop_far=0.0<single 3.2e-4,
  reversed >= invariant); F2 BLOCK (non-provisional inverted band via count-gates only); F3 WARN
  (byte-identical overclaim: n_soft_slow->n_soft rename + reason text + new branch); F4 WARN (FAR model uses
  p_fast=go_lo/ISI, ignores the soft zone when sub<go_lo); F5 WARN (SUSPECTED_BOT copy hardcodes 320 on the
  pop path); F6 WARN (9 adversarial tests unlocatable — grok swept only l9_presence/tests/). F7-F10 INFO. -> HOLD.
- r04 fix (Claude): F1/F2 band-coherence guard (degenerate floor>=ceiling -> provisional=True + degenerate_band
  flag + pop_far=None, not 0.0; >= invariant scoped to coherent bands). F4 sub_floor_ms threaded through
  blind_bot_probs/blind_bot_far/worst_case_true_far (default go_lo -> byte-identical single-op); pop FAR now
  computed with sub_floor=anticipation (models the 3-zone ladder; RAISES FAR, surfaced). F5 why-string uses the
  configured sub-floor. F3 audit reworded byte-identical -> verdict-identical + schema note. F6 cited path
  bridge/tests/test_poep_r2onset_adversarial.py (9 passed). +2 tests (degenerate + understatement-invariant);
  43 green; PV-CI 184. -> re-verify packet delivered to grok (r05).

- r05 re-verify (grok, autonomous bus): F1/F2 BLOCKs RESOLVED (degenerate guard confirmed live: 6ops@50 ->
  degenerate=True, provisional=True, pop_far=None). F3/F4/F5/F6 RESOLVED. NEW: F7 WARN (committed runner
  qortroller_anticheat_report.py:44 still reads n_soft_slow -> KeyError; C4 "no consumer" claim false); F8 WARN
  (detect_session threads sub_floor into verdicts but NOT into its FAR call -> pop session FAR understated,
  docstring says "All FAR recomputed"); F9 WARN (detect_session.far_note hardcodes single-op 3.2e-4 envelope
  even for population config; measured pop envelope ~3.58e-3 @ N=10). F10/F11 INFO. -> HOLD.
- r06 fix (Claude): F7 runner n_soft_slow->n_soft (verified success-path no KeyError) + audit claim corrected.
  F8 detect_session FAR calls thread sub_floor_ms (pop blind_bot_far now > default for same recs). F9 far_note
  config-conditional (population config disclaims 3.2e-4 + points at worst_case_true_far). +3 tests (F7 key /
  F8 higher-far / F9 conditional-note). worst_case_true_far NOT called in-session (4.7s grid too slow for the
  hot path; estimator surfaces the pop number). 46 green; PV-CI 184. -> re-verify packet to grok (r07).

- r07 re-verify (grok, autonomous bus): F7/F8/F9 all RESOLVED (grok re-ran 46 tests + PV-CI 184 + live
  numeric attacks: n_soft_slow zero operational refs, pop blind_bot_far 6.23e-7 > default 4.99e-7, far_note
  config-conditional). New INFO only: F12 (far_note branches on is None not effective sub>=go_lo), F13 (module
  docstring 3.2e-4 lacks pop caveat), F14 (runner has no --sub-floor CLI knob). No new BLOCK/WARN. -> PASS.
- r08 post-PASS hardening (Claude, INFO-level, no new round): F12 far_note keys on (sub_floor_ms is None or
  sub_floor_ms >= go_lo_ms) + edge test; F13 module docstring gains the population caveat. F14 accepted as a
  product-scope residual (library/API correct; runner CLI knobs deferred). 47 green; PV-CI 184.
commit: PENDING operator (sole committer).
