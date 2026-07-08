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

## RP-2c / RP-2d — card-free authorship gates (opened + executed 2026-07-07)

| Gate | State | Evidence |
|------|-------|----------|
| RP-2d deferred-attestation tier | **CLOSED 2026-07-07** — M14 **DEFERRED_AUTHORED_SESSION 3/11** (conjunction-preserving; +1 OBSERVED); M13 cross-check PASSED (deferred 9 ⊇ live 8); verifiers OK (20+59 checks); 12 tests | `audits/rp-close-1-rp2d-report.md` |
| RP-2c window-gated densification | **CODE SHIPPED, default-OFF** — Fix A REFUTED (F-RP2C-1: live classify already full-res); Fix B = `RETINA_KF_EVERY_BURST` + burst-thread flush-on-new-stash; anti-splice rail pinned (test caught a real sentinel bug); live validation rig-gated (bar: reads/cluster ≥ 2.5) | same report |

## LUMEN track — meaning-plane gates (opened 2026-07-07, per D-RP-1 follow-through)

Second track under the same closure discipline. Design basis:
`docs/trio-retina-lumen-qortroller-alignment-2026-07-07.md`. Rails inherited unchanged:
observation may suggest, only assertion may claim, meaning belongs to the gamer;
everything advisory + default-OFF until calibrated; no perception output touches
`presence_score`, classification windows (R2∧B2), or the PoAC/PoSP boundary.

