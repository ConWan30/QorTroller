# F-MATCH-3 recall mining → ROOT CAUSE FOUND + FIXED — 2026-07-13

**Question:** why did the scored match read 34 feed lines but author 0 of the operator's kills?
**Answer:** the live OCR never saw the feed — it read a 5×-downscaled thumbnail. The names, the
fold, and the HARD-1 exact-equality rule were all fine.

## The mining (session_1783982308, 76 full-res ring crops)
Swept every crop through the SAME rapidocr path (`killfeed_raw_reader.read_rows`) + canon:
- **`Qortrola30` reads EXACTLY** (canon `q0rtr01a30`, exact match) in dozens of rows.
- **Killer-slot kill rows crediting the operator, plainly readable:** `Qortrola30 → Megaooo1234`,
  `→ 4leFtyCWC`, `→ Richlewis_ Xx`, `→ NO_M3RCY`, `→ Deadeye225br` (feed shows downs+finishes in
  Resurgence; operator's scoreboard said 2 kills — the feed credits more events than scoreboard
  kills, expected).
- Death rows + roster lines (`'3', 'Qortrola30'`) also present — correctly NOT authorship.

## The root cause (one line)
`qortroller_retina_capture.py` stashed the killfeed crop from **`buf_small`** — the
governor-downscaled frame. The session log recorded `downscale: 5` under GPU pressure → the live
`_kf_bgr` was ~1/5 resolution. **Empirical proof pair (same crop, same OCR):**
```
FULL-RES : ['[MxiCo]oebking', 'B00ber9075', … ]  handle exact-match: True
5×-SMALL : []                                    handle exact-match: False
```
The garbage the live session did read (`'iwer'`, `'sha dy'`, CJK noise) = moments of lower downscale.
The **panel path had already fixed this exact bug** (its comment: "buf_small would be ~76px under
GPU-pressure downscale = unreadable") — the kf path never got the same fix.

## The fix (applied)
Stash `_kf_bgr` from the FULL-RES `buf` (mirrors `_panel_roi_crop`). One-line-class change;
watcher's gray-diff unaffected (it downscales internally to 128px for the change signal).
Regression: 97/97 (fresh-trigger + daemon + CLI) · PV-CI 183 · compile clean.

## What this reframes
- The 0/2 self-score stands as the honest record of THAT match — but its cause is now closed, not
  open-ended "OCR fidelity." F-MATCH-3: **ROOT-CAUSED + PATCHED (live re-validation = next match).**
- HARD-1's exact-equality rule is VINDICATED: at full-res the real handle exact-matches; no fold
  loosening needed (the confusable-collision A8 posture unchanged).
- The next match's expected recall is a real number, not a hope: the mined crops prove the feed is
  readable at the resolution the live path now uses.
- `kf_bound_kills` (R2 binding) remains the second gate — dual-connection HID blindness is a separate
  known constraint (AUTHORED needs triggers; SEEN/OWN-credited does not).
