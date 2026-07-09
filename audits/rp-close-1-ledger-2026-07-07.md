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
| RP-7 | Claim-limiting rails (independence / population / PoEP / AIT) | **CLOSED-AS-ENCODED 2026-07-08** — the rails are now MACHINE-READABLE, not prose: C-4.2 `advisory_presence_confidence.py` (AIT=LOW w/ FAR/FRR pinned not-usable; PoEP/L6B UNCALIBRATED N=0; OPERATING_CONSERVATIVE), `verifier_independence=False` + `cert_scope=developer_self` + `population_certified=False` on every fused proof, `advisory=True` on PoSP/deferred/scene/match-state records. Every new artifact this arc inherited them. The gate's residue is the LONG-ARC work itself (witness-node independence, population corpus) — tracked on ES/LUMEN/OA rows, not here | C-4.2 + record fields |

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
| RP-2c window-gated densification | **CLOSED 2026-07-08 (M17)** — Fix B VALIDATED live: 2.08/s in-window vs 0.53 outside (3.9×), 7.5 reads/cluster (bar was ≥2.5) → live authored 17/18. **F-FIXB-1 FIXED same day**: dedicated 0.15s flush thread unbinds the flush from the ~1s classify worker (spawns only when armed+capture; NO flush after stop() — the lifecycle test caught the shutdown race on first run, fixed); next match should approach the ~5-6/s stash-limited ceiling | M17 report + 2 lifecycle tests |

## VHR-PROOF-2 CLOSED (2026-07-08) — real proof over M17's ACTUAL matrix

The VHR arc is now complete end-to-end on real data: 27,672 real M17 HID frames → φ →
**1,730-tick** SanitizedReplayMatrix + real 463-record PoAC chain root → Groth16 proof
(token `0x0e675e6a…`, 256 bytes) → `snarkjs verify` **OK!**. M17 now carries FIVE proofs
of one session: SYNCHRONIZED presence + 17/18 live authorship + fully-rooted PoSP +
on-chain anchor (block 45447322) + this ZK replay proof. Privacy: only the 6-element
zero-knowledge public.json + proof.json committed; the matrix-bearing private/circuit
inputs computed locally + deliberately UNCOMMITTED. consentPolicyHash=0 + humanity=0.92
are demo placeholders (floor math real); 0 IOTX; submission operator-gated.
`audits/vhr-proof-2-real-m17-matrix-2026-07-08.md`.

## VHR-PROOF-1 CLOSED (2026-07-08) — first real Groth16 replay proof

The last dormant arc (Arc 5, 2026-05-29) awoke: `Groth16Prover.prove()` ran real for the
first time — token `0x22f3c60d…`, 256 proof bytes, `deferred_reason=None` — and
`snarkjs groth16 verify` returned **OK!** against the ceremony VK. Both rails held
(humanity 0.92 mints + verifies; 0.50 → deferred, no proof producible). KC-VHR-1: the
whole prover + 5 artifacts were already populated (another verify-before-building find);
the deliverable was EXECUTING the first proof, not writing the helper. Honest scope: an
8-tick synthetic matrix (M17-labeled) — a full M17-matrix proof (VHR-PROOF-2) needs the
pre-processor over `bridge_match17.db`. 0 IOTX; verifiers already on-chain (A4);
submission is operator-gated. `audits/vhr-proof-1-first-real-proof-2026-07-08.md`.

## A3 second anchor (2026-07-08, operator GO)