| Gate | Title | State | Unblocked by |
|------|-------|-------|--------------|
| LUMEN-1 | Game-state buffer vs archives (ROI persistence + temporal event clusters; offline, advisory, no flags) | **CLOSED 2026-07-07** — `game_state_buffer.py` + runner; M14 403 events / M13 484 events, joins OK; F-LUMEN-1 panel-scale threshold noted (LUMEN-2 refinement) | RP-2 ✓ |
| LUMEN-2b | LIVE match-state tracker (`l9_presence/match_state_live.py` + `scripts/watch_match_state.py`) | **CLOSED 2026-07-08 (rig-free)** — KC-2b-1: live span-snapping is retroactive, so every transition carries ts_ms AND detected_at_ms (truth late beats guess early); ENDED withheld until forward exit-gap confidence. **Validated by replaying M14's REAL logs through a simulated clock:** MATCH_STARTED @20:49:55 confirmed +10s; MATCH_ENDED @20:57:35 confirmed +240s; exactly 2 transitions, zero flap through the 183s rotation. 7 tests. A2's live run is the confirmation, not the first test | replay output in ledger; `--replay` re-runs it |
| LUMEN-2 | Structured scene stream + session_id join (scene events emitted from archive replays, commitment-referenced, joined against real KAS/PoSP records) | **PARTIAL 2026-07-07** — join check shipped inside LUMEN-1; **match-state detector v0 CLOSED** (`l9_presence/match_state.py` + runner): M14 MATCH_ENDED within 1s of KAS evidence end (460s match + 233s lobby tail correctly split); M13 one 710s match, 18/18 anchors + 30/30 windows contained; **F-LUMEN-2** (post-match handle sightings — K15 @ match+4min; anchor discipline = K≥2, sightings reported separately; RP-2d's K≥3+conjunction rails already excluded it, validating the tier). Remaining: panel-threshold study (F-LUMEN-1) + live advisory annotator variant | LUMEN-1 ✓ |
| LUMEN-3 | Predictive-coupling study offline (N5: expected-screen-response-given-input vs observed — the anti-GCAP oracle measurement; synthetic -> archive first) | QUEUED | LUMEN-1 (parallel-safe with LUMEN-2) |
| LUMEN-4 | Live perception on the sidecar node (retina perception ON in the witness box; first real `retina_perception_root` in a PoSP record; ioID registration scoped) | HARDWARE-GATED | RP-2b / OA-RP-1 (capture card) |
| LUMEN-4b | Perception root rolled AT ISSUANCE — daemon stop wired via the shared engine (`lumen4a_perception_root.roll_perception_root`; fail-open: no perception data = honest null, never fabricated; M14 anchor `4f335588…` is the regression check) | **WIRED 2026-07-07** — next `--kas` session's PoSP is the first born with BOTH named roots populated (validation = the Fix B rig match) | `scripts/retina_capture_daemon.py` `_issue_posp` + 6 tests |
| LUMEN-4a | Trio pipeline over session data -> first non-null retina_perception_root CANDIDATE | **CLOSED 2026-07-07** — M14's perception pipeline ran LIVE (299 retina_event_log rows / 46,483 trio-retina-model events incl. 44 trigger onsets); root `4f335588…` rolled via existing sha256_v1 `compute_events_root`; join: session_id match + 98/200 PoSP fusion refs carry perception rows; issued PoSP stays honestly null (immutable — a future session carries it live). M13: honest no-data (pipeline not armed then). Trio-Lumen product announced same day (NOT open-sourced; building blocks are; hosted-Lumen feeds consent-gated per LUMEN-5) | `audits/retina_perception_root_candidate_match14_*.json` |
| LUMEN-5 | Meaning-plane sovereignty (consent-category registration + φ-class sanitization for derived session intelligence, BEFORE anything external) | QUEUED | LUMEN-2 |

Honest scale note: LUMEN-1..3 are session-scale offline builds against existing corpora
(M13's 524 crops + Match 14's archive + the coupling-campaign corpus). The general
world model beyond the narrow game-state model is a roadmap, not a gate — it earns
entry only after LUMEN-1..3 produce calibrated keep.

## EDGE-SENSE track — the controller as perception hardware (opened 2026-07-07)

The operator's existing DualSense Edge prototyped as Lumen/Retina hardware: cause-lobe
sensor + haptic-echo witness (game -> haptic actuation -> IMU signature — a
screen-independent, capture-contention-immune event lobe INSIDE the signing device).
Design + first probe: `docs/edge-sense-controller-as-perception-2026-07-07.md`.

| Gate | Title | State | Unblocked by |
|------|-------|-------|--------------|
| ES-P0 | RP haptic-forwarding premise (fire a weapon, feel it — never assumed) | **OPERATOR, ~2 min** | — |
| ES-P1 | Mine already-captured M14 data | **CLOSED 2026-07-07** — substrate confirmed (334 IMU-feature records); F-ES-2 sparse flag, F-ES-3 idle tail (23% over haptic threshold; game haptics / grip / Cycle25 tether candidates), F-ES-4 120Hz spectral ceiling | — |
| ES-P2 | Instrumented 1000Hz capture, 4 segments (tether-on idle / tether-off idle / firing / damage-taking) | RIG-GATED (~15 min; can share rig time with any match session) | ES-P0 |
| ES-P3 | Haptic-vs-tremor separation study (>=10x band-power bar, zero false events on idle) | QUEUED | ES-P2 |
| ES-P4 | Three-lobe alignment (echo x screen x HID on session_id) — IS LUMEN-3's third channel | QUEUED | ES-P3 (merges with LUMEN track) |
| ES-W | Advisory oracle wiring (EchoEvent -> NQPV active_oracles, default-OFF) | GATED on P0–P4 green | ES-P4 |

## ACT-1 — IoTeX Activation Ladder (opened 2026-07-08)

The workflow: dormant IoTeX-connected machinery gets pointed at the evidence the RP/LUMEN
arcs now produce — one rung at a time, each rung carrying its BRAINSTORM LOG
(hypothesis -> kill-check -> flip -> observed impact), so activations keep their reasoning
the way arcs keep their findings.

| Rung | What | State |
|------|------|-------|
| A1 | Flag activations (DA witness / BCC / replay pipeline) | **CLOSED 2026-07-08** — see brainstorm log |
| A2 | Rig match (validates Fix B + ES-P0/P2 + live match-state + first dual-rooted PoSP + now BCC-witness/DA exercise) | RIG-GATED, operator-announced |
| A3 | Anchor M14 PoSP digest on IoTeX | **FIRED 2026-07-08 (operator GO)** — tx `98fab4111c211a6aa38b006b7f9f6e9630dedc06aa2bfcd206eea567e71f5a2d`, block **45438141**, status 1, gasUsed 143115, cost **0.143 IOTX** (wallet 29.670671 → 29.527556, live-verified); payload = SHA-256(record file) `1667147a…` via AdjudicationRegistry `recordAdjudication`; kill-switch line in bridge/.env verified UNCHANGED (process-scoped gates only); anchor manifest `audits/posp_anchor_match14_*_anchor.json`. **The first Remote-Play-born synchronized presence proof is now a public on-chain record.** A3-b (beacon-bind wiring) still queued. Was PREPARED same day: — `scripts/anchor_posp_commitment.py` estimate-only ran clean against live IoTeX: payload=SHA-256(record file)=`1667147a…`, est **0.1789 IOTX** (gas 143115×1.25 — matches Guardian Tier-2's historical gasUsed exactly), revert-guard PASS, wallet 29.670671 live. **KC-A3-1:** PoSP has NO commitment method BY DESIGN — the anchor is an EXTERNAL file digest (no schema change, no new tag); anchor manifest documents the preimage. Fire = one command + triple gate + operator GO |
| A4 | Arc 5 VHR trusted-setup ceremony (operator-interactive ~1h; then inner verifier deploy joins A3-class session) | QUEUED, any quiet hour |
| A5 | Sentry/Curator autonomous O3 (two-key: per-agent flag AND kill-switch; 0.05 IOTX/day caps) | PARKED until A3-class anchoring is routine |

### A1 brainstorm log (the kill-checks that reshaped the rung)

- **KC-1:** "flip three flags" -> verified names in code first. Two are real env bools
  (`RETINA_DA_WITNESS_ENABLED` config:2041, `REPLAY_PROOF_PIPELINE_ENABLED` config:2264);
  **BCC had NO env wire** — `enabled=False` was a dataclass-only default (F-ACT-1).
- **KC-2:** BCC's host is the **Witness lane** (`witness_agent.py`), NOT the match flow —
  "every match harvests" was wrong. Witness-lane activation is real but narrow; the
  match-lane harvest adapter (nqpv/session-close -> BCC) is queued as **A1-b** follow-up.
- **KC-3 (the good surprise):** `.env` already had BOTH real flags set `true` — and M14's
  329 `retina_da_witness_log` rows prove the DA witness RAN during the match. Two thirds
  of the "activation" was already live; the menu met reality and shrank to one honest wire.
- **Flip executed:** `WitnessConfig` gains `BCC_ENABLED`/`BCC_SUBLANE_B_ENABLED` env reads
  (code default stays OFF; env only opts in; sublane B independent) + `BCC_ENABLED=true`
  appended to `bridge/.env` (gitignored — config change, not a commit). 4 new tests;
  witness+bcc regression 30/30; PV-CI 182 PASS.
- **Impact now live:** any Witness-processed PRESENT+reliable session harvests into the
  sealed BCC lane (corpus growth for the population studies gating the biometric roadmap);
  DA witness + deferred replay pipeline confirmed already-active on the match path.

## SESSION-REPORT capstone + A3-b (built 2026-07-08, offline continuation)

| Item | State |
|------|-------|
| A3-b beacon-bind | **WIRED** — PoSP gains additive-optional `temporal_beacon` field (advisory recency REFERENCE, not PoSR §1.2 commitment math — labeled inline); daemon `_fetch_latest_beacon()` view-call (zero IOTX, fail-open). **KC-A3b-1:** live read returned block 45,026,880 — the keeper's LAST run; beacon freshness = keeper cadence; when recency matters, a pre-match keeper single-shot (~0.005 IOTX) is the operational answer |
| Per-match slicing | **BUILT** — `slice_scan_by_spans` (pure, in kas_deferred): multi-match sessions slice into per-match deferred records; outside-match clusters honestly bucketed, never dropped. Cores unchanged — composition only |
| Session-close report | **BUILT + VALIDATED on M14** — `scripts/session_close_report.py`: one command -> PoSP 7/7 + match timeline + session & per-match deferred attestation + perception-root recompute (matched the anchored `4f335588…`) + beacon ref + honest GAP list. The casual-product "personal integrity certificate" seed, running today. `audits/session_report_match14_*.md` |

Next `--kas` session now mints: both named roots + beacon ref + auto-reportable in one
command. Remaining offline: A1-b (BCC match-lane, own design pass), F-LUMEN-1 threshold
study, LUMEN-3/N5 study, RP-6 harness prep.

## OPERATOR-ACTION box

- **OA-RP-1 (DEMOTED TO OPTIONAL 2026-07-07 — operator has no funds; roadmap
  re-planned card-free):** HDMI/USB capture card (USB — no internal slot needed;
  cheapest ~$20) remains the *someday* path to live full-density RP attestation +
  the sidecar witness node (trio alignment N3). Nothing on the board requires it.
  The card-free replacements: **RP-2c** (software densification — killfeed-ROI-priority
  capture + window-gated dense bursts on the same laptop) and **RP-2d**
  (deferred-attestation tier — the archive is manifest-committed live evidence;
  M14's sealed archive already holds 4/11 kills at K=3 with 0 false reads =
  DEFERRED_AUTHORED 36%, honestly labeled vs live AUTHORED). Match 15/Option A
  parks until funds exist; RP-2b task parked accordingly.
