# A2A-POEP-P3P4 · Round 17 — Claude builds the RIGHT thing: P-LIVE-0 (nonce-bound), not RBM-v1

**2026-07-15 · Claude → grok + operator.** grok round-16 verdict: presence is NOT earnable from stored
scalars via an offline model (a scalar-matching macro A-SCALAR samples the human joint and clears any
offline scorer); presence structurally REQUIRES the live nonce-challenge protocol. So "proceed with
build" built the right thing -- **P-LIVE-0**, not the dead RBM-v1.

## Built (`l9_presence/poep_live_verify.py`)
- **Candidate PoEP commitment** binding the response to THIS challenge's fresh nonce:
  `SHA-256(b"QORTROLLER-POEP-v0-CANDIDATE" ‖ device_id ‖ nonce ‖ feature_digest ‖ ts_ns)`.
- **Offline verify auditor** (NOT an ML model) -- fail-closed 5-check: nonce match · response-after-
  challenge · reaction-band [80,300]ms of the LIVE challenge · IMU corroboration · commitment integrity.

## What it DEFEATS -- by construction (the win the offline model couldn't get)
| attack | RBM-v0 offline FAR | P-LIVE-0 |
|---|---|---|
| **A-REPLAY** | 0.90 | **DEFEATED** -- replayed response carries the OLD nonce → mismatch (test-pinned) |
| **A-CONST / pre-scheduled** | 0.76 | **DEFEATED** -- challenge fires at an unpredictable nonce-scheduled time → fixed-schedule response lands out of band (test-pinned) |
| pre-recorded / forged commitment | — | DEFEATED (temporal + binding checks) |

6 tests prove each attack fails against a fresh nonce. This is a real, provable advance: presence
moves from "score a stored number" (spoofable) to "answer a live unpredictable challenge, cryptographically bound."

## Why poep_enabled STAYS False (the honest limit)
P-LIVE-0 does NOT defeat a **reactive bot** -- one that detects the live challenge onset and reacts
within 80-300 ms. Timing + binding alone can't separate a fast reactive bot from a human; that needs
**waveform-shape features + Stage-A**. So the flip is materially closer but NOT earned. `poep_enabled`
/ `L6B_ENABLED` / `L6_CHALLENGES_ENABLED` verified still False; candidate tag, no FROZEN promotion.

## The honest remaining path to the flip
1. **Live-capture instrumentation** (rig): daemon fires nonce-scheduled challenges, captures response
   + a bounded raw accel window (hashed) -- gives waveform shape offline strengthening.
2. **Reactive-bot analysis + waveform shape** -- the tier that separates a live human from a live bot.
3. **Stage-A** measurements + two-key operator flip.

## The honest bottom line for the operator's request
"Flip PoEP to true" -> the loop proved the offline path CANNOT earn it, built the protocol path that
genuinely can (P-LIVE-0 defeats replay + pre-schedule), and HELD the flip because a reactive bot
isn't yet defeated. QorTroller will claim presence only when it can defend it -- that discipline is
the product. The flip is earned at the live-capture + reactive-bot tier, operator-two-key-fired, not here.

---
*Round-17 — P-LIVE-0 built + test-pinned 2026-07-15. Replay + pre-schedule DEFEATED by construction;
reactive-bot open. poep_enabled HELD False. 16 tests · PV-CI 183. The honest presence path is live, not offline.*
