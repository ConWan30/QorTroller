# F-T66B-1 observation-recall CLOSED — the 17-kill match, 2026-07-13

**Three sessions of empirical recall history:**
| session | witnessed own-kills / scored | pipeline state |
|---|---|---|
| T6.6b (M-t66b4, 21 kills) | **0 / 21** | tune-tick throttle (~2 reads/match) |
| 2-kill match (today) | **0 / 2** | fresh-trigger live BUT reading 5x-downscaled thumbnails |
| **17-kill match (today)** | **~17 / 17** | fresh-trigger + FULL-RES stash (F-MATCH-3 fix) |

**The 17-kill match's evidence:** 426 sink rows · 205 conformant v3 events · **117 raw own-kill
reads** (`Qortrola30` exact-canon killer) → fold-collapsed to ~21 distinct victims ≈ the 17
scoreboard kills (+ OCR variants + Resurgence downs-vs-finishes). Deaths (11) and others' kills
(298) separated correctly. Oracle live verdict `AUTHORED_PRESENT, own=128, bound=3`.
PoSP SYNCHRONIZED (140 fusion rows). grok live-spectated (first AI second-witness session; log:
`audits/a2a_spectator_log_17kill_match_2026-07-13.md`) and called the operator's kills in real time.

**The honest layering (why the scorecard still prints authored 0/17):**
- WITNESSED (observation) ~17/17 — F-T66B-1's recall gap is empirically CLOSED.
- BOUND (causal R2→kill) = 3 — dual-connection HID passes only fragments (known constraint).
- AUTHORED (KAS strict = bound + hygiene) = 0 — the hygiene bar refuses dual-connection HID.
The scorecard prints the STRICTEST layer and tags every number — working as designed. The remaining
path WITNESSED→AUTHORED runs through HID topology (USB-only sessions / PoEP presence), not OCR.

**New finding F-MATCH-5 (label collision):** the default label "session" makes same-day artifacts
overwrite (`kas_record_session_2026-07-13.json` etc. — the 2-kill match's versions live only in git
history at `90f772d9`). Fix: default label should carry the stamp (label_prefix already supports it);
route to the next PKG round.

**Zero-false-read held again:** 426 rows, no false authorship of another player.
