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
- commit: c7ba84b7 (F-RIG27-8, operator-fired) + 782df5a9 (SYNC-GO, operator-fired)
- rig-4 (LIVE 2026-07-18): 9 real-hardware fires under RP → `dev_lat=-1.0` on ALL; t_mono floors ~1.2s
  (tracks reaction: 4.7s natural → 1.2s big-jerk); clean trigger reflex invisible to IMU accel
  (peaks 62–459 < threshold). SYNCHRONIZED not reached; honest IDENTITY_ONLY (n_go_issued=1). The device
  clock is DEAD on silicon under RP (or span>500ms — not yet split). Banked:
  `audits/rig-session-cfb27-4-2026-07-18.md`. Next: (i) raw-tick log, (ii) R2-analog reflex, (iii) accel threshold.
- r06 (F-RIG27-8b raw-tick instrumentation — log-only, non-gating): `cross_ts`/`probe_ts` added to the
  `POEP-HID-RING: resolve` INFO line so ONE rig fire splits dead-wire (both ~0) vs span-reject
  (both large, span>500ms). grok 8b verify = **SHIP** + 1 NIT (`probe_ts` re-read) → NIT APPLIED (both raw
  ticks hoisted into locals + passed as params → log == exact `_rp_device_latency_ms` inputs). 38 tests +
  PV-CI 184. Envelope `round-rplatency-8b-envelope.md`; grok raw `scratchpad/grok-rplatency-8b-verify.txt`.
  **STAGED — operator commits.**

## ASM-Loop continuation — batch-boundary claim, 2026-07-20

r01 scope: investigate why live-ring reflex latencies (900-4600ms, both t_mono and a
companion device-clock span) never fall in the sealed GO band (195,416]ms across tonight's
7 real fires, given F-RIG27-8 already named process-time `t_mono` inflation and a no-RP
retest tonight showed the same magnitude | ceiling: static code-investigation only, no
live fires this round, no fix implemented/tested.

r02 build: `dualshock_integration.py` session-loop batching read (`_session_loop`/
`_poll_frames`/`request_poep_nonce_probe`) + `logs/l6b_probe_diagnostic.jsonl` evidence |
claims C1..C10: session-loop batches HID in ~1s blocking windows via `_poll_frames`, fire
path unsynchronized to batch boundary, framed as a NEW root cause distinct from F-RIG27-8,
"directly explained" by diagnostic rows 1557/1585 plus a claimed device-clock agreement.

r03 audit: grok, invoked directly via CLI terminal bus (`grok --prompt-file`, no manual
copy-paste this round) →
- F1 (BLOCK): crossing lands early in post-fire buffer (`crossing_index=0`/`3`) — refutes
  "waited for a later batch to find the peak"; real mechanism is `_build_l6b_report`
  stamping `t_mono` at classification time, not capture time
- F2 (BLOCK): not a new root cause — same mechanism F-RIG27-8 already named; ~1s batching
  is a contributing lag source, not an independent second cause
- F3 (BLOCK): device-clock-agreement claim doesn't hold in code — `_rp_device_latency_ms`
  fail-closes above 500ms and falls back to the already-inflated mono path
- F4/F5 (WARN): `frames_remaining=350` at ~8ms/frame is multi-second, not a ~1s residual;
  mid-batch arming can route pre-fire frames into the post buffer (contamination surface,
  no per-frame `t_mono >= probe_ts` gate at buffer-append time)
- F6/F7 (WARN): "consistently 900-4600ms" may be a selected subset (a 279ms HUMAN row
  exists same night); RP-independence claim not re-verifiable from cited artifacts
- F8/F9/F10 (INFO): control-flow facts (C1-C3, C8-C9) check out; fix options honestly
  design-only; GO band (195,416]ms uncontested
→ verdict **HOLD**

