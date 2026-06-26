---
type: synthesis
id: s-bt-capture-topology-inversion
title: Inverted capture topology (USB→PS5 + optimized BT→laptop) — feasibility + the real QorTroller-native answer
created: 2026-06-25T00:00:00Z
modified: 2026-06-25T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 50
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

OPERATOR QUESTION (2026-06-25 live capture session): the laptop↔controller USB link won't stay
stable during dual-host play, so the 10-NOMINAL enrollment corpus can't accumulate. Proposal:
INVERT the topology — give the PS5 the primary USB link (full-rate gameplay) and capture on the
laptop over Bluetooth, with a QorTroller-exclusive BT software layer to OPTIMIZE the laptop↔
controller BT connection. Is that possible? This note records the honest feasibility analysis so
the protocol doesn't chase a software fix that physics/firmware forbids.

EMPIRICAL GROUNDING (this session): the bridge measured BT-to-laptop = ~114 Hz / DEGRADED;
USB-to-laptop = ~1600 Hz / NOMINAL / EXCLUSIVE_USB. The accel-spectral-entropy feature and the
biometric fingerprint require sustained ~1 kHz, so 114 Hz BT capture cannot certify (enrollment
status = unknown, humanity → 0, FLAG). USB-only capture is STABLE and full; the instability is a
property of *simultaneous dual-host*, not of USB itself.

PART A — THE BT-OPTIMIZATION INTUITION IS HALF-RIGHT (and worth stating plainly):
The 114 Hz almost certainly reflects the DualSense's BASIC Bluetooth HID report (0x01) — the
compatibility mode a host gets before "unlocking" the device. The DualSense exposes a FULL report
(0x31) carrying the IMU + higher cadence, activated by reading feature report 0x05 / issuing an
output report. Open-source stacks (pydualsense, DualSenseX, DS4Windows) already do exactly this.
So a QorTroller BT layer COULD push laptop BT capture well above 114 Hz WITH IMU — toward the
~250–500 Hz BT-practical ceiling (BT BR/EDR HIDP is latency/slot-bound below USB's 1 kHz, per the
BT-CALIB canonical anchor). The operator's instinct that "BT can be optimized" is correct AT THE
SINGLE-LINK LEVEL.

PART B — THE FATAL CONSTRAINT IS NOT THE BT RATE, IT'S DUAL-HOST SIMULTANEITY:
A stock DualSense streams its rich telemetry to ONE active host. When USB-connected (to the PS5),
the BT radio is generally dormant/unavailable for a second host. So "USB→PS5 AND BT→laptop at the
same time" hits the SAME one-active-link wall as the current setup — just flipped. Crucially, NO
laptop-side software can make the controller dual-broadcast if Sony's firmware won't expose a
second concurrent host link. A "QorTroller BT software" runs on the LAPTOP; it cannot rewrite the
controller's firmware host-arbitration. So the inversion does not, by itself, escape the wall.

PART C — THE ONE HONEST EMPIRICAL UNKNOWN (testable, cheap):
There is a real asymmetry worth a 10-minute test before discarding the idea: does the DualSense
PERMIT a Bluetooth host connection to the laptop WHILE it is USB-connected to the PS5? If it pairs
+ streams (even at basic rate) → the inversion has legs and the QorTroller BT layer (full-mode
unlock) becomes worth building. If the USB link blocks BT pairing → the inversion is dead and we
stop. This is Empirical Unknown #BT-INV-1; it must be measured, not assumed.

PART D — THE ROBUST ALTERNATIVE THAT SIDESTEPS THE WALL ENTIRELY:
Passive USB tap. PS5←USB→controller stays pristine (full rate, full auth, full IMU, full play);
a passive hardware tap mirrors that USB stream to the laptop, which parses it. No second
controller link is needed, so the dual-host arbitration never arises. This is strictly more
reliable than betting on BT dual-host, and the QorTroller "software" becomes a USB-stream parser
rather than a BT-mode hack. For getting 10 NOMINAL gameplay sessions during real PS5 play, the
passive tap is the lower-risk path.

PART E — THE NOVEL, QORTROLLER-EXCLUSIVE ANSWER (the synthesis-worthy part):
The operator's idea is unbuildable on a STOCK DualSense (firmware single-host limit) — but it is
exactly a DESIGN REQUIREMENT for the QorTroller-native controller (Path A dev-kit / HWFL-1 BOM).
A controller designed FOR this protocol can natively expose TWO concurrent channels: a primary
gameplay link (USB or wireless to the console) AND a secondary, always-on, full-rate biometric
TELEMETRY channel to the capture host — because the protocol's whole thesis is that the
controller is the cryptographic agency-holder over its own data. Stock DualSense treats capture as
adversarial/incidental; a QorTroller controller treats it as a first-class output. So the right
home for "optimized capture link alongside gameplay" is not laptop BT software over a Sony
controller — it is a BOM/firmware requirement on the QorTroller dev-kit: dual-channel
(play + full-rate signed telemetry) output. That reframes the operator's question from "patch
around Sony" to "spec it into our own silicon," which is the protocol-consistent move.

HONESTY RAILS:
  - No claim that laptop software can override DualSense firmware host-arbitration. It cannot.
  - The BT full-mode unlock (0x31) is real and raises single-link rate, but BT BR/EDR stays below
    USB 1 kHz and is jitter-bound (BT-CALIB anchor); it may still under-serve accel-spectral-entropy.
  - The dual-host simultaneity question is an EMPIRICAL UNKNOWN (#BT-INV-1), not a settled fact —
    test it (pair laptop BT while USB→PS5) before building anything.
  - Nothing here changes the certification blocker by itself: even with perfect simultaneous
    capture, enrollment_status=unknown means a gameplay-conditions calibration pass is still
    required for CERTIFY → M1.

PRACTICAL ANSWER TO "HOW DO 10 NOMINAL SESSIONS GET PRODUCED IF USB WON'T STAY STABLE":
USB-only IS stable (1600 Hz NOMINAL this session); the instability is dual-host-specific. So the
near-term, zero-hardware path is to capture the enrollment corpus in USB-EXCLUSIVE mode (stable,
full-rate) — accepting that the captured "play" is controller manipulation / laptop-side or
Remote-Play gameplay, not native PS5-BT play — until either (a) the passive USB tap is in hand, or
(b) #BT-INV-1 proves the inverted BT link viable, or (c) the QorTroller-native dual-channel
controller exists. The enrollment math doesn't require PS5-native play; it requires 10 stable
NOMINAL captures of THIS player on THIS hardware.
