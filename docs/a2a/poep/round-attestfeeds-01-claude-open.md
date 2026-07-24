# A2A ATTEST-FEEDS r01 - CLAUDE OPEN (F-RIG27-1/2: the two false-negative attestation feeds)

**Micro-arc:** fix the two feeds that held Shell B on the first CFB 27 rig session
(`audits/rig-session-cfb27-first-2026-07-18.md`) so the next session can honestly reach
`SYNCHRONIZED_CONTROLLER`. Charter ruling (a). **Spend: ZERO; no flag flips; sealed l9 modules +
challenge_live/classify_activity byte-untouched; PV-CI 184.**

---

## F-RIG27-1 - PCC rate-counter starvation (GROUNDED root cause)

`dualshock_integration.py` ~1702-1710: the session loop prefers the side hidapi counter's delta over
`len(frames)`, guarded by `self._hid_counter_thread.is_alive()`. Last session the thread was **ALIVE
but SILENT** (0 reports under the RP topology while the MAIN reader minted 448 records) -> `_delta=0`
fed every iteration -> rate 0 -> DISCONNECTED -> the CLI's PCC gate refuses. **The designed
`len(frames)` fallback never engaged because aliveness != productivity.**

Complication: the fallback's `len(frames)` is capped ~120Hz (dt_ms=8 in `_poll_frames`) -> yields
DEGRADED (NOMINAL needs >=950Hz) -> the sealed PCC gate STILL refuses. So the honest fix has layers:
- **(1a)** silent-counter detection: N consecutive zero-delta iterations WHILE `frames` flow ->
  trigger the EXISTING self-healing restart machinery (`_hid_counter_restarts`, ~883) - bounded.
- **(1b)** while silent: feed `len(frames)` (honest degraded telemetry, better than fabricated 0) +
  surface `rate_counter_stalled: true` on capture-health (visibility, not papering).
- **(1c)** the OPEN empirical question: does a counter restart re-attach under RP? Unknown until the
  next rig. If it structurally cannot, NOMINAL is unreachable under RP and that truth must surface -
  options then: an operator-acked PCC source config (main-reader cadence as the attested source with
  its own NOMINAL band), never a silent threshold loosening.

## F-RIG27-2 - live activity surface (GROUNDED)

`agent_grind.py` ~118: `latest_gameplay_context` comes ONLY from the store's ruling summary
(adjudication-time stamps; no adjudicator in campaign config -> never stamps). BUT the transport
ALREADY tracks live `trigger_active` per iteration (~1676, `_spc_kwargs` into the PCC SPC binding).
**Proposed:** transport keeps a rolling window (deque, last N iterations' trigger_active bits) ->
expose `live_trigger_active_fraction` (+ window size + `live_activity_source: "bridge_main_reader"`)
on capture-health -> the attach CLI's activity fetcher maps it to `{"trigger_active_fraction": v}` -
which the SEALED `classify_activity` already accepts (>0 -> ACTIVE_GAMEPLAY; ==0 -> MENU; absent ->
UNKNOWN). No sealed edit; no GAD/ruling change; the same reader that fires attests activity.

## grok r02 FORWARD - weigh
- **A.** F-RIG27-1 layering (1a restart + 1b honest-degraded + 1c surface-the-truth): right shape?
  Is feeding len(frames) while stalled honest telemetry or a masking risk? Should DEGRADED-under-
  fallback be visible as its own capture-health field?
- **B.** F-RIG27-2: rolling-window fraction on capture-health + CLI mapping to the sealed
  classifier's existing grammar - any fabrication seam? Window size (my lean: last ~20 iterations
  ~= the GAD evidence-window spirit)? Should MENU (fraction==0) be distinguishable from
  no-window-yet (absent field -> UNKNOWN)?
- **C.** The PCC gate question: with 1b in place the state may be DEGRADED not NOMINAL under a
  stalled counter - the sealed pcc gate (`NOMINAL` + EXCLUSIVE_USB/UNKNOWN) would still refuse.
  Hold that line (fires wait for a true-rate recovery), or is there an honest operator-acked path?
- **D.** Fabrication hunt: can a stalled-counter fallback or the live fraction be gamed into a
  false-positive attestation (idle pad reading ACTIVE, disconnected pad reading NOMINAL)?
- **E.** Test shape (no rig in CI: fakes for the counter thread + frames) + the r03 bars.

## Sequencing
r01 (this) -> grok r02 FORWARD -> build (transport + agent_grind + CLI fetcher + tests) -> r03 verify
-> operator commits -> next rig session: eye-check the feeds live, then Shell B.
