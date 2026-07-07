# RP-CLOSE-1 — Remote Play Anti-Cheat Closure Ledger

**Opened: 2026-07-07.** The workflow: the 7 gates from the RP readiness assessment become
a machine-tracked closure ledger (HWFL-1 Sensor C discipline applied to the RP claim);
each session closes the cheapest open gate first. Honest framing throughout: the presence
half of QorTroller is RP-proven; the authorship/PoSP half is HDMI-proven and RP-unproven
(M12 failed under RP for measured contention reasons; M13 succeeded by bypassing RP).

## Gate states

| Gate | Title | State | Evidence |
|------|-------|-------|----------|
| RP-1 | Capture-topology decision | **OPERATOR-DECISION** | `docs/rp-close-1-topology-decision-2026-07-07.md` (D-RP-1; rec: B-then-A) |
| RP-2 | Match 14 under actual RP (AUTHORED + SYNCHRONIZED) | **RIG-GATED** (blocked by RP-1 + RP-5 pass) | Launch stack per C-3.2 runbook; success = AUTHORED_SESSION + PoSP SYNCHRONIZED + published RP recall floor |
| RP-3 | OCR precision on RP-encoded frames | **CLOSED (precision half) 2026-07-07** — bar HELD 0 FP/151 RP-era crops; recall rate deferred to RP-2's archive | `audits/rp-ocr-precision-scan-report-2026-07-07.md` |
| RP-4 | Cross-lobe latency calibration (USB-direct, then RP delta) | **RIG-GATED** | Feeds fusion window + recoil-precognition band (human Δ∈[+80,+280]ms vs macro Δ≤0) |
| RP-5 | Match preflight gate (contention hygiene) | **CLOSED 2026-07-07** | `l9_presence/match_preflight.py` + `scripts/match_preflight.py`, 11/11 tests; first live run surfaced F-RP5-1 |
| RP-6 | Adversarial pairing vs RP-encoded replays | **RIG-GATED** (corpus capture) | B2 anti-GCAP property to be validated vs real RP replay, not synthetic only |
| RP-7 | Claim-limiting rails (independence / population / PoEP / AIT) | **TRACKED — own arc** | C-4.2 `advisory_presence_confidence.py` encodes honestly; verifier_independence=False by design |

## Findings

- **F-RP5-1 (2026-07-07, preflight first live run):** bridge DB regrown to **5.3GB** —
  the cycle-49 per-record-write lag source is back. Action before any Match 14:
  fresh `DB_PATH` override (same fix that worked in cycle-49). The preflight gate now
  catches this class mechanically on every run.

- **F-RP3-1 (2026-07-07, scan):** M12's RP archive is precision-clean but
  readability-unanswerable — 35 crops over a full match is too sparse to distinguish
  "codec degraded the glyphs" from "no kill rows sampled." The honest readability answer
  needs RP-2's match (denser RP archive). Precision claim stands: zero canon-matched
  reads on codec noise = zero hallucinations = the ABSTAIN discipline held.

- **RP-3 result (2026-07-07):** 151 RP-era crops (M12 35 + M11 116), **0 false reads**,
  5 genuine own-kill killer-slot reads through fps-collapsed RP capture — exactly
  reproducing the prior ad-hoc M11 fast scan with a committed re-runnable script.
  The "v6 hallucinates on RP macroblocking" risk did not materialize.

## Session log

- **2026-07-07 (session 1):** Ledger opened. RP-5 built+tested+closed (11 tests; live
  run → F-RP5-1). RP-3 scan run over M12 (35 crops) + M11 (116 crops) RP-era archives.
  RP-1 decision artifact drafted (D-RP-1 open, rec B-then-A). RP-2/4/6 queued rig-gated.

## Next-cheapest open gate

**RP-1** (operator picks D-RP-1 — zero build cost) → unblocks **RP-2** (Match 14, the
claim-converting proof). Rig protocol: preflight must pass (`python
scripts/match_preflight.py --capture-dir <fresh>`), fresh DB_PATH, VPN off,
kill stale processes — and never launched unannounced.