**Match 17's PoSP anchored:** tx `da3a8547db86a95bb5057c0e85ef45d436a865231241bdca6b596742aef6959c`,
block **45447322**, status 1, gasUsed 126015 (estimate exact), ~0.126 IOTX (wallet
29.527556 → 29.401541 live-verified). Payload = SHA-256(record file) `545f9d44…`.
Kill-switch line verified UNCHANGED. Both flagship sessions (M14 SYNCHRONIZED-first +
M17 17/18-live-authorship) are now permanent public records — record file → verifier
7/7 → digest → chain, no trust required anywhere in the walk.

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
| LUMEN-3 | Predictive-coupling study (N5) | **Increment 1 CLOSED 2026-07-08 — HONEST NEGATIVE** (`audits/lumen3-n5-lag-structure-study-2026-07-08.md`): pre-registered lag-consistency bar MISSED on all 3 channels (426 genuine vs 213 spectate windows), direction partially inverted. **F-N5-2 (the lesson):** the lag estimator has a zero-default degeneracy — consistency rewards the degenerate case; 5s windows aggregate multiple fire events = wrong unit of analysis. **Increment 2 GATED on RP-4** (per-event latency, USB-direct first — the rig item is now the DEMONSTRATED prerequisite, not an assumption). Machinery + pre-registration retained (`predictive_coupling.py`, 8 tests) | LUMEN-1 ✓ |
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
| ES-P3 | Haptic-vs-tremor separation study | **CLOSED 2026-07-08 — PRE-REGISTERED BAR MET** (`audits/es_p3_spectral_result.json`): haptic-band (30-200Hz) fire/idle ratio **40.4×** (bar ≥10×); zero-false on idle **HELD** (0/602 windows at idle-max×1.5); fire events 9% of windows (burst cadence). **F-ES-P3-1 (honest caveat):** tremor-band control also rose 10.3× (recoil/hand motion confound) — the 40× vs 10× margin + M15's in-match 49Hz support the motor interpretation, and deferred seg-3 (damage rumble while STILL) is now the precisely-scoped disconfound stimulus | ES-P2 segs 1+2 ✓ |
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
| A2 | Rig match (six-surface validation) | **CLOSED 2026-07-08 (Matches 15+16+17)** — M17: **AUTHORED_SESSION 17/18 LIVE under Remote Play** (94.4% at K=3; was 0/11 at M14); **Fix B VALIDATED** (RP-2c CLOSED: 2.08/s in-window vs 0.53 outside = 3.9× gated densification; 7.5 reads/cluster vs 1.93; 908 crops, 0 suspects — largest precision test yet); tiers CONVERGE (live 17 = deferred 17; perception-root recompute = MATCH; session report ZERO GAPs, first time); link-guard protocol proven (M15 flip caught+survived, M16 unplug → honest HYGIENE_FAIL, M17 clean). Reports: match15/16-in-15/17 | `audits/rp-close-1-match17-report-2026-07-08.md` |
| A2-M15 | (superseded detail) | **PARTIAL 2026-07-08 (Match 15)** — an ACCIDENTAL TRUE-NEGATIVE, the strongest validation nobody staged: controller link silently flipped to BT-PS5 at ~25s; operator played 13 kills + felt haptics; system honestly refused everything (IMPLAUSIBLE all match, 0/13 attested, 0 windows) while kills were visible on screen (12 archive reads, 0 false; first-ever suspect = l→i confusable of own handle, adjudicated genuine — bar HOLDS). **First fully-rooted PoSP minted live** (perception root `a5957a7c…` from 119,928 events + beacon ref — LUMEN-4b + A3-b working at issuance). **ES-P0 CLOSED**: RP forwards haptics AND the IMU measured them (median tremor 48.94Hz in-match vs 0 pre — the echo lobe works in exactly the failure mode that blinds the input lobe, F-M15-2). **Fix B UNTESTED** (no windows) — rerun w/ link-guard protocol (report §Open) | `audits/rp-close-1-match15-report-2026-07-08.md` |
| A3 | Anchor M14 PoSP digest on IoTeX | **FIRED 2026-07-08 (operator GO)** — tx `98fab4111c211a6aa38b006b7f9f6e9630dedc06aa2bfcd206eea567e71f5a2d`, block **45438141**, status 1, gasUsed 143115, cost **0.143 IOTX** (wallet 29.670671 → 29.527556, live-verified); payload = SHA-256(record file) `1667147a…` via AdjudicationRegistry `recordAdjudication`; kill-switch line in bridge/.env verified UNCHANGED (process-scoped gates only); anchor manifest `audits/posp_anchor_match14_*_anchor.json`. **The first Remote-Play-born synchronized presence proof is now a public on-chain record.** A3-b (beacon-bind wiring) still queued. Was PREPARED same day: — `scripts/anchor_posp_commitment.py` estimate-only ran clean against live IoTeX: payload=SHA-256(record file)=`1667147a…`, est **0.1789 IOTX** (gas 143115×1.25 — matches Guardian Tier-2's historical gasUsed exactly), revert-guard PASS, wallet 29.670671 live. **KC-A3-1:** PoSP has NO commitment method BY DESIGN — the anchor is an EXTERNAL file digest (no schema change, no new tag); anchor manifest documents the preimage. Fire = one command + triple gate + operator GO |
| A4 | Arc 5 VHR trusted-setup ceremony | **VERIFIED-COMPLETE-PRIOR 2026-07-08 (ACT-1 KC-4** — same species as KC-3: verify before doing, find it done): BOTH ceremonies already ran (v1 full chain `_0000..._0002→final`; v2 with transcript + IoTeX block-45008286 beacon, 2026-06-25) and ALL FOUR contracts are DEPLOYED (v1 inner `0xcE56404C…` + wrapper `0x5182372d…`; v2 inner `0x55A15cC8…` + wrapper `0xf4106736…`). **v1 zkey re-verified today: `snarkjs zkey verify` → ZKey Ok!** The ONE remaining VHR gap, precisely named: **VHR-PROOF-1** — the circomlibjs Poseidon inputs helper (Phase 237 `compute_inputs` pattern) so the real prover replaces DeferredProver and mints the FIRST real Groth16 replay proof (target: Match 17's session; offline, zero chain). Own build session |
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
command.

## Offline continuation 2 (2026-07-08): F-LUMEN-1 CLOSED + A1-b design-resolved

- **F-LUMEN-1 CLOSED** — panel-threshold study (`audits/f-lumen-1-panel-threshold-study-
  2026-07-08.md`): delta distributions CROSS-TOPOLOGY STABLE (RP p50=47.4 vs HDMI p50=47.2
  — ambient change energy is the game's HUD, not the capture path); kill onsets sit at
  ~p75-p80 (median 68-72); **`PANEL_FRESH_DIFF=63.0`** (cross-topology p75) calibrated +
  wired as runner default. M14 stream: 403 events (0 stable) -> **168 events (36 stable
  segments)** — legible structure. Rail: SCENE_CHANGE is structure, never kill evidence.
- **D-A1b-1 (BCC match-lane): implementation DEFERRED on a decisive kill-check** — L9's
  `_SEP_FEATURES` = 3-feature coupling space; the match flow emits the 13-feature L4
  vector. DIFFERENT spaces: cross-harvesting would poison BCC corpus semantics. Honest
  path = a new sub-lane with its own feature contract + gate (PoSP SYNCHRONIZED +
  coherence fraction) — sized as its own design session, not an adapter. No silent
  approximation.
- **RP-7 CLOSED-AS-ENCODED** (rails machine-readable across C-4.2 + record fields).
- Remaining offline: LUMEN-3/N5 predictive study (next deep arc), A1-b sub-lane design
  session, RP-6 harness prep.

## Offline continuation 3 (2026-07-08): A1-b BCC Match-Lane v0 BUILT (design audited)

grok authored the A1-b design (`docs/a1b-bcc-match-lane-design-2026-07-08.md`); Claude
audited it against the code before implementation, then built v0 on operator GO.

- **Audit (F-A1b-AUDIT-1):** 4/5 "Code truth" citations byte-exact; the 5th (§2.4 L4
  13-key list) matched **no** real bridge constant (`behavioral_archaeologist.FEATURE_KEYS`
  is 9 keys in a different order; `continuity_prover`/`pitl_prover` differ again). Since L4
  attach was already optional, resolution = **ship v0 NONE-only** (assertion-plane only,
  zero controller-internal biometrics; L4 → `artifact-v1` pinned to a real `FEATURE_KEYS`).
  Rubric 10/10; rails clean. Audit-resolution block + inline markers added to the design doc.
- **A1-b v0 BUILT** — `l9_presence/bcc_match.py` (new, pure stdlib): separate sealed lane
  `bcc_match/` (D-A1b-2 — own genesis `QORTROLLER-BCC-MATCH-GENESIS-v0` **candidate tag, NOT
  registered**, formula-twin of BCC v0 so tooling reuses but chains can't concatenate);
  `MatchPresenceArtifact` typed payload (`qortroller-bcc-match-artifact-v0`); fail-closed
  admission G1–G6 (**PoSP SYNCHRONIZED-only** + authorship non-empty + **coherence ≥ 0.50**
  pre-registered + no inherited HYGIENE_FAIL + session-id anti-assertion); NOMINAL-only
  writes; `record()` refuses (LOUD) any non-NONE contract or L9 payload (poison rail).
- **Isolation-as-architecture:** parallel `BCCMatchStore` (never imports tournament writers);
  writes only to `out_dir`; `advisory=true` / `cert_scope=developer_self` /
  `population_certified=false` on every row. `.gitignore bcc_match/`.
- **Host:** standalone runner `scripts/bcc_match_harvest.py` (fail-OPEN — harvest error never
  breaks anything); session-close auto-hook deferred (minimize touch, reversible).
- **VALIDATED on real M14 (the honest RP card-free path):** live KAS `INSUFFICIENT_KILLS`
  (0/11 live under RP — F-RP2-1 starvation) would fail live-only, but the **deferred tier
  carries admission** — `DEFERRED_AUTHORED_SESSION`, authored 3 / eligible 4 → **coherence
  0.75 ≥ 0.50** → tier=DEFERRED, BUILT, NONE-only. Exactly the §6.2 design rationale, on
  real data. Enabled write-path proven into a temp lane (chain_intact=true).
- **Verify:** `test_bcc_match.py` **29/29** green (poison / M15 / M16 / M17 / PARTIAL /
  isolation / honesty / reference / chain-monotonic / NONE-only); 608 other l9 tests green
  (2 pre-existing `test_cocapture` failures = env `controller` import, unrelated); **PV-CI
  182 PASS**. 0 IOTX, no FROZEN-v1 / no 228B PoAC / no chain write. Committed `3c694c47`.

## Offline continuation 4 (2026-07-09): A1-b artifact-v1 L4 attachment + audit self-correction

- **F-A1b-AUDIT-1 SELF-CORRECTED (honesty):** the artifact-v1 investigation traced the real
  live 13-dim vector — `l9_presence/cocapture.py::compute_l4_features` →
  `controller/tinyml_biometric_fusion.py::BiometricFeatureFrame.to_vector()` — and found the
  design's §2.4 13-key list is **CORRECT** (matches `to_vector()` exactly, line-by-line). Only
  the *attribution* to `bridge/behavioral_archaeologist` (a 9-key SUBSET) was wrong. My original
  "phantom order" framing **overstated** the defect; corrected in the design doc's AUDIT
  RESOLUTION + inline §2.4 marker. **v0 NONE-default still stands** (corpus purity +
  controller-import isolation), so nothing shipped was wrong — the finding's *conclusion* held,
  its *reason* is now accurate.
- **artifact-v1 BUILT** (unblocked by the confirmed source): `bcc_match.L4_SESSION_V13_KEYS`
  frozen tuple = `BiometricFeatureFrame` field order, **pinned by a guarded test**
  (`test_l4_keys_pinned_to_dataclass_field_order` — imports the dataclass and asserts equality;
  RAN + PASSED live where the module loads, skips cleanly in CI-without-controller). L4 attaches
  **additive-optional** on the candidate v0 schema (PoSP A3-b precedent): pass a session-scoped
  13-vector → `feature_contract.name="L4_SESSION_V13"`, dim=13, canonical keys, order preserved;
  omit it → NONE (byte-identical v0 default). `record()` guard loosened to accept ONLY
  {NONE, canonical L4_SESSION_V13}; any off-order/garbage contract still raises (poison rail).
- **Runner:** `--l4-npz <cocapture.npz>` reads a stored `l4_vec` and attaches it (no controller
  import — reads the persisted vector). Smoke: M14 PoSP+deferred + synthetic l4 npz →
  `L4_SESSION_V13`, built, dormant (default-OFF).
- **Verify:** `test_bcc_match.py` **35/35** (29 v0 + 6 artifact-v1); PV-CI **182 PASS**; 0 IOTX,
  no FROZEN-v1 / no 228B PoAC / no chain write. Staged for operator commit.

## Offline continuation 5 (2026-07-09): EVENT-BIND arc opened — cryptographic per-event authorship (increment 1)

New novelty arc (operator-chosen over PORT-CERT / ADVERSARY-EXPAND). The gap the code itself names
(`cocapture_binding`): **presence binds by identifier (session_id); authorship binds by clock.** KAS
today authors a kill by a **temporal ∩** ("composite resolves only inside an R2 window"). EVENT-BIND
gives the on-screen OUTCOME and its causing HID-onset INPUT a **shared PoAC `record_hash` anchor** so
authorship is a cryptographic join, not clock proximity.

- **Honest scope (pinned, `docs/event-bind-design-2026-07-09.md` §2):** CLOSES cross-source **SPLICE**
  (a temporal ∩ provably cannot); **composes** with PoSR recency (Arc 6 beacon) for **replay**
  resistance (not closed alone — a faithful replay carries self-consistent old anchors); does **NOT**
  close a compromised host (verifier_independence=False inherited). No overclaim.
- **Increment 1 BUILT (offline):** `l9_presence/event_bind.py` (pure stdlib, generalizes
  `cocapture_binding`) — `EventBindMode` {RECORD_HASH_PRODUCTION / TEMPORAL_PROTOTYPE / UNBOUND},
  crypto-preferred-over-temporal, per-kill mode + `binding_is_cryptographic` all-or-nothing claim,
  honest banner (the temporal-prototype caveat verbatim). Consumes optionally-present `record_hash`,
  fails open to temporal today.
- **The demonstration (the arc's result):** `scripts/event_bind_splice_demo.py` + a pinned test —
  two corpora with **identical timing** (both 100% temporally bound, same 80 ms offsets); the genuine
  co-capture (shared anchor) is crypto-bound/**splice-proof**, the splice (outcome anchor A + onset
  anchor B) degrades to TEMPORAL_PROTOTYPE. "Separates genuine from splice on the ANCHOR, not the clock."
- **Verify:** `test_event_bind.py` **12/12**; l9 **625 passed** (2 pre-existing cocapture env failures
  unrelated); PV-CI **182 PASS**; 0 IOTX, no 228B PoAC contact (references `record_hash`, never alters
  the wire), no FROZEN-v1 / domain tag / chain write. Staged for operator commit.
- **Increment 1 committed `2ef36e33`.**

**EVENT-BIND increment 2 (2026-07-09) — capture-path stamping SUPPORT (offline core):** the events can
now carry the shared anchor, additive + backward-compat. `hid_onset_event` + `authored_screen_event`
accept an optional `record_hash`, stamped **key-only-when-present** → unstamped events byte-identical,
existing captures' `events_root` UNCHANGED (verified); a stamped session folds the anchor INTO the
events_root/KAS commitment. `HidOnsetDetector.set_record_hash()` stamps live onsets (default None =
byte-identical); `session_hid_events` preserves it; `event_bind.bind_session_events` + row adapters +
`stamp_enabled()` env gate (`EVENT_BIND_STAMP_ENABLED` default OFF). Tested end-to-end (stamped →
RECORD_HASH_PRODUCTION, unstamped → TEMPORAL_PROTOTYPE). **Verify:** `test_event_bind.py` **23/23**
(12 inc1 + 11 inc2); l9 **636 passed** (2 pre-existing cocapture env failures); PV-CI **182 PASS**;
no PV-CI pin on the event shapes; 0 IOTX; no 228B PoAC contact / FROZEN-v1 / chain write. Staged for
operator commit.
- **Remaining (rig / next):** the daemon call-site calling `set_record_hash` with the live PoAC
  `record_hash` stream + surfacing each kill's `binding_mode` on the KAS record (a KAS-commitment change)
  — field-validated at a rig session (pairs with RP-6). Then increment 3: PoSR beacon compose (replay).

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
