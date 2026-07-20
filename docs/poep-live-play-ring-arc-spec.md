# POEP live-play ring arc — spec (what earns `poep_enabled`) · 2026-07-20

**Correction 2026-07-20 (post-INC-0 empirical fire):** every `/operator/poep/fire` reference below is
the wrong URL — this doc assumed a single `/operator/` prefix before the endpoint was ever actually
tested. The real, working path is **`/operator/operator/poep/fire`** (doubled prefix: the sub-app is
mounted at `/operator` in `main.py`, and the route itself is declared as `/operator/poep/fire` inside
that sub-app — an established, already-integrated convention, not a defect to fix here).
`l9_presence/poep_bridge_fire_adapter.py` already uses the doubled path with its own comment
documenting why; `audits/rig-session-cfb27-first-2026-07-18.md` and two other rig-session docs
independently confirm it from real hardware sessions. Left as-is by operator decision 2026-07-20 —
changing the server route would break the already-working client + break continuity with prior
hardware-fire records.

**Goal:** reach **SYNCHRONIZED_CONTROLLER under REAL gameplay** — a live human, proven present by a
nonce-bound haptic reflex *while actually playing a game* — which is the presence proof `poep_enabled` gates.
Everything to date proved presence **at a desk with the game OFF** (exclusive-HID reflex captures); this arc
proves it **during play**. Candidate/campaign throughout; flips NOTHING until the arc completes + operator seal.

## Why the desk path doesn't earn it (the topology crux)
- The desk reflex path (`poep_live_capture.py`) needs **exclusive HID** — it REFUSES to fire while the bridge
  holds the pad (dual-writer). So it can't run during a live bridge session.
