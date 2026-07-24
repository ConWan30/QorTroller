# Third CFB 27 rig session — 2026-07-18 (LEAN mode + full pipeline works; F-RIG27-8 latency finding)

**Setup:** campaign env + `L6B_PROBE_HOLD_MS=500` + `POEP_FIRE_TIMEOUT_S=20`; Edge USB->PC active host;
PS Remote Play -> PS5; CFB 27 live. Shell B run by Claude (operator-authorized; key from bridge/.env
never printed). Zero spend; no flag flips; kill-switch verified; L6B_ENABLED/poep_enabled stayed False.

## Two WINS
- **F-RIG27-7 FIXED — LEAN campaign mode.** The first launch starved the event loop (loop_health:
  42 starvation events, max excess 61.85s; capture=DISCONNECTED, HTTP timing out) under the heavy
  retina/DA/replay/nqpv lane (14 flags on in bridge/.env: RETINA_GAME_CAPTURE, PERCEPTION, DA_UPLOAD,
  DA_WITNESS, PDA, W3BSTREAM, CAPTURE_BURST + REPLAY_PROOF_PIPELINE + NQPV_COCAPTURE + DUAL_GRIND_TETHER)
  — the exact WGC-vs-RP-decoder contention the 2026-06-27 lean-mode arc measured. Relaunched with those
  flags forced OFF via process env (load_dotenv override=False confirmed -> process env wins over .env,
  bridge/.env untouched): **LOOP STARVATION 42->~2, DA uploads flood->0, retina WGC->0, capture=NOMINAL,
  HTTP fast.** The PoEP ring needs none of that lane; lean is the RP-compatible path (+ smoother gameplay).
- **F-RIG27-6 FIXED (confirmed) + the ENTIRE PIPELINE WORKS END-TO-END for the first time.** Under lean
  + the 20s timeout, all **8 nonce-bound fires completed**: dispatched -> real HID write -> IMU capture
  (~420 samples) -> analyze `error=ok` -> Future resolved `real_hardware=True` -> client confirmed ->
  GO recorded. `n_go_issued=8, effective_live=True, live_hardware=True`. The resolve-INFO instrument
  (F-RIG27-6) worked exactly as designed — every fire logged nonce/lat/peak/post_n/error.

## NEW FINDING — F-RIG27-8 (the honest wall; why verify still fails)
`n_go_verify_pass=0` -> IDENTITY_ONLY. The reflex CONTENT is real and strong (peaks 615, 3028, 290,
4450, 6597, 3889, 4760, 1120 — textbook hard grip-jerks, operator reacting cleanly), analyze `error=ok`
every time. But EVERY measured latency is 3-15x out of the 80-280ms human band: 940, 694, -1, 873,
3040, 1047, 594, 4600 ms. A 6597-peak reflex "at 3040ms" is physically impossible as a reaction time
-> this is a MEASUREMENT issue, not operator timing.

**Grounded root cause:** `bridge/controller/l6b_reflex_analyzer.py` computes
`true_latency_ms = (crossing_t_mono - probe_ts)` where `t_mono = time.monotonic()` stamped when the
BRIDGE PROCESSES each frame (session loop builds `_l6b_entry` with `t_mono`), NOT the controller's
device sensor timestamp. Under Remote Play the bridge reads IMU frames in laggy BURSTS (the 350-frame
window spans ~9s wall-clock, post_n~420), so the crossing frame's `t_mono` lands far after the physical
reflex -> latency inflated. The device HAS a precise timestamp (offset 28, uint32 @3MHz) — the l2_ads
path already extracts it — but the reflex analyzer uses bridge wall-clock. **RP gives live input CONTENT
(broke the dual-connect blind) but corrupts input TIMING; the 80-280ms band was calibrated on tight
direct-USB frame delivery.**

### Fix space (next A2A loop — round-rplatency):
- (a) Use the DEVICE sensor timestamp for reflex latency (immune to bridge/RP processing lag; the
  timing-authoritative source; but the 220-usable corpus was computed with t_mono -> the band may need
  recalibration against device-ts).
- (b) Require direct-USB (PC game) for reflex-VERIFY while RP handles presence CONTENT (topology split).
- (c) Verify on peak+shape (not latency) under RP (weaker; latency is the human-band discriminator).
- Also weigh the 500ms rigid hold vs the corpus capture params (mode=rigid seen in log; corpus was pulse).

## Corpus / SYNCHRONIZED status
Corpus unchanged (220/197 MET). Note: the 8 fires all had policy_ref=edge_operator_reflex_v1 but
verify_pass=0 -> whether they inserted usable rows depends on is_usable_reflex (latency out-of-band ->
NOT usable; peaks fine but latency artifact). SYNCHRONIZED_CONTROLLER not reached: the last gate
(reflex latency in-band) is blocked by F-RIG27-8, a measurement-timing question, not a pipeline gap.

## Wrap
Bridge stopped clean; demo artifacts purged. No code changed this session (the fixes were the lean
env-launch + already-committed d09d1547/31de44f2). Next: F-RIG27-8 via A2A loop (round-rplatency) —
device-ts latency vs topology-split vs recalibration -> then Shell B verify-passes -> first SYNCHRONIZED.
