---
type: synthesis
id: s-bt-capture-research-validation
title: External research validates + corrects the inverted-topology synthesis — BT dual-host is architecturally blocked; inline USB HID proxy is the answer
created: 2026-06-25T00:00:00Z
modified: 2026-06-25T00:00:00Z
phase: VSD-LOOP
status: draft
confidence: highly-likely
effort: 55
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

Operator ran a Claude.ai deep-research pass on the concurrent-capture question from
[[s-bt-capture-topology-inversion]] (cycle 18). This note records the convergence AND the
corrections the sourced research forces on the loop's prior synthesis — the VSD discipline applied
to itself: an external authoritative source refining a loop-produced note, recorded honestly rather
than quietly overwritten.

WHAT THE RESEARCH CONFIRMS (cycle-18 held up):
  - Concurrent USB-host (PS5) + BT-second-host (laptop) reading one controller is NOT feasible.
  - BT cannot be host-overclocked the way USB can (hidusbf/DS4Windows filter are wired-only).
  - The full IMU-bearing report (0x31) only appears over BT after the 0x05 feature-report handshake;
    a naive BT bridge gets the simplified 0x01 report with NO motion data.
  - The robust answers are the inline USB proxy and the passive USB tap; crypto-agency is the axis
    on which to judge them; a cheap falsification test should formally close the BT idea.

THREE CORRECTIONS the research forces on cycle 18 (the load-bearing updates):

  C1 — INVERTED BT IS ARCHITECTURALLY BLOCKED, NOT "TESTABLE/MIGHT-HAVE-LEGS." Cycle 18 left
  #BT-INV-1 (can the DualSense hold BT-to-laptop while USB-to-PS5?) as an open empirical unknown
  worth building toward if positive. The research closes it as a hard NO at the radio/firmware
  layer: the DualSense is Bluetooth *Classic* (BR/EDR), a slave can belong to ONE piconet master
  at a time, there is one radio and one shared HID input-report state machine, and the kernel
  hid-playstation driver binds a controller to exactly one bus at enumeration. So the falsification
  test is now for FORMAL CLOSURE with the operator's exact firmware, not a real path. Cycle-18's
  "the inversion might have legs" was too optimistic; corrected to "blocked."

  C2 — BT IS DOUBLY DISQUALIFIED. Beyond dual-host, even a SINGLE-host BT read degrades the signal
  that matters: ~250 Hz (standard DualSense) / 400–600 Hz (Edge) vs 1000 Hz USB, with ~2 ms-worse
  and jitter-prone latency. The physiological tremor BAND (8–12 Hz + ~20–25 Hz mechanical) is
  recoverable by Nyquist at 250 Hz — but the protocol's anti-spoof edge lives ABOVE the band
  (micro-corrections, inter-sample timing entropy, fine trigger-force curves), which needs USB's
  1 kHz + low stable jitter. So BT-as-telemetry is a poor trade even where it works.

  C3 — THE DISCONNECT MECHANISM IS SEQUENCE/CRC DESYNC — WHICH VALIDATES THE L6B-DISABLE FIX. The
  research's best-grounded explanation for the "stick modules not attached" disconnect: the 0x31 BT
  report carries a sequence counter + CRC-32, output reports carry an incrementing seq_tag, and the
  controller has ONE shared state machine; when a second host DRIVES the controller (sends output
  reports / triggers the feature handshake) while the PS5 holds the link, the shared sequence/feature
  state desyncs from what the console expects → PS5 drops it. This is exactly why disabling L6B
  (whose L6TriggerDriver wrote adaptive-trigger OUTPUT reports every 60 ticks) stopped the
  disconnects: it made the bridge READ-ONLY, which is precisely the research's Fallback-C mitigation
  ("never send output reports, never trigger the calibration handshake"). The L6B finding and the
  research independently converge on the same root cause. Recorded as a cross-validation, not a
  coincidence.

THE PATH SHIFT (cycle 18 → cycle 19): cycle 18's protocol-correct answer was a QorTroller-NATIVE
dual-channel controller (long-horizon silicon). The research adds a BUILDABLE-NOW path that cycle 18
under-weighted: Fallback A — an inline USB HID man-in-the-middle PROXY (RP2040 with PIO-USB /
ESP32-S3 / Raspberry Pi) between PS5 and controller. It forwards the genuine controller's reports to
the PS5 unmodified (passing Sony's controller auth by RELAYING, not emulating) and mirrors every
report to the bridge over a side channel — full ~1000 Hz USB-grade reports incl. IMU + trigger
force, sub-ms added latency, crypto-agency PRESERVED (the genuine controller stays the agency-holder,
the PS5 sees exactly one device on one transport, so the desync of C3 never arises). Open-source
precedents exist (RP2040 DualSense↔PS5 passthrough PoC; felis USB_Host_Shield PS5USB;
paulcager/hid-passthrough; GIMX/USBProxy; HID-Remapper auth passthrough). RANK: A (inline proxy) >
B (passive USB tap; observe-only, can't issue feature challenges → may weaken active PoAC
interrogation) >> C (root-cause read-only; still asks the controller to hold two links it can't) >>
D (BT sniff; BR/EDR sniffing unreliable + link-key encryption + ToS-fraught). So: inline USB proxy
is the NEAR-TERM recommended architecture; the native dual-channel controller (HWFL-1 BOM / Path A
dev-kit) is the LONG-TERM convergence — the proxy is the prototype, the silicon is the destination.

HONESTY RAILS (inherited from the research's own caveats):
  - "module inconsistency" / "stick modules not attached" is NOT a documented error string in any
    primary source; the desync mechanism (C3) is INFERRED from documented report structures, not
    from a source naming that error. Operator should pin the exact wording from their own logs.
  - PS5 controller-auth passthrough is Fallback A's chief technical risk; precedent says it's passable
    by relaying the genuine controller, but a Sony firmware update could break it. Benchmark gate:
    2-hour PS5 session, zero disconnects, ≥99.9% reports mirrored at <1 ms added latency.
  - BT rate figures (~250 / 400–600 Hz) are developer/community order-of-magnitude, not spec.
  - Sniffing/MITM of the PS5↔controller link may violate Sony ToS; not recommended.
  - Sony firmware 0213 (2025-09-17) multi-device = up to four PAIRINGS with MANUAL 3-second switching,
    NOT simultaneous active links — and switching is unavailable while connected to a PS5 console.

DECOUPLING REMINDER (unchanged from cycle 18, reaffirmed): none of this changes the certification
blocker. enrollment_status=unknown + the probe-vs-gameplay calibration mismatch means a
gameplay-conditions enrollment pass is STILL required for CERTIFY → M1, and that pass can run NOW in
USB-EXCLUSIVE mode (stable 1600 Hz this session) — fully decoupled from solving the play+capture
topology. Topology unlocks simultaneous PS5-play capture; it does not by itself produce a certified
session.
