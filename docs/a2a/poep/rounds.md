# ASM-Loop: F-RIG27-8 device-clock reflex latency — 2026-07-18

Task: under Remote Play the reflex latency uses bridge `t_mono` (inflated 3-15× by bursty frame
processing) → real reflexes measure 594-4600ms, never in the 80-280ms band → SYNCHRONIZED unreachable.
Fix: an ADDITIVE device-sensor-clock companion (immune to bridge processing lag) on the nonce-bound RP
verify path. Ceiling: device_ts NEVER gates the corpus/band/verdict — it is a t_mono-fallback companion
only; poep_enabled/L6B_ENABLED stay False; canonical latency_ms/classification byte-stable.

- r01 scope: RP-immune reflex clock companion | ceiling: non-gating t_mono fallback, corpus byte-stable
- r02 build: additive `crossing_device_ts` analyzer field + `_rp_device_latency_ms` helper + `_l6b_entry`
  device_ts + resolve preference | claims C1..C7 | round-rplatency-02-*
- r03 audit: F(BLOCK) `_f.timestamp_ms` is a DEAD WIRE — `InputSnapshot` has no such field → device_ts
  always 0 → device path never arms (bar 7 FAIL); + units bug (offset 28 = uint32 @3MHz ticks, not ms);
  + bar 6 PARTIAL (no wrap/frozen rail) → **HOLD** | round-rplatency-03-grok-verify.txt
- r04 fix: device ts sourced from REAL `poll()` `_states[28:32]` → new `InputSnapshot.sensor_ts_ticks`;
  raw ticks end-to-end; helper `(c-p) % _U32 / 3000` wrap-safe + uint32-range guard + frozen→0→reject;
  live-poll test drives real poll(); serialize byte-stable test; 13 device tests + 310 regression green;
  PV-CI 184; sealed l9_presence untouched. C8 = full-stream progression rail NOT built (labeled known
  limit, non-gating). | round-rplatency-04-claude-fix.md → grok re-verify pending
- r05 re-verify: **PASS** (grok independent; 13/13 + PV-CI 184; no BLOCK/WARN; INFO residuals F1-F4 only) | round-rplatency-04-grok-verify.txt
- r05 reconciliation (Claude, for record accuracy): grok's LITERAL r04 verdict string was **HOLD**,
  driven by F1 tagged BLOCK = the *wording* over-claim "arms on real hardware" (grok F2 CONFIRMS the
  code is correct: the fake `ds` does not bypass the real offset-28 unpack) + WARNs on inherent-rig
  limits (F4 silicon tick-rate unmeasured, F9 grok did not re-run the 173/112, F11 `real_hardware` set
  elsewhere) and test-depth (F3 no single end-to-end getattr-through-analyzer test). Operator ruling =
  accept-residuals PASS: the BLOCK is an over-claim not a code defect; residuals are rig-4 / re-run
  matters, not defects. Two GENUINE doc defects grok caught (F6 `(0,human_max]`→`(0,500ms]`; F8 false
  "50-byte", serialize()=56B) were FIXED post-audit (comment-only; 13/13 + PV-CI 184 re-held). F3
  (integration getattr coverage) remains an OPEN residual — cheap to close with one test if desired.
  PRE-EXISTING (not F-RIG27-8, flagged not touched): Python serialize()=56B vs firmware
  ds_input_snapshot_t=50B assert — touches FROZEN PoAC commitment; recommend separate audit.
  Honest claim ceiling: off-rig the fix is correct + unit/parse-proven; SILICON confirmation (real Edge
  populates offset 28 under RP) is rig-4, NOT claimed as done.
- r05 F3-close: extracted `_build_l6b_report(frame, accel_scale, t_mono=None)` (module-level) from the
  session-loop inline dict → the production `getattr(_f, "sensor_ts_ticks", …)` wiring is now
  production-covered by 2 new end-to-end integration tests (real InputSnapshot → _build_l6b_report →
  analyze → _rp_device_latency_ms → in-band 180ms; + absent-ticks→0→fallback). A silent getattr-name
  typo now fails a test. Behavior-identical extraction. 15 device tests + 120 session-loop regression +
  PV-CI 184 green. F3 residual CLOSED. Remaining residuals = rig-inherent only (silicon confirmation = rig-4).
- commit: (operator only — uncommitted until you fire)