r04 fix: retracted C4/C5/C7's "new, dual-clock-confirmed root cause" framing in
`docs/poep-live-play-ring-arc-spec.md` INC-3; corrected to "F-RIG27-8 confirmed and
refined, not superseded" — `_build_l6b_report`'s process-time `t_mono` stamping is the
mechanism, ~1s `_poll_frames` batching is a contributing lag source, the device-clock-
agreement comparison removed as unverified against the live code path. F4/F5 retained as
open leads for a future build round (stamp `t_mono` at collection time inside
`_poll_frames`, not at classification time; gate post-buffer append on `t_mono >=
probe_ts` to prevent pre-fire contamination). No code fix attempted this round — matches
the r01 ceiling.

r05 re-verify: not run this round — this is a documentation retraction against an
already-issued HOLD, not a new build; no further live fires attempted per the r01 ceiling.

commit: feed4495 (operator-fired)

## ASM-Loop continuation — build the two open leads, 2026-07-20

r01 scope: build the two leads the prior HOLD left open: (a) stamp `t_mono` at frame-
collection time inside `_poll_frames`, not at classification time; (b) gate post-buffer
append on the frame's actual collection time vs `probe_ts` (pre-fire contamination gate).
Operator instruction: run through ASM-Loop before touching the rig again.

r02 build: `_poll_frames` now captures `time.monotonic()` immediately after each
`poll()` returns, stored 1:1-aligned as `self._frame_collect_t_mono`; session-loop L6b
entry-build passes that stamp into `_build_l6b_report(t_mono=...)`; new branch routes a
frame to `_l6b_pre_buffer` even when `_l6b_pending` is armed if its own collection stamp
predates `probe_ts`; `frames_remaining` decrements by post-appended count, not
`len(frames)`. Claims C1-C10 (stamp wiring, contamination gate, defensive length-mismatch
fallback, decrement correction, additive-on-common-path, regression scope, explicit
non-claims: 350ms magnitude bug not touched, no live-rig confirmation).

r03 audit: grok, direct CLI → **HOLD**, all WARN-tier (no BLOCK): F2/F8 the new stamp
wiring and contamination gate shipped as call-site glue with ZERO dedicated tests; F3 the
length-mismatch fallback degrades silently (no log); F7 "ADDITIVE/behavior-preserving"
claim over-reads — t_mono VALUES do change on the common path, that's the actual fix, not
a no-op; F1/F5/F6/F9/F10 INFO, hold clean.

r04 fix: extracted the session-loop's inline classification into a new pure module-level
function `_classify_l6b_batch(frames, collect_t_mono, accel_scale, pending)` (same
extraction rationale as `_build_l6b_report`'s own precedent) — closes F2/F8 by making the
new logic directly unit-testable without session-loop/asyncio scaffolding. Added
`log.warning` on the length-mismatch fallback path before degrading (closes F3). Rewrote
the call-site comment to state plainly that t_mono values change on the common path even
though routing/decrement don't (closes F7's wording precision). 7 new tests in
`test_rp_device_latency.py`: all-pre-unarmed, all-post-armed-before-batch, the
contamination-gate split itself, collection-stamp carry-through, length-mismatch
fallback+log assertion, None-stamp-never-gates-into-pre, and a `_poll_frames`-level
alignment test (unbound-method pattern, matching `test_poep_hidring_fire.py`
convention). 49/49 relevant tests green, PV-CI 184 held. F4(c) (pre_reports snapshot
staleness), F9 (350ms magnitude bug), F10 (live-rig confirmation) explicitly NOT
touched — named as deferred, not claimed fixed.

r05 re-verify: grok, direct CLI, re-read the live tree + re-ran all tests independently
→ **PASS**. F2/F3/F7/F8 disposition FIXED (verified against actual code+tests, not
builder's claims); F4/F9/F10 disposition STILL-OPEN, correctly left as accepted residuals
never claimed closed. No new regressions, no FROZEN/PV-CI drift, no letter-vs-spirit gaps
found (checked: no leftover inline classification path, tests call production code not
reimplementations, boundary `t_mono == probe_ts` routes post/conservative).

commit: staged by builder, operator commits.
