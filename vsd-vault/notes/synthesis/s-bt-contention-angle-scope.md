---
type: synthesis
id: s-bt-contention-angle-scope
title: BT-contention angle scope — treat Bluetooth link contention as a FIRST-CLASS capture-integrity signal that gates the presence proof; unifies PCC + tether + agent #34 + bt_witness + dev-cert + Remote Play under "capture integrity precedes presence"
created: 2026-06-26T21:30:00Z
modified: 2026-06-26T21:30:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 90
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Scopes the "BT-contention angle": what it is, what a BT-contention intelligence capability would DO, and
how it slots SYNERGISTICALLY into QorTroller's already-built infrastructure (no new silo). Surfaced
alongside the developer-self-cert + Remote Play retina work; formalizes the existing
vapi_bt_contention_intelligence MCP surface + the BT-CALIB threat model into one integrity primitive.

WHAT IT IS: BT-contention = interference/competition on the DualSense Edge's Bluetooth BR/EDR link that
degrades the INTEGRITY of the captured input stream. Sources observed across this arc: (a) dual-connection
(USB->laptop + BT->PS5 both active) — the controller reports real input only to its active host, so BT
contention correlates with the dual-connection biometric blindness; (b) Remote Play streaming (USB/HID
traffic -> poll-rate variance -> PCC CONTESTED, per CLAUDE.md); (c) the "module not attached" flaps (the
DUAL_GRIND_TETHER finding); (d) AFH channel-hopping under RF congestion + retransmission slotting (the
BT-CALIB v1.1 anchor's BR/EDR primitives — Tpoll variance, AFH-aware retransmission). It MANIFESTS as
poll-rate CV (PCC's CONTESTED host_state), Tpoll variance, and HCI retransmission counts.

WHAT A BT-CONTENTION CAPABILITY WOULD DO (4 layers, each mapped to an EXISTING piece — no new silo):
  1. SENSE — poll-rate CV (PCC capture_continuity, ALREADY LIVE: EXCLUSIVE_USB/CONTESTED/EXCLUSIVE_BT)
     + bt_witness HCI observations (LAN-tower BlueZ, Tpoll/retransmission, Phase 242 scaffold) + the
     module-flap events (tether finding) + the tether's own pulse efficacy (a healthy tether == low
     contention).
  2. CLASSIFY — distinguish BENIGN contention (Remote Play streaming, RF congestion, legitimate
     dual-connection) from ADVERSARIAL (a relay/cloud-bot CONTENDING the link to mask injected input —
     exactly the BT-CALIB cloud-gaming-bot stealth threat model) from HARDWARE (module flap). This is the
     load-bearing novelty: contention is where the BT-CALIB attack class would SHOW UP, so classifying it
     is anti-cheat signal, not just ops telemetry.
  3. GATE — feed the integrity/presence layer: CONTESTED -> agent #34 PRESENCE_CONTESTED (JUST BUILT,
     LIVE) + the dev-cert NQPV proof DEGRADES/abstains. This already embodies "capture integrity precedes
     presence" — devcert_signal_for_verdict() makes contested WIN over any human verdict (a contested
     capture cannot certify). The BT-contention angle generalizes that rule into a named primitive.
  4. MITIGATE — the DUAL_GRIND_TETHER (A/B/A-validated: anchors the wireless module, cuts flaps/contention)
     + operator guidance (e.g., "Remote Play is contending — accept COUPLED_CLEAN-only, or switch to
     direct-USB for full L4").

SYNERGY MAP (everything already exists; the angle UNIFIES them):
  - PCC/capture_continuity = the live CONTESTED sensor (layer 1).
  - DUAL_GRIND_TETHER = the mitigation (layer 4), causally validated.
  - agent #34 PRESENCE_CONTESTED = the live signal surface (layer 3) — just enhanced/activated.
  - bt_witness (LAN-tower BlueZ) = the cryptographic forensic witness of BT-session HCI (layer 1 evidence
    + the cross-tournament non-repudiable attestation the BT-CALIB anchor said is the genuine novelty).
  - dev-cert NQPV proof = the consumer that degrades under CONTESTED (layer 3).
  - Remote Play retina capture = a benign-contention SOURCE the classifier must not mislabel (layer 2).
  - BT-CALIB v1.1 anchor = the threat model + the BR/EDR primitives the classifier reads (layer 2).

ALIGNMENT RAILS (so it stays QorTroller-coherent, not a bolt-on): (i) "capture integrity precedes
presence" is the governing principle — BT-contention GATES the proof, never fabricates one; (ii) honest
scope — benign vs adversarial classification is a CLAIM that needs measurement (the BT-CALIB FN floors:
5.84% CFO / 8.72% RSSI / 2.37% combined per BlueShield), so v1 surfaces CONTESTED + a benign/adversarial
LEAN, not a hard adversarial verdict, until measured; (iii) no FROZEN-v1 / 228B PoAC / chain change — BT
contention is an integrity overlay, not a wire-format change; (iv) the LAN-tower witness is hardware-gated
(bt_witness stays dormant until the BlueZ tower exists) — the angle works in a degraded mode on PCC alone
until then.

WHAT v1 (agent-buildable now) WOULD BE: a thin BT-contention intelligence module that fuses PCC host_state
+ poll-rate CV + module-flap rate -> a contention_state {CLEAR / CONTESTED-BENIGN / CONTESTED-SUSPECT /
FLAPPING} + a benign/adversarial LEAN (benign if a known streaming source like Remote Play is active;
suspect otherwise) -> already consumed by #34 (PRESENCE_CONTESTED) and the dev-cert gate. bt_witness HCI
evidence + the hard adversarial verdict are v2 (LAN-tower hardware). HONESTY: this names + unifies what the
arc already proved (CONTESTED gates the proof); the adversarial-detection claim stays a measured-LEAN until
the BT-CALIB study runs. Related: [[s-live-p-l4-reanchor-scope]], [[s-presence-oracle-liveness-scope]],
[[project_dualconnection_capture_blind_finding]], [[l9-presence-arc]].
