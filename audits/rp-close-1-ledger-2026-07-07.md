# RP-CLOSE-1 — Remote Play Anti-Cheat Closure Ledger

**Opened: 2026-07-07.** The workflow: the 7 gates from the RP readiness assessment become
a machine-tracked closure ledger (HWFL-1 Sensor C discipline applied to the RP claim);
each session closes the cheapest open gate first. Honest framing throughout: the presence
half of QorTroller is RP-proven; the authorship/PoSP half is HDMI-proven and RP-unproven
(M12 failed under RP for measured contention reasons; M13 succeeded by bypassing RP).

## Gate states

| Gate | Title | State | Evidence |
|------|-------|-------|----------|
| RP-1 | Capture-topology decision | **CLOSED 2026-07-07 — D-RP-1: B-then-A** (operator) | `docs/rp-close-1-topology-decision-2026-07-07.md` |
| RP-2 | Match 14 under actual RP (AUTHORED + SYNCHRONIZED) | **READY — awaiting rig** (Option B; Match 15 = Option A rerun after capture-card acquisition) | Runbook: `docs/rp-close-1-match14-runbook.md` |
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
  Committed `cbad38e8` (13 files, +1328).
- **2026-07-07 (session 1, cont.):** **D-RP-1 DECIDED: B-then-A** (operator). RP-1
  closed. Match 14 runbook written (`docs/rp-close-1-match14-runbook.md`) — Option B,
  full pre-match/launch/stop/post-audit chain incl. F-RP5-1 fresh-DB mitigation and the
  NQPV_COCAPTURE_ENABLED lean-mode gotcha (fusion surface needs it or SYNCHRONIZED is
  unreachable). Match 15 (Option A) queued behind capture-card acquisition.

## Next-cheapest open gate

**RP-2** (Match 14, Option B) — everything code-side is ready; needs only the operator
at the rig. Protocol per the runbook: preflight GO, fresh DB_PATH, VPN off, lean bridge
with NQPV co-capture ON — and never launched unannounced. After Match 14: rerun the
precision scan on its archive (closes RP-3's readability half), then Match 15 = Option A.

## OPERATOR-ACTION box

- **OA-RP-1:** Acquire HDMI/USB capture card (≈$20–150) for the Match 15 Option-A rerun
  (sidecar-device witness of the RP client output). No deadline; Match 14 does not wait.
  Convergence note (2026-07-07): this box is also the seed hardware of the trio-retina
  perception node — one purchase serves both the RP recall ceiling and the future
  DePIN gaming-witness-node track. See
  `docs/trio-retina-lumen-qortroller-alignment-2026-07-07.md` (N3).
