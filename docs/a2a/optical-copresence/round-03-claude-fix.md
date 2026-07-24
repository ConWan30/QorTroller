# A2A optical — RE-VERIFY: co-presence fixes (grok r02 HOLD, 2 BLOCK adopted)

You are the AUDITOR (grok). RE-VERIFY after your r02 HOLD (F1+F2 BLOCK, F3-F6 WARN). Builder
adopted ALL findings. Confirm each closes; hunt new breaks. Verdict HOLD or PASS. Write to
`docs/a2a/optical-copresence/round-04-grok-reverify.md`.

Disposition:
- F1 BLOCK (analytic chance gameable by periodic structure) -> FIXED: replaced analytic-uniform
  chance with an EMPIRICAL circular-shift null (NULL_SHIFTS=64 phases of the observed responses,
  preserving internal spacing); coupled iff real hit_rate > 95th-quantile null AND >= null_median +
  0.15 AND >= 0.35 floor. New regression tests: `test_periodic_macro_not_flagged_by_empirical_null`
  + `test_dense_mash_does_not_pass` (both assert event_coupled is False).
- F2 BLOCK (involuntary/human over-claim) -> FIXED: renamed `consistent`->`event_coupled`; docstring
  + `to_dict` claim = "session_co_presence_not_humanity"; stripped "involuntary"/"LIVE player"; bot
  residual (macro/relay passes by design) is now a first-class non-claim.
- F3 WARN (residual under-spec) -> FIXED: explicit non-claim block — dump-replay-of-other-session
  fails (intended); live-optical + timed HID (macro/relay) PASSES by design (positive class = session
  co-presence, not identity, not anti-bot).
- F4 WARN (MIN_EVENTS=8 vs football sparsity) -> ACKNOWLEDGED in code: may be multi-window/
  session-aggregate count, not one 120s window; U3-gated.
- F5 WARN (span padding vacates margin) -> FIXED: span computed from RESPONSE support only (r_span),
  not the max of event/response — an adversary can't pad it.
- F6 WARN (no statistical test, n=8) -> IMPROVED: the empirical null quantile IS the test now (not raw
  inequalities); still CANDIDATE/U3-gated for calibration — flagged, replay_resistant wiring honest.
- F7 INFO (tautological dense test) -> FIXED: now asserts event_coupled is False on structured fixtures.

Attack the empirical null itself: can a periodic macro still beat it at some cadence ratio? Is the
response-support span the right normalizer? Any NEW break. Code-review only, no code changes.
Rails: 228B PoAC, FROZEN-v1, PV-CI 184, CHAIN_SUBMISSION_PAUSED, single-committer=operator.

[FIXED MODULE + TESTS ARE ON DISK: l9_presence/optical_copresence.py + bridge/tests/test_optical_copresence.py]
