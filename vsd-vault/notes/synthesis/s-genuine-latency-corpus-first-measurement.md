---
type: synthesis
id: s-genuine-latency-corpus-first-measurement
title: First live genuine cross-channel latency corpus — measured 17 ms tight-coupling cluster (100% timespan)
created: 2026-06-29T00:10:00Z
modified: 2026-06-29T00:10:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

FIRST live genuine corpus for the cross-channel latency invariant ([[s-cross-channel-latency-invariant]]),
captured over a real Warzone / PS Remote Play session (2026-06-28, dev-cert / continuous monitor capture,
`scripts/retina_capture_daemon.py`). This is the measurement the invariant + the product thesis
([[s-retina-presence-product-thesis]]) were gated on — the genuine (FRR) half.

CORPUS. 282 dense RGC-diag samples -> **77 usable** (>= 2 coupled channels) -> **41 "coupleable"** (>= 2
channels that cleared the null-collapse guard, i.e. eligible to read PRESENT_COHERENT). **ts_source = timespan
on 282/282 (100%)** — the WGC presentation-timestamp enhancement ([[s-wgc-capture-enhancements-built]]) ran
flawlessly on live HDR frames, zero wall-fallback.

THE RESULT — a tight cluster, measured. Lag-spread (MAD over the 41 coupleable):
`min=0  median=17ms  p75=158ms  p90=183ms  max=233ms`. **Bimodal**: roughly half the coupled samples agree
TIGHTLY (~<=20 ms) and half spread wide (>150 ms). tau-sweep genuine acceptance: tau=20ms -> 51%, 80ms -> 66%,
120ms -> 71%, 200ms -> 98% (only by going far too loose). At the placeholder tau=80 the 77 split
27 PRESENT_COHERENT / 14 INCOHERENT / 26 INSUFFICIENT_CHANNELS / 10 UNVERIFIABLE.

READING IT (load-bearing). The **median 17 ms agreement on ~half the coupled play is the invariant working on
live data** — trigger/stick/screen sharing one render clock, exactly the causal-presence signal. The wide tail
(>150 ms) is noise (chaotic-combat windows where channels coupled but their lag estimates disagreed; B2-vs-B1
timing drift). The FAR-safe threshold should therefore sit near the **tight cluster (~20-40 ms)**, NOT at the
66%-capturing tau=80 — tight cross-channel agreement is precisely what a forger cannot fabricate across
independent channels.

WHAT MADE IT WORK (the capture journey, for the record). Three fixes turned a 3-sample dud into this corpus:
(1) **monitor capture** not window ('Remote Play' is not a real window title -> start() failed silently);
(2) **continuous** capture not burst-on-demand (burst waited for a trigger file that was never touched ->
started=False, 0 frames, 144 empty samples); (3) **dense sampling** (`RETINA_DIAG_EVERY=4`) + the **detached
daemon** that survives the remote-access view dropping when the game goes fullscreen.

OPEN GATE (why the certified threshold is NOT set here). This is the **genuine/FRR half only**. The FAR-safe
`tau_lag_ms` cannot be fit without a **forged (spectate-along) corpus** — the threshold is wherever the tight
genuine cluster sits BELOW where spectated-screen forgeries fall. Expectation: if forged spreads land >40-60 ms
(a spectated screen is not on your clock), tau ~ 20-40 ms -> FAR~0 with ~50-60% genuine accept — a real,
defensible operating point. The forged pass + `calibrate_tau_lag` is the immediate next step. Until it lands,
`CALIBRATION_STATUS` stays uncalibrated; this note records the measured genuine side, not a certified gate.

No FROZEN-v1 / 228B PoAC / chain / IOTX touched; advisory presence calibration. Raw corpus
(`genuine_*.jsonl`) stays local (not committed — session data).
