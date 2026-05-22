# Proof of Embodied Presence (PoEP) — Scope

**Status:** SCOPE / design-only. A new primitive built from scratch to prove a gamer's
**live, embodied presence on the specific certified device** — the claim QorTroller's
purpose actually needs, distinct from the (hard, sub-grade) inter-person *identity*
problem. Eventual implementation lives controller-side (L6); this scope sits with the
PoEP-adjacent infra it reuses (`hid_probe`, `imu_probe`, `pocp`).

## Mythos real-time alignment audit (2026-05-22)
Scope validated live against QorTroller's established infrastructure:
- **mythos_methodology_drift = 0** → sensor-stack/VBDIP trust chain CLEAN; PoEP may inherit
  the **Sensor Stack v2 canonical anchor** (adaptive trigger = PRIMARY DISCRIMINATOR;
  "L4-coupled-to-L6 challenge-response channel") without drift.
- **mythos_corpus_drift = 0** → separation/GIC/AIT clean; PoEP is presence/liveness,
  orthogonal to the separation/TGE gate (does not touch `separation_ratio`).
- **mythos_frozen_drift = 1 HIGH (pre-existing INV-016, from `1e8f8c23`)** → guardrail:
  PoEP adds **no new pinned PV-CI invariant except via the governance ceremony**, and must
  **not compound INV-016** (which stays operator-gated, not auto-fixed).

## The claim PoEP proves (and why it's the right one)
"Prove a gamer's presence using a specific device" = three claims; PoEP targets the two
that are **population-/physics-level** (so they sidestep the per-player-corpus ceiling that
left identity sub-grade at EER 29%):
1. **Device authenticity** — a real certified Edge (CFI-ZCP1), not Cronus/XIM/emulator/cloud-bot.
2. **Liveness + presence** — a live human acting *now*, hands on the device.
3. ~~Identity (which human)~~ — out of scope; that's the L9/biometric track (banked sub-grade).

## Mechanism (nonce-bound challenge-response)
1. At a cryptographically random time, the bridge issues a **sub-perceptual** adaptive-trigger
   resistance change and/or haptic pulse (challenge = nonce).
2. The human's involuntary motor micro-response (grip / trigger force / stick) is captured at
   **1 kHz** in the **80–280 ms reflex window** (the L6-Response band).
3. Decision: device-auth (only a real Edge renders the adaptive-trigger physics; translators
   cannot synthesize a biomechanically-structured force response) + liveness (response lands
   in the human reflex band with biomechanical structure) + freshness (response is to *this*
   nonce → unreplayable).
4. Commit: `PoEP = SHA-256(b"QORTROLLER-POEP-v0" || device_id || nonce || response_features ||
   ts_ns)` — a **v0 candidate**, parallel to PoAC, NOT anchored, NOT a registered primitive.

## Alignment with established infrastructure (the contract)
| Established surface | PoEP obligation |
|---|---|
| 228-byte PoAC wire format (FROZEN) | **Untouched** — PoEP is a PARALLEL commitment, never a PoAC change |
| PITL L6 = active haptic challenge-response | PoEP **is** L6-Response; honor `L6_CHALLENGES_ENABLED=false` default |
| Hard rule: `L6B_ENABLED=false` until **N≥50 neuromuscular reflex calibration** (current N=0) | PoEP's reflex IS L6B → v1 is infra + de-risk + **calibration-gathering only; NOT activated** until N≥50 |
| Roadmap: L6-Response activates only after **GIC_100** + N≥50/player; **sub-perceptual ≤60/255** | Scope respects both gates + the amplitude cap |
| Sensor Stack v2 canonical anchor + BT-CALIB-LESSON-001 (3 independent verification sources) | Every PoEP sensor claim cites vendor-spec + open-source driver + literature; Stage-A measurement gates before any field claim |
| PV-CI / FROZEN (Mythos frozen=1 INV-016) | New invariants only via governance ceremony; don't compound INV-016 |
| Deferred-activation / two-key discipline | `poep_enabled=False` default, `dry_run=True`, operator opt-in to go live |
| CONSENT v1 + gamer sovereignty | PoEP data gamer-owned, consent-bound; bridge never grants/revokes consent |
| Device cert (DualShock Edge CFI-ZCP1) | PoEP binds `device_id`; certified-device only |

## The decisive constraint (and why v1 is bounded)
The **read** side (1 kHz HID/IMU capture) is validated (`hid_probe`/`imu_probe`). The **write**
side (issuing the challenge) is unproven and the **reflex feature maps to L6B, hard-gated at
N≥50** — so PoEP cannot make a liveness *claim* until calibrated. Therefore **v1 = de-risk +
capture infra + calibration corpus**, default-OFF, no activation.

## Phases
- **P0 — De-risk (10 min, on-rig).** Can the bridge issue a haptic / adaptive-trigger command
  over USB **and** capture a measurable reflex in the 80–280 ms band at 1 kHz, without conflicting
  with the PS5 (which owns haptics over BT during Remote Play)? GO mid-game → in-game PoEP; if it
  conflicts → v1 is an **enrollment / between-match presence check** (bridge owns the controller).
- **P1 — Capture infra.** Nonce scheduler + sub-perceptual challenge emitter (reuse pydualsense
  trigger/haptic writes) + 1 kHz reflex window capture + feature extraction (reaction latency,
  force-response curve, post-stimulus grip micro-adjustment). Stores a labeled PoEP session.
- **P2 — Calibration (gated).** Gather the **population reflex-band model** + per-device adaptive-
  trigger physics signature. Liveness is population-level (no N-player identity corpus needed) but
  honors the **N≥50 L6B calibration** hard rule before any liveness verdict.
- **P3 — Commitment.** `pocp`-style `PoEP` commitment + a gamer-facing verification card; Sentry-
  anchorable later (dry-run seam, like the Witness).
- **P4 — Governed activation.** `poep_enabled` + `L6_CHALLENGES_ENABLED` flip only via two-key
  operator action, after GIC_100 + N≥50 + Stage-A measurements + (any new invariant) PV-CI ceremony.

## What this is NOT
Not an identity claim (that's L9, banked sub-grade). Not a PoAC/FROZEN change. Not activated
(L6B N≥50 hard rule). Not anchored (v0 candidate). Not a field-validated detector until Stage-A
measurements + the de-risk pass. Mythos to be re-run at each phase as the alignment gate.
