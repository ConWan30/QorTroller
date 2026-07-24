# Second CFB 27 rig session — 2026-07-18 (attest-feeds validation + first ring fires)

**Setup:** bridge under `POEP_CAMPAIGN_MODE=true` + `POEP_LIVE_FIRE_ENABLED=1` +
`GAME_PROFILE_ID=ncaa_cfb_27` + `L6B_PROBE_HOLD_MS=500` (perceptible reaction pulse); Edge
`581a836c…` USB->PC active host; PS Remote Play -> PS5; CFB 27 live. Shell B run by Claude
(operator-authorized; key from bridge/.env, never printed). Zero spend; no flag flips; kill-switch
verified suppressing tx live; `L6B_ENABLED`/`poep_enabled` stayed False.

## Banked wins — BOTH attest-feeds fixes (d09d1547) CONFIRMED LIVE
- **F-RIG27-1 FIXED (confirmed):** the interface-3 rate counter attached cleanly this run
  (`Phase 235-PCC-RATE-FIX: hidapi rate counter live on interface 3`) -> `capture_state=NOMINAL`,
  `host_state=EXCLUSIVE_USB`, `poll_rate_hz` 1592->2379, `rate_counter_stalled=False`,
  `rate_source=hid_interface3`, `hid_counter_restarts=0`. **The PCC gate went GREEN** — no stall
  under RP this session (the healer stayed armed but unneeded). The 1c question (does RP starve the
  counter?) answered NEGATIVE this run.
- **F-RIG27-2 FIXED (confirmed):** the live activity surface greened — `live_trigger_active_fraction`
  0.0 -> 0.1 within the first poll of play, `live_activity_window_n=20`,
  `live_activity_source=bridge_main_reader`. The CLI mapped it -> the sealed classifier ->
  ACTIVE_GAMEPLAY -> `activity_source=bridge`, `gameplay_active_fraction=1.0`, `n_activity_samples=3`
  in the summary. **The activity gate went GREEN without any adjudicator** — exactly the design.
- **The ring fires REACH the pad end-to-end under RP:** 3 nonce-bound probes dispatched
  (`POEP-HID-RING: nonce-bound probe dispatched mode=rigid r2_force=60`), `_l6b_pending` armed +
  cleared between each (no 409). 734 verified PoAC records (RP topology holding), 20 presence bursts.

## NEW FINDING — F-RIG27-6 (the honest hold this session)
Verdict `IDENTITY_ONLY`, `n_go_issued=0` despite 3 real dispatches. Root cause (bounded from
evidence): the endpoint awaits the fire Future with a **5.0s timeout** (`operator_api/_app.py:1422`);
the capture window is `frames_remaining=350` drained by `len(frames)` per ~1s session-loop
iteration. **Under Remote Play the frame cadence into the L6b buffer is slower than direct-USB, so
the 350-frame drain takes >5s** (bounded 5-11s: the client 504'd, yet the next probe ~11s later was
not 409-blocked -> pending cleared in that window). POST times out -> client honestly returns
`fired=False` -> no GO recorded -> IDENTITY_ONLY. **No l6b_probe_log rows inserted** (newest row
still 2026-07-17), consistent with late/failed completion under RP frame starvation.

**This is a win-shaped finding:** the entire ring path works end-to-end under RP — fire dispatches,
real probe fires, pending arms/clears — the ONLY gap is the 5s POST timeout is tuned for direct-USB
drain speed, not RP's slower delivery. The honesty rails held perfectly: no fabricated pass.

### Fix candidates (next arc — A2A loop, grok forward+verify; operator picked B = do it right)
- Raise the endpoint `wait_for` timeout to match RP drain (~15s; probes already spaced ~11s) — the
  simplest; only makes the handler wait longer for a REAL confirmed fire (rails unchanged). OR
- Make the capture window frame-count adaptive to the observed frame cadence (measure len(frames)/
  iter; drain in wall-time not frame-count) — more robust but a bigger, tuning-sensitive change.
- Open sub-question: did the completion's `analyze` ALSO fail under RP (no clean reflex -> would need
  a physics look at the RP post-buffer)? The zero DB rows can't distinguish late-completion from
  analyze-fail; the next arc instruments the completion (INFO log the resolve outcome).

## Corpus status
Unchanged: Edge usable 220 / independent 197 (gate MET). No new reflex rows this session (fires
didn't complete -> no inserts). Corpus growth resumes when F-RIG27-6 lands and fires complete.

## Wrap
Bridge stopped clean; demo artifact purged (gitignored). No code changed this session (attest-feeds
fixes were already committed at d09d1547 and are now LIVE-VALIDATED). Next: F-RIG27-6 via the A2A
loop -> Shell B completes -> first SYNCHRONIZED_CONTROLLER + corpus growth.
