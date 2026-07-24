# ASM-Loop: the exclusive QorTroller anti-cheat detector — 2026-07-19

Builder: Claude · Auditor: grok (operator-ferried) · Charter (a) · operator sole committer.
Goal: session-level detector from nonce-bound R2-onset haptic challenges -> honest live-human verdict,
exclusive to the certified DualSense Edge (silicon-clock + physical-haptic + nonce binding).

- r01 scope: multi-challenge detector composing detect_voluntary_go + K-of-N aggregator; defeat the
  fixed-delay bot via unobservable-challenge compounding FAR=(band/ISI)^K | ceiling: voluntary-reaction
  liveness CANDIDATE, single-operator provisional band, hardware-class "exclusive" (NOT unbreakable),
  fire-time-observing bot + crypto-binding are published rig/crypto residuals; poep_enabled/L6B stay False.
  -> HOLD for operator confirmation.
- r02 build: l9_presence/qortroller_anticheat.py (detect_session) + scripts/qortroller_anticheat_report.py
  runner + l9_presence/tests/test_qortroller_anticheat.py (10) + audits/qortroller-anticheat-v0-2026-07-19.md.
  Live: N=35 real dumps -> HUMAN_PRESENT, GO=18>=thr7, blind-bot FAR=3.34e-05; controls: blind-bot->not human,
  sub-floor->SUSPECTED_BOT, dead->DEAD_FEED, observing-bot->HUMAN_PRESENT (published residual). PV-CI 184.
  claims C1..C11 -> auditor packet issued, HOLD.
- r03 audit (grok): F1(BLOCK peak FAR wrong: true N=25 not N=20) F2(BLOCK "exact" binom != session FAR)
  F3/F4/F5/F6/F7/F8/F9/F10/F11/F12/F13 (WARN/INFO) -> HOLD.
- r04 fix: F1 corrected peak to N=25 (true 4.55e-5 / binomUB 4.58e-4) in code+audit+test; F2 added TRUE
  multinomial blind_bot_far (zero-sub-floor) + kept binom as labeled loose UB, both reported; F3 docstring
  "shrinks"->"non-monotone, concentrates beyond crossover"; F5 "impossible for a human"->"provisional floor
  heuristic"; F6 audit relabels live N=35 as operator-machine, not committed-reproducible; F9 measures+reports
  observed_isi_ms + FAR labeled ISI-conditional; F10 module title+audit demoted to hardware-class candidate/
  advisory; F13 residual_note discloses timing-only synthetic-gold privilege; F4 proxy-gold noted; F12 noted
  uncommitted. 14 fixture tests + PV-CI 184. Autonomous re-verify -> grok.
- r05 re-verify (grok): F1/F2 BLOCKs CLEARED; NEW F14(WARN module lead still teaches binom as THE FAR +
  2.8%->2.67%) F15(WARN RATE_MIN comment still "shrinks") F16(WARN material: far_note/docstring/audit say
  rapid cadence RAISES true FAR but it LOWERS it via sub-floor trap; TRUE FAR non-monotone in ISI, joint
  worst ~1.4e-4) F17(INFO exclusive on test/runner titles) F18(INFO blind_bot_probs p_go+p_fast>1 for ISI<GO_HI)
  -> HOLD.
- r06 fix: F14 module "why it works" reworded TRUE multinomial primary + binom labeled UB + 2.67%; F15 comment
  -> non-monotone; F16 far_note+blind_bot_far docstring+audit ISI section corrected (rapid raises p_go AND
  p_fast; TRUE FAR non-monotone in ISI; joint worst-case 1.4e-4 @ISI500/N6 disclosed) + test peak500>peak3000;
  F17 test+runner titles demoted; F18 intersection measure p_go+p_fast<=1 + test. 16 fixture tests + PV-CI 184.
  Autonomous re-verify -> grok (r07).
- r07 re-verify (grok): F14/F15/F17/F18 CLEARED; F16 NOT cleared -> F19(MATERIAL: joint worst-case understated;
  true global max 3.20e-4 @ N=5 ISI=400=GO_HI = (band/GO_HI)^K = 0.2^5, ~2.2x the disclosed 1.4e-4) + F20(WARN
  "short ISI lowers true FAR" needs N-scope) + F21(INFO stale "14 tests"/version) -> HOLD.
- r08 fix: F19 added worst_case_true_far() code-derived joint max (analytic (band/GO_HI)^K at N=K,ISI=GO_HI) +
  fixed blind_bot_far docstring + far_note + audit table/§ISI to 3.20e-4 @ N=5/ISI=400 + a test pinning it
  (far>=3e-4, ==analytic, N=K, ISI~GO_HI); F20 scoped "short ISI lowers" to LARGE fixed N + noted joint
  adversary picks small N + ISI~GO_HI; F21 audit -> 17 tests + version r02->r08 + FAR-vs-N header scoped to
  fixed ISI=3s. 17 fixture tests + PV-CI 184. Autonomous re-verify -> grok (r09).
- r09 re-verify (grok): F19/F20/F21 RESOLVED (grok's own 1ms dense grid + analytic proof confirm the global
  max = (band/GO_HI)^K = 3.20e-4 @ N=5/ISI=400; test pins it). 2 INFO residuals (module N~=25 fixed-ISI scope;
  audit "10x lower" scope) -> tightened in code+audit post-PASS. VERDICT: **PASS**. HOLD cleared.
- r10 post-PASS tighten (INFO, non-blocking): module docstring N~=25 scoped "AT FIXED ISI" + joint-max line;
  audit "~10x lower" scoped "at fixed ISI=3s (coincide at joint max)". 17 tests + PV-CI 184.
- FINAL: 9 A2A rounds (r01 scope -> r02 build -> r03 audit HOLD -> r04 fix -> r05 re-verify(2 blocks cleared,
  new WARNs) -> r06 fix -> r07 re-verify(new F16/F19) -> r08 fix -> r09 PASS). Autonomous grok bus used for
  r05/r07/r09. Awaiting operator commit.
