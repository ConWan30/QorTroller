# POEP live-play ring arc — spec (what earns `poep_enabled`) · 2026-07-20

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
- `POST /operator/poep/fire` — operator endpoint (arms `_l6b_pending` w/ nonce + Future, awaits w/ timeout).
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
- **INC-0 — L6B live + ring dry-check (no play).** After the L6B seal fires: `POST /operator/poep/fire` with a
  nonce while the bridge holds the pad → confirm a REAL fire (`fired + real_hardware=True + nonce` echoed),
  MEASURED features (never band-filled), 409-on-busy. This is the ring working WITHOUT a game — the mechanism,
  not yet the claim. Verify: `poep_rig_reflex_selftest`-class check through the bridge endpoint.
- **INC-1 — presence-candidate under the bridge.** With the bridge UP and `activity_source=="bridge"` (bridge
  reading the pad live), a fired nonce probe + human reflex → `controller_presence` yields
  `presence_candidate=True`. Still no game; proves the candidate path is reachable when the bridge owns the pad.
- **INC-2 — LIVE PLAY.** Operator plays a REAL game through Remote Play (pad USB→PC to the bridge; game on the
  PS5). During play the bridge (or `/operator/poep/fire`) serves nonce challenges; the human reacts mid-play;
  the ring captures the reflex from its own reader. Verify: reflex `real_hardware=True`, latency in the
  competitive band, nonce-bound, activity_source=bridge — DURING a live match.
- **INC-3 — SYNCHRONIZED_CONTROLLER under play.** `identity_bound` (ioID/VMDR) + `presence_candidate` (live
  ring fire) → verdict **SYNCHRONIZED_CONTROLLER** while a real match is in progress. This is the artifact the
  whole arc targets. Verify: the fused verdict, device-match, no `real_hardware=False` path reaching it.
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
