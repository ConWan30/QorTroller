---
type: synthesis
id: s-independent-witness-retina-design
title: Independent-Witness Retina — decentralized screen-presence (off-device capturer → W3bstream verify → on-chain commitment)
created: 2026-06-28T19:15:00Z
modified: 2026-06-28T19:15:00Z
phase: VSD-LOOP
status: draft
confidence: possible
effort: 70
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

PROBLEM. The retina screen-lobe ([[s-wgc-capture-enhancements-built]], [[s-cross-channel-latency-invariant]])
runs WGC on the **player's own machine** — the player self-captures the screen they are also driving. That is
a single, self-attested trust point: a compromised host can feed fabricated frames. WGC the API cannot be
"decentralized" (it grabs local pixels); the unit to decentralize is the **trust in who observes the screen**.

THESIS. Move the screen observation OFF the player's box to an **independent witness**, keep HID telemetry on
the **certified controller**, verify their causal coupling on **W3bstream** (DePIN off-chain compute), and
**commit the result on-chain** — so no single machine, least of all the player's, is a root of trust.

PIPELINE (concrete).
1. **Session nonce.** Verifier/tournament issues a session nonce N (binds the proof to a time + context;
   defeats replay). Both the controller path and the witness path carry N.
2. **Controller path (certified, gamer-sovereign).** The DualShock Edge emits 1 kHz HID — R2 trigger,
   right-stick — timestamped on the device/bridge clock. This is the INPUT half (the [[s-retina-presence-product-thesis]] ground truth).
3. **Witness path (independent capturer).** A party that is NOT the player observes the screen and emits the
   per-frame channel signals (B1 flash luminance, B2 red kill-marker, geometric pan, ADS/FOV) with the WGC
   presentation-timestamp discipline already built. Three witness realizations (axis-1 options):
   - **Off-device HDMI sidecar** — a second box captures the game's HDMI output (the lag-free production
     answer in [[s-sidecar-capture-process-vs-device]]); zero capture load + zero trust on the gaming PC.
   - **Optical witness** — a tournament-station camera observes the screen / DualSense lightbar symbol stream
     (Sensor-Stack Surface 4); the player's box is entirely out of the trust chain.
   - **Peer/LAN witness** — the L8 BT-witness-tower pattern generalized to the screen lobe.
4. **Coupling = the binding.** The cross-channel latency invariant is computed over (controller HID × witness
   screen): the channels must share ONE render+stream latency. THIS is what makes the witness honest — a
   forger can fabricate one channel's score, but cannot make an **independent** witness's screen lag-agree
   with HID *they* pulled, because they do not drive that witness's pipeline. Cross-clock agreement across an
   independent observer is the decentralized presence claim.
5. **W3bstream verify (DePIN compute).** The validation runs in the retina Rust/Wasm applet (`INV-W3S-006`,
   `test_retina_w3bstream.py`) on W3bstream nodes — not on the player's bridge. Mechanical input-validation
   only (no biometric capture inside the sandbox, per the w3bstream mechanical-validation rule).
6. **On-chain commitment.** Emit the Poseidon `retina_events_root` + `retina_state_commitment` and anchor a
   32-byte `retina_pda_attestation` on IoTeX (all built, advisory/default-off). Bulky frames/signatures live
   on DePIN DA nodes (Arc-7 decoupled sidecar; `test_retina_da_witness.py`) — pointer-only on the wire.
   Any third party recomputes the commitment from the committed inputs months later.

WHAT IS NEW vs the current build. Today axes 2–4 (compute / commitment / DA) exist but consume a
**player-self-captured** screen. The novelty here is **axis 1**: the screen signal is sourced from an
**independent witness bound to the same nonce + latency window**, so the on-chain proof attests "an
independent observer saw a screen that causally obeyed this certified controller," not "the player says so."

HONEST OPEN GATES (why `possible`, design-only).
1. Needs a SECOND observer — real hardware/peer cost (HDMI sidecar, camera rig, or a witnessing node). A solo
   player with only their own PC cannot produce this; it is a tournament / staked-node / co-located construct.
2. **Witness↔controller time sync** is load-bearing: the two clocks must be reconcilable to the render-latency
   window or the coupling lag is meaningless. The presentation-timestamp epoch-alignment ([[s-wgc-capture-enhancements-built]])
   is the controller-side half; the witness needs its own anchor (shared QPC is impossible across boxes — use
   the nonce + a coupling-derived offset, the same trick the cross-channel invariant already tolerates).
3. The cross-channel latency invariant itself is still **UNCALIBRATED** (no measured FAR) — this design
   inherits that gate; it decentralizes the trust model but does not by itself prove separation.
4. W3bstream/commitment/DA paths are **advisory/default-off** in the repo; wiring the witness feed through them
   end-to-end is unbuilt. Optical-witness + sidecar are design, not hardware-validated.

NET. WGC stays a local sensor; everything around it decentralizes — capture *source* (independent witness),
compute (W3bstream), commitment (on-chain Poseidon root), data (DePIN DA). The roots of trust become the
**certified controller + an independent witness**, never the gaming PC. No FROZEN-v1 / 228B PoAC / chain /
IOTX touched; design-only.
