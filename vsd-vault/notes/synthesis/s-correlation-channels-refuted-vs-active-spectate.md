---
type: synthesis
id: s-correlation-channels-refuted-vs-active-spectate
title: Correlation channels REFUTED vs active-spectate-spam — kill-feed authorship is required (measured)
created: 2026-06-29T00:40:00Z
modified: 2026-06-29T00:40:00Z
phase: VSD-LOOP
status: draft
confidence: likely
effort: 50
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

DECISIVE NEGATIVE (live, 2026-06-28/29, Warzone/Remote Play). Tonight's paired capture — genuine play WITH
kills vs active-spectate WHILE SPAMMING R2 — shows that NONE of the correlation-based presence channels
separate the two. This refutes the cross-channel latency invariant ([[s-cross-channel-latency-invariant]])
AND single-channel magnitude as standalone anti-spectate discriminators, and NECESSITATES game-state
authorship ([[s-killfeed-authorship-spectate-defeat]]).

THE DATA (genuine-kills vs spectate-spam):
- Cross-channel latency `calibrate_tau_lag`: **NO_SAFE_THRESHOLD**, best tau=35ms -> FAR=0.46 / FRR=0.69.
  Forged lag-spread (median 0ms) was TIGHTER than genuine (median 17ms) — the invariant fails.
- B2 kill-marker magnitude: genuine med 0.156 / spectate med 0.148; at B2>=0.20 both 29%, at B2>=0.25
  genuine 6% vs spectate 14%, at B2>=0.30 genuine 0% vs spectate 7% — **spectate is EQUAL or HOTTER**.
- B1 flash: genuine med 0.191 / spectate 0.138 (slight edge, total overlap, both max ~0.37-0.39).
- geometric: genuine med 0.124 / spectate 0.084 (slight edge, spectate max 0.415 — overlap).
(n: genuine-kills 17 coupled B2 samples — short session; spectate-spam 96 — solid.)

THE MECHANISM (load-bearing). Spamming R2 at a teammate's combat POV produces the SAME correlational
structure as genuinely causing the events: the spectated screen is full of the exact flashes / red / motion
you would cause yourself, so your firing correlates with it just as well. The coupling oracles measure
CORRELATION between input and screen events; an active-combat spectate screen SUPPLIES that correlation. B2
keys on "red near the reticle while I fire" — a spectated firefight is full of red. So co-observation +
synced input is indistinguishable from causation, by any correlation metric.

CONCLUSION. The entire correlation-based presence-coupling family (cross-channel latency + per-channel
magnitude) is REFUTED against active-spectate-spam. This is the honest result; recording it straight (cf. the
GCAP honest-negative, the touchpad separation ceiling) is the protocol's credibility.

THE ACTUAL DIFFERENTIATOR — game-state authorship (semantic, not correlational). The one thing that
distinguishes "I caused this" from "I am watching this and mashing along" is a **kill-feed entry crediting the
player's OWN handle** (operator handle: `QorTrola30`). A spectated kill credits the teammate; the dead,
spectating player never appears in the feed as the killer. No amount of R2-spam fabricates your name in the
kill-feed. Required binding: an own-handle kill row appears within the render-latency window AFTER one of your
R2 onsets. Build path: kill-feed OCR (reuse `hud_ocr.py`, pytesseract; tesseract binary + per-game ROI are
operator-gated) -> `killfeed_authorship` oracle -> fuse with (not replace) the coupling channels.

NET. Coupling proves a live human is exercising the controller against a live screen (presence/liveness); it
does NOT prove that screen is the player's OWN game vs a spectated one. Authorship closes that gap. No
FROZEN-v1 / 228B PoAC / chain / IOTX; advisory. Raw corpora stay local.
