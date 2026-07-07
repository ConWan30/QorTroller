---
type: synthesis
id: s-killfeed-authorship-spectate-defeat
title: Kill-feed authorship binding — OCR "you eliminated X" lag-bound to your trigger, the load-bearing defeat for active-spectate
created: 2026-06-28T14:08:00Z
modified: 2026-06-28T14:08:00Z
phase: VSD-LOOP
status: draft
confidence: possible
effort: 60
deployer: 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692
refs: []
---

THE PROBLEM IT TARGETS. The B2 live calibration (audits/trigger-hud-b2-calibration-2026-06-28.md) surfaced the
one negative that runs hot: ACTIVE-COMBAT SPECTATE. Watching a teammate's POV during a firefight and firing
along produced B2 coupling up to 0.261 vs a kill-positive floor of 0.282 — a ~0.02 margin, too thin to
certify. The mechanism is correlational, not causal: your ~20 s-spaced R2 pulls catch the spectated screen's
red markers by chance (or you subconsciously fire in rhythm). B2 keys on a red BLOB and cannot tell "my kill"
from "their kill on a screen I am watching."

THE NOVEL FIX — bind to GAME-STATE AUTHORSHIP, not to a blob. Warzone-class FPS renders a discrete, OCR-able
kill-feed / elimination banner crediting the KILLER by name ("You eliminated X", or the player-name row in the
top-right feed). The new channel asserts: **your trigger must causally precede a kill-feed entry that credits
YOU, within the session render-latency window.** A spectated POV shows the *teammate's* name in the feed when
THEY get a kill — it is never lag-bound to your trigger, and it never carries your handle. The active-spectate
attack collapses because the attacker would have to make the spectated stream print THEIR name in the feed in
response to THEIR trigger — which only happens if they are actually the one playing.

WHY THIS is the right layer. It upgrades B2 from "your trigger caused a red thing" to "your trigger caused a
**scored elimination attributed to you**" — a strictly stronger, game-state-bound claim, and the exact
semantic the tournament-integrity and marketplace-provenance surfaces ([[s-retina-presence-cross-purpose-map]])
actually want to buy. It reuses the witness agent's existing tesseract HUD-OCR path (down/distance/clock OCR is
already wired with `--hud-region`); the kill-feed is just another fixed screen region + a name match against
the session's known handle.

DESIGN SKETCH. (1) OCR the kill-feed ROI on each burst; (2) detect a NEW elimination row crediting the session
handle (string match, fuzzy for OCR noise); (3) measure the causal lag from the nearest preceding R2 onset to
the row's appearance; (4) PRESENT-AUTHORED iff that lag falls in the shared render-latency band
([[s-cross-channel-latency-invariant]]) and the handle matches. This is a low-rate, high-confidence channel
(few kills per session) — it does not replace B1/B2, it RESOLVES their ambiguous hot-negatives. Note the
honesty caveat from the sensor-stack anchor: HUD OCR needs the kill-feed region per game/HUD-scale, and the
handle string must be configured, not inferred.

OPEN GATE (`possible`). Unbuilt; depends on tesseract availability + a per-game kill-feed ROI + handle config.
Risk: kill-feed also shows DEATHS and teammate kills — the name-match + "credits YOU" filter is load-bearing
and must be tested against a spectate session where teammate names appear. First pass: OCR-log the feed region
during a real match and confirm own-kill rows are detectable and lag-bind to R2, vs a spectate session where
they must NOT. No FROZEN-v1 / 228B PoAC / chain / IOTX touched; advisory presence layer only.
