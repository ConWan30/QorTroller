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
| RP-2 | Match 14 under actual RP (AUTHORED + SYNCHRONIZED) | **CLOSED TIER-2 2026-07-07** — PoSP SYNCHRONIZED under RP (FIRST EVER, Arc A VERIFIED 7/7); KAS authored 0/11 at K=3 (F-RP2-1: RP thins crops-per-kill; density is the binding constraint); 38.6fps validates the M12 remediation | `audits/rp-close-1-match14-report-2026-07-07.md` |
| RP-3 | OCR precision on RP-encoded frames | **CLOSED (both halves) 2026-07-07** — precision 0 FP/564 RP-era crops; readability CLOSED by M14's dense archive (29 reads/15 clusters over 11 kills — codec is not the constraint) | `audits/rp-ocr-precision-scan-report-2026-07-07.md` + M14 report |
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

- **F-RP2-1 (2026-07-07, Match 14):** Remote Play's tax is **crops-per-kill, not
  readability, not contention, not code**. Reads-per-cluster 1.93 (M14 RP) vs 2.85
  (M13 HDMI) at identical engine/thresholds → only 4/15 clusters reach K=3 → live
  authored 0/11 despite 2 live reads, 45 classifications, 7 R2 windows, 38.6fps.
  Archive ceilings: K=3 36%, K=2 64%. The Option A sidecar buys exactly this density
  — the B/A delta is now measured, not hypothesized.

- **D-RP-2 (parked, NOT taken):** lowering live K under RP. K=2 would attest ~7/11
  but any K change on a certificate path needs its own adversarial re-pairing first
  (splice-FAR at K=2 unmeasured — C1/B8 discipline). Option A preferred.

- **Topology learnings (baked into runbook):** the daemon SPAWNS its own lean bridge —
  daemon-only launch IS the stack (a separately-started bridge = port bind failure +
  shared-HID contention); `--kas` is a stop flag; DB_PATH must live in the daemon
  shell's env (spawned bridge + stop-time PoSP issuance both read it).

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

- **2026-07-07 (session 1, cont.) — MATCH 14 RAN LIVE.** Stack launched by Claude at
  operator command (preflight GO_WITH_WARNINGS, two-bridge contention caught+fixed
  live, daemon-solo relaunch). Result: **PoSP SYNCHRONIZED under Remote Play — first
  ever** — Arc A VERIFIED 7/7; KAS INSUFFICIENT_KILLS 0/11 at K=3 (tier-2; F-RP2-1);
  precision bar held 0/413; 38.6fps validates the M12 remediation chain. RP-2 CLOSED
  TIER-2; RP-3 fully closed; LUMEN-1 unblocked. Report:
  `audits/rp-close-1-match14-report-2026-07-07.md`.

## Next-cheapest open gate

**LUMEN-1** (game-state buffer vs archives) — offline, zero rig, corpus in hand
(M13 + M14 + coupling campaign). In parallel: **OA-RP-1** (capture card) unblocks
RP-2b / Match 15 (Option A) for the full-density RP authorship figure that F-RP2-1
priced. RP-4/RP-6 remain rig-gated.

## LUMEN track — meaning-plane gates (opened 2026-07-07, per D-RP-1 follow-through)

Second track under the same closure discipline. Design basis:
`docs/trio-retina-lumen-qortroller-alignment-2026-07-07.md`. Rails inherited unchanged:
observation may suggest, only assertion may claim, meaning belongs to the gamer;
everything advisory + default-OFF until calibrated; no perception output touches
`presence_score`, classification windows (R2∧B2), or the PoAC/PoSP boundary.

| Gate | Title | State | Unblocked by |
|------|-------|-------|--------------|
| LUMEN-1 | Game-state buffer vs archives (ROI persistence + temporal event clusters; offline, advisory, no flags) | **UNBLOCKED 2026-07-07** (Match 14 done; corpus now M13 524 + M14 413 crops + 92 diag samples) | RP-2 ✓ |
| LUMEN-2 | Structured scene stream + session_id join (scene events emitted from archive replays, commitment-referenced, joined against real KAS/PoSP records) | QUEUED | LUMEN-1 |
| LUMEN-3 | Predictive-coupling study offline (N5: expected-screen-response-given-input vs observed — the anti-GCAP oracle measurement; synthetic -> archive first) | QUEUED | LUMEN-1 (parallel-safe with LUMEN-2) |
| LUMEN-4 | Live perception on the sidecar node (retina perception ON in the witness box; first real `retina_perception_root` in a PoSP record; ioID registration scoped) | HARDWARE-GATED | RP-2b / OA-RP-1 (capture card) |
| LUMEN-5 | Meaning-plane sovereignty (consent-category registration + φ-class sanitization for derived session intelligence, BEFORE anything external) | QUEUED | LUMEN-2 |

Honest scale note: LUMEN-1..3 are session-scale offline builds against existing corpora
(M13's 524 crops + Match 14's archive + the coupling-campaign corpus). The general
world model beyond the narrow game-state model is a roadmap, not a gate — it earns
entry only after LUMEN-1..3 produce calibrated keep.

## OPERATOR-ACTION box

- **OA-RP-1:** Acquire HDMI/USB capture card (≈$20–150) for the Match 15 Option-A rerun
  (sidecar-device witness of the RP client output). No deadline; Match 14 does not wait.
  Convergence note (2026-07-07): this box is also the seed hardware of the trio-retina
  perception node — one purchase serves both the RP recall ceiling and the future
  DePIN gaming-witness-node track. See
  `docs/trio-retina-lumen-qortroller-alignment-2026-07-07.md` (N3).