- Under real play the pad is **USB→PC + BT→PS5** (Remote Play). The **dual-connection blind** (which cost us
  an hour tonight — the PS5 owns the pad's output over BT) means a second process can't cleanly fire the
  trigger while the PS5 is the active host.
- Therefore the honest live-play path is the **single-HID bridge fire+IMU ring**: the bridge owns the pad
  (USB reader) AND serves the fire AND captures the IMU/reflex — all from ONE reader. No dual-writer, no
  second process fighting for the trigger.

## What already EXISTS (reuse, do not rebuild) — commit `92f6e848`
- `DualShockTransport.request_poep_nonce_probe(nonce, amplitude)` — nonce-bound probe served from the
  bridge's OWN reader (fail-closed: `POEP_LIVE_FIRE_ENABLED=1` + `l6b_enabled` + driver + controller; 409 busy).
- `POST /operator/operator/poep/fire` (doubled-prefix — see correction above) — operator endpoint (arms
  `_l6b_pending` w/ nonce + Future, awaits w/ timeout).
- The bridge's single-reader ring under `l6b_enabled`: `_l6b_pre_buffer` → `_l6_driver` fire →
  `_l6b_post_buffer` → `_l6b_analyzer` → `_l6b_pending`; two-way auto-tick exclusion (F-HIDRING-1 fixed, r04).
- Client `l9_presence/poep_bridge_fire_adapter.py::BridgeFireCaptureAdapter` (weakest-seam pin: a 200 without
  bridge-confirmed `fired+real_hardware+nonce` is NOT a fire; one-shot stash).
- Composition: `l9_presence/controller_presence.py` (SYNCHRONIZED_CONTROLLER verdict from identity_bound +
  presence_candidate; device mismatch fail-closed).

## The BOOTSTRAP that just unblocked
The ring requires `l6b_enabled=True`. That was gated on N≥50-on-the-Edge, which is now **MET** (see
`docs/l6b-enable-seal-2026-07-20.md`). **So the L6B enable-seal is this arc's prerequisite** — firing it
(after F-L6B-SEAL-1 is resolved) unblocks the ring campaign. This arc does not start live until L6B is on.

## Increments (staged, each with a verify-hold; grok-audited per charter (a))
- **INC-0 — L6B live + ring dry-check (no play). CONFIRMED 2026-07-20.** After the L6B seal fired
  (`L6B_ENABLED=true` + `POEP_LIVE_FIRE_ENABLED=1`, process-scoped, bridge restarted): fired one nonce-bound
  probe via `POST /operator/operator/poep/fire` while the bridge held the pad → `{"fired": true,
  "real_hardware": true, "nonce": "<echoed exactly>", "error": ""}`. `latency_ms=-1.0`/`peak_lsb≈3.8`/
  `precursor_gap_ms=null` — no reflex captured, correctly honest since no human was holding the controller
  ready to react. The mechanism itself is proven; INC-1 (a human actually reacting) is the next open step.
- **INC-1 — presence-candidate under the bridge. REFLEX CAPTURED 2026-07-20.** First 3 fires post-INC-0
  (amplitude 60/255/255) all read `latency_ms=-1.0`/`peak_lsb=0.0` — no reflex, despite the operator
  actively reacting. Root-caused, not a rig failure: (a) `bridge/.env` had **`L6B_PROBE_MODE=rigid`** set
  (meant for desk bench-testing only, per its own docstring — never switched back), so the ring was firing
  a resistance profile only felt on a hard deliberate R2 pull, never a passive buzz; (b) the L6b analyzer
  reads **only accelerometer motion** (`ax/ay/az`) — it explicitly ignores the R2 trigger channel — so even
  a felt press-reaction (the technique the population-band captures used) is invisible to this specific
  measurement; the ring needs a physical hand/wrist jolt, not a controlled trigger press. Restarted the
  bridge with `L6B_PROBE_MODE=pulse` (process-scoped override at first) → next fire: `{"fired": true,
  "real_hardware": true, "nonce": "<echoed exactly>", "latency_ms": 1503.3, "peak_lsb": 5793.4,
  "error": ""}` — a genuine, unambiguous accelerometer spike (vs the 0.0 floor before) from a real human
  startle-reaction. **Repeated once more to check it wasn't a fluke: `latency_ms=1102.1`,
  `peak_lsb=5429.5`** — same order of magnitude on both peak and latency, 2/2 since the fix. `bridge/.env`
  since fixed PERMANENTLY (`L6B_PROBE_MODE=rigid` → `pulse`, surgical single-line edit with a `.bak`
  taken first; the file's CRLF line-ending convention was preserved) so future bridge restarts default
  correctly without needing the process-scoped override. `latency_ms` used the `t_mono` fallback clock
  both times (device-clock cross-check rejected it via the existing wrap-safe-span rail — honest
  fallback, not a bug); 1.1-1.5s is plausible for an unprompted startle jolt vs. the population-band's
  195-416ms *trained* R2-press reflex — different motor response, not comparable numbers.
  `presence_candidate` composition (via `controller_presence.py`) not yet separately re-verified against
  either fire — that's the next check before calling INC-1 fully closed.
  **Residual, non-blocking:** `sensor_ts_ticks` (the device-clock field used for `dev_lat`) was observed
  frozen at an identical value across 3 fires spanning ~7 minutes on the prior bridge instance — consistent
  with the previously-documented device-clock fragility under Remote Play topology (no RP session was
  necessarily active this time; not fully root-caused). Diagnostic-only — never gates the verdict, the
  system correctly fell back to `t_mono` throughout.
- **INC-2 — LIVE PLAY. REFLEX CAPTURED DURING A REAL MATCH 2026-07-20.** Operator set up dual-connection
  (Edge USB-C→PC for the bridge + BT-paired→PS5 for play) and got into an active match. Capture-health
  confirmed the setup before firing: `host_state=EXCLUSIVE_USB`, `poll_rate_hz≈1282` stable,
  `sustained_duration_s≈1028` (~17min). Fired one nonce-bound probe mid-play:
  `{"fired": true, "real_hardware": true, "nonce": "<echoed exactly>", "latency_ms": 1735.7,
  "peak_lsb": 3968.2, "error": ""}` — same order of magnitude as the two desk-based INC-1 captures
  (5793.4/5429.5), confirming the mechanism holds up under real in-game conditions, not just quiet-desk
  conditions. Post-fire capture-health showed `live_trigger_active_fraction` jump `0.0 → 0.45` in the
  recent window, corroborating genuine gameplay activity coincided with the fire (`latest_gameplay_context`
  didn't populate a label in this status view — a display gap in that specific field, not a gating issue).
  `latency_ms` again used the `t_mono` fallback clock (same `sensor_ts_ticks` residual as INC-1, unchanged);
  1.7s is on the slower end even vs. the desk captures, plausible given the operator had to disengage from
  active play to react rather than sitting ready for it. Single fire, banked as sufficient by operator call
  — not repeated for a larger in-play sample. `presence_candidate`/`SYNCHRONIZED_CONTROLLER` composition
  (INC-3) not yet separately verified against this fire.
- **INC-3 — SYNCHRONIZED_CONTROLLER under play. ATTEMPTED 2026-07-20 — HONEST GAP FOUND, NOT YET CLOSED.
  CORRECTED 2026-07-20 (same session): the first write-up of this finding was WRONG — see below.**
  `identity_bound` (ioID/VMDR) + `presence_candidate` (live ring fire) → verdict **SYNCHRONIZED_CONTROLLER**
  while a real match is in progress. Ran the pre-built one-command orchestrator
  (`scripts/poep_session_identity_attach.py --live`, already wired with the real ioID ceremony constants —
  tokenId 498, owner DID, TBA, VMDR pubkey hash, controller NFT) mid-match, twice (2 GO challenges each,
  4 real fires total). Both runs: `identity_bound=True` (full two-hop birth-cert→NFT→TBA chain verified),
  `live_hardware=True`, `activity_trusted=True`, `effective_live=True` — every mechanical/honesty-spine gate
  passed — but `n_go_verify_pass=0/2` both times → `gates.go_ok=False` → verdict **IDENTITY_ONLY**, not
  SYNCHRONIZED_CONTROLLER, at latencies 1102-1844ms across all 7 live-ring fires tonight (INC-1/INC-2/both
  INC-3 attempts) — 3-4x the sealed verify's GO band (195,416]ms.
  **This is NOT a new finding — it is the SAME problem as `docs/a2a/poep/round-rplatency-01-claude-open.md`
  (2026-07-18, F-RIG27-8): "8 fires ... real reflexes peaks up to 6597 ... every measured latency was
  594-4600ms, NEVER in the 80-280ms human band." That round diagnosed the root cause as Remote Play's
  bridge-side frame-processing lag inflating the bridge-wall-clock (`t_mono`) latency measurement, and
  built a companion device-clock latency (`dev_lat`, from the controller's own 3MHz onboard sensor
  timestamp — immune to bridge processing lag) as the fix.** The original write-up of INC-3 here framed
  the gap as a "reaction-speed / measurement-modality mismatch" WITHOUT checking for this prior finding
  first — that framing was wrong and has been removed. Correction, checked the same session: every one of
  tonight's fires shows `dev_lat=-1.0` (the device-clock fix never activated, rejected by its own
  `max_ms=500` plausibility rail) — computing the RAW device-clock span directly from the logged
  `cross_ts`/`probe_ts` ticks for 4 fires gives **1228-4608ms**, closely matching the corrupted `t_mono`
  values rather than showing a short "true" reaction that RP delayed in software. Since the device clock
  is stamped by the controller's own firmware at report-generation time — independent of when the bridge
  gets around to processing that report — this means **the inflation is NOT fully explained by bridge-side
  RP processing lag alone** (that theory predicts the device clock should show a short, undelayed span; it
  doesn't). Two live possibilities, genuinely unresolved without independent ground truth: (a) the physical
  reactions really did take 1.1-4.6s (plausible for an unprompted jolt with divided attention, less
  plausible for the 4.6s outlier), or (b) the analyzer's crossing-detection logic is identifying a frame
  well after the true accelerometer peak, in which case BOTH clocks would show the same inflated span
  because both are timestamping the same (mis-identified) frame, not the real reflex moment. **This is
  exactly the ambiguity a capture card resolves and neither software clock can** — an independent,
  hardware-level reference for when the physical reaction actually happened, uncoupled from the bridge's
  frame processing, the device's own HID timestamp, and the analyzer's crossing-detection logic, all three
  of which are now in question. RP-4 (`cross-lobe latency — BLOCKED (needs capture card + controlled
  stimulus)`) was scoped for exactly this measurement, before tonight's session existed.

  **Retest with a capture card + Remote Play FULLY CLOSED, same session, later that night:** operator
  connected a capture card, closed the RP app entirely (input never routed through it anyway — the
  controller BT-pairs directly to the PS5; RP only ever carried the video feed for the operator's screen),
  re-established dual-connection (USB→PC + BT→PS5), and restarted the bridge for a clean HID handle after
  ~11 reconnect cycles during the physical reconfiguration left the read in a degraded state (`frac=0.0`
  on two consecutive 45s preflight windows despite confirmed active play; resolved immediately on bridge
  restart — a real, separate finding: heavy USB/BT reconnect churn can leave the bridge's HID interface
  handle stale even while basic poll-rate/connectivity checks still pass). With RP fully closed and a
  fresh bridge: 2 more real fires, `latency_ms=2818.0/1029.0`, device-clock span `2416.8/899.9ms` (computed
  the same way as before) — **same order of magnitude as every RP-topology fire tonight, no improvement
  from removing RP.** This weakens the "RP frame-processing lag is the cause" theory further rather than
  confirming it: if RP were the cause, removing it should have produced short latencies. It didn't.

  **Sharper finding from `logs/l6b_probe_diagnostic.jsonl`** (a raw per-probe waveform record that exists
  for this exact purpose, checked after the no-RP retest): for one recent probe (`probe_r2_force=200,
  probe_hold_ms=300` — this specific entry's params don't match either of the operator's two manual fires,
  most likely the auto-tick's own independent periodic probe rather than one of the two logged above, so
  treat as characterizing the probe class on this rig rather than those two specific fires), the buffer
  shows `precursor_t_mono` and `crossing_t_mono` **13 microseconds apart** (`reflex_gap_ms=0.013`) — the
  "reflex" is detected essentially AT THE FIRST SAMPLE of the post-fire buffer, not found deep within a
  long search window. The entire measured `true_latency_ms=1488.9` is the gap between `probe_ts` (when the
  fire happened) and `crossing_t_mono` (when the post-fire buffer's first samples were collected).

  **RETRACTED 2026-07-20 (ASM-Loop external audit, grok, verdict HOLD — `docs/a2a/poep/rounds.md`):** the
  paragraph above (as originally written) framed this as a **"session-loop batch-boundary wait" mechanism,
  distinct from F-RIG27-8** — that framing did not survive audit and is retracted. Grok's findings against
  the same evidence, checked directly against the live tree and the diagnostic rows (probe_log_id 1557,
  1585):
  - **F1 (BLOCK):** the crossing lands EARLY in the post-fire buffer (`crossing_index=0` or `3`, not deep
    in a long search) — this REFUTES "waited for a later batch to find the peak." The real mechanism is
    that `_build_l6b_report` (`dualshock_integration.py:236-249`) stamps `t_mono` at classification/
    process time, not capture time — nearly every frame in a returned batch gets close to the same wall
    stamp. That inflates `true_latency_ms` independent of when within the batch the crossing sits.
  - **F2 (BLOCK):** this is the SAME mechanism `round-rplatency-01-claude-open.md` (F-RIG27-8) already
    named — "`t_mono` stamped when the session loop builds each entry, not device sensor time." Tonight's
    ~1s `_poll_frames` batching is a contributing lag source on top of that, not a second, independent root
    cause. The "NEW root cause" claim is retracted.
  - **F3 (BLOCK):** the device-clock-agreement claim doesn't hold in code as described — the live
    `_rp_device_latency_ms` (`dualshock_integration.py:205-233`) fail-closes above 500ms and falls back to
    the (already-inflated) mono path; a multi-second "device span" as described can't reach the comparison
    this doc drew from it. That comparison is retracted as unverified/likely a separate stale-timestamp
    artifact, not evidence of a second independent clock agreeing.
  - **F4/F5 (WARN, retained as open leads):** `frames_remaining=350` at `_poll_frames`'s ~8ms/frame cadence
    is actually a multi-second post-capture window, not the ~1s single-boundary residual implied above —
    the doc's "0-1s uniform residual" model understates the completion path. Mid-batch arming can also
    route pre-fire frames into the post buffer (no per-frame `t_mono >= probe_ts` gate at buffer-append
    time), a contamination surface not previously named.

  **What survives, corrected:** the mechanism is `_build_l6b_report`'s process-time `t_mono` stamping
  (F-RIG27-8, confirmed and refined — not superseded), with the session loop's ~1s batched poll interval
  as one concrete contributor to how large that process-time lag can grow. The fix direction is still
  code-side and still untried: stamp `t_mono` at frame **collection** time (inside `_poll_frames`, per
  frame) rather than at classification time, and/or thread the existing device-clock fix's intent through
  correctly instead of falling back silently past its 500ms rail. Needs code review of the
  fire→post-buffer-collection timestamp path, not more live fires — that's the next real step for a future
  session.
  **Left open. No further live-ring fires attempted this session.**
- **INC-4 — corpus + honesty spine.** Grow a corpus of SYNCHRONIZED-under-real-play sessions (N target TBD by
  the operator). The honesty spine (inherited): `effective_live = mode==live AND all(GO.live_hardware)`;
  `live_hardware = fire.real_hardware`; a dry/injected fire can NEVER reach SYNCHRONIZED (round-04 F-GP-4
  spoof defeat). No fabrication anywhere.
- **INC-5 — the `poep_enabled` seal (operator).** ONLY after INC-3/4 land with a real corpus + grok PASS:
  prepare the `poep_enabled` enable-seal (like the L6B one). Operator fires. This is the flip that makes PoEP
  presence proofs count.

## Claim ceiling (holds until INC-5)
- `poep_enabled` / `L6B` / `L6_CHALLENGES` stay operator decisions; this arc is candidate/campaign; gates
  nothing; zero spend; no chain; no FROZEN/PoAC edit.
- Rig/crypto residual: a fire-time-OBSERVING bot (host APIs / hardware injector) is a published residual,
  defended by the named HMAC(nonce‖t0‖onset) frame-commitment follow-on, not this arc.
- The reaction band (advisory) is scoped to competitive players; this arc reuses that band as the
  reflex-latency plausibility window but does not re-open it.
- SYNCHRONIZED-under-play is a session-liveness proof, not identity; the DID names the gamer wallet, not the
  silicon (per the ioID controller-presence fusion rulings).

## What earns `poep_enabled`, in one line
A corpus of **SYNCHRONIZED_CONTROLLER verdicts produced from real, nonce-bound, single-HID bridge-ring reflex
fires DURING live gameplay** — each `real_hardware=True`, none reachable by a dry/injected fire — then an
operator seal. Not the desk band; the live ring under play.
