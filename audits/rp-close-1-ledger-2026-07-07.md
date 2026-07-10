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

## Offline continuation 6 (2026-07-09): PORT-CERT + ADVERSARY-EXPAND (two novelty arcs)

**PORT-CERT — portable, independently re-verifiable Match Certificate** (`docs/port-cert-design-2026-07-09.md`).
Composes a session's proofs (PoSP + KAS/deferred + VHR ZK proof + on-chain anchor + consent) into ONE
bundle (`qortroller-match-certificate-v0`, reference-and-bind — no new primitive) whose cryptographic
claims a THIRD PARTY re-verifies against PUBLIC parameters, without the rig or raw data. `l9_presence/
port_cert.py` (pure builder + verifier; snarkjs + chain RPC are INJECTED callables — the module never
shells/reads); off-rig checks: session-join (anti-splice) · PoSP SYNCHRONIZED · **anchor-digest match**
(published PoSP file SHA-256 == the on-chain-anchored digest) · VHR Groth16 (C5) · on-chain anchor (C6).
**Honest overall:** VERIFIED needs C5+C6 (a forger can fabricate an anchor ref — only reading the chain
disproves it); missing snarkjs/RPC → PARTIAL, never a false VERIFIED. **Demonstrated on REAL M17**
(`audits/match_certificate_m17.json`, 2068 B, no raw data): all offline checks green incl. anchor-digest
== `545f9d44…` anchored at block 45447322; ZK/chain UNCHECKED this shell → honest PARTIAL. `test_port_cert.py`
14/14. **Scope:** cross-trust-boundary RE-verifiability of the PROOFS, NOT capture trust
(verifier_independence=False inherited). `scripts/match_certificate.py` build/verify.

**ADVERSARY-EXPAND — presence-forgery attack → rail matrix** (`l9_presence/adversarial/presence_forgery.py`).
Turns "we assert fail-closed" into "we DEMONSTRATE it": **11 forgeries across 5 verifiers, all REJECTED
by a named rail** (`audits/presence_forgery_matrix.json`, `holds=True`) — posp forged-SYNCHRONIZED→S6;
deferred replayed-crop→sha-poison + session-splice→anti-assertion; bcc coherence-gaming→G4, hygiene-bypass→G6,
partial-posp→G2, session-mismatch→G6; cert digest-tamper→C4, zk-false→C5, session-splice→C2; event-splice→
record_hash crypto-join. A single un-rejected attack fails the suite loudly. `test_presence_forgery.py` 5/5;
`scripts/run_forgery_matrix.py`.

- **Verify:** l9 **655 passed** (2 pre-existing cocapture env failures); PV-CI **182 PASS**; 0 IOTX; no
  228B PoAC contact / FROZEN-v1 / domain tag / chain write. Staged for operator commit.

## Offline continuation 7 (2026-07-09): EVENT-BIND increment 3 — PoSR recency compose (replay resistance)

EVENT-BIND alone closes cross-source SPLICE; a faithful full-session REPLAY reproduces self-consistent
OLD anchors, so the crypto join still passes. Increment 3 composes the binding with the Arc 6 PoSR
temporal beacon (the on-chain block hash the PoSP A3-b field already carries): `l9_presence/
event_bind_recency.py` — `replay_resistance(bind_report, temporal_beacon, reference_block)` →
**REPLAY_RESISTANT** (crypto ∧ FRESH) / **SPLICE_PROOF_ONLY** (crypto ∧ stale/no-beacon — the naive
replay, downgraded honestly) / TEMPORAL_ONLY / UNVERIFIABLE (with a future-block anti-forgery rail).
Reference block INJECTED (no RPC); default bar 256 blocks (4× ANCHOR_CADENCE ≈ 11 min).

- **Demonstrated** (`scripts/event_bind_recency_demo.py`): two FULLY splice-proof sessions separated by
  beacon freshness ALONE — the live one REPLAY_RESISTANT, the replayed one (stale beacon, 60k blocks
  behind) SPLICE_PROOF_ONLY. Recency catches the replay the crypto join cannot.
- **Forgery matrix extended to 12 attacks / 6 verifiers** (`audits/presence_forgery_matrix.json`,
  `holds=True`): the new `stale_replay` attack → `event_bind_recency` rail (crypto-bound but stale →
  not REPLAY_RESISTANT).
- **Honest limits:** closes the naive/stale replay; NOT a compromised host re-stamping a fresh beacon
  (witness independence); per-record beacon binding impossible (228B PoAC body FROZEN) → recency is
  session-scoped.
- **Verify:** `test_event_bind_recency.py` 12/12 + `test_presence_forgery.py` 5/5; l9 **667 passed**
  (2 pre-existing cocapture env failures); PV-CI **182 PASS**; 0 IOTX; no 228B PoAC contact / FROZEN-v1
  / domain tag / chain write. Staged for operator commit. EVENT-BIND offline arc (inc 1/2/3) COMPLETE;
  only inc 2b (daemon live wiring) is rig-gated.

## On-chain continuation (2026-07-09): VHR-PROOF-2 SUBMITTED ON-CHAIN (the capstone)

The M17 real Groth16 replay proof — verified locally at VHR-PROOF-2 — is now **witnessed on IoTeX**.
`scripts/submit_vhr_proof.py` called `VAPIReplayProofVerifier` v1 `0x5182372d…` `verify(a,b,c,
publicInputs[6])`, which re-ran the pairing check on-chain and emitted `ReplayProofVerified`.

- **tx** `0db5fafff622d8510786f38e03d950f1fbe5f27a52173a1a50b520c5801445f9` · **status 1** · block
  **45479067** · gasUsed 283,279 · cost **0.2833 IOTX** (29.401541 → 29.118262).
- **De-risked before spend:** a `verifyView` eth_call (0 IOTX) confirmed the chain ACCEPTS the exact
  calldata FIRST; snarkjs→Solidity calldata done in pure Python (no snarkjs dep). Triple-gated
  (CHAIN_SUBMISSION_PAUSED=false process-scoped + VHR_SUBMIT_AUTHORIZED=true + --confirm), 1.0 IOTX
  hard cap, estimate_gas×1.25. `bridge/.env` kill-switch stays `=true` (process-scoped override only).
- **Zero-knowledge preserved:** only the 6 public inputs crossed the wire (replayProofToken
  `0xe675e6ae…`, humanityThreshold 700); the sanitized matrix never left the rig.
- Manifest `audits/vhr_proof2_m17/vhr_onchain_submission.json`. **This closes the VHR arc's on-chain
  leg** — the PORT-CERT stack is now publicly checkable end-to-end (a third party confirms the ZK
  claim against this on-chain event). Decision #1 from the chain/IOTX board: DONE.

## Rig prep (2026-07-09): EVENT-BIND increment 2b — daemon stamping wired (Session 1, awaiting rig)

The offline half of inc 2b: the retina capture now threads the live PoAC record_hash into BOTH lobes so
a post-session bind reports RECORD_HASH_PRODUCTION. All flag-gated `EVENT_BIND_STAMP_ENABLED` (default
OFF -> byte-identical; the flag propagates shell -> daemon -> bridge child via `env = dict(os.environ)`).

- **INPUT lobe:** `dualshock_integration` consumption loop (where `_record_hash_hex` is already computed)
  → one guarded `self._retina_game_capture.set_record_hash(_record_hash_hex)`.
- **RetinaGameCapture.set_record_hash():** stores `_current_record_hash`; when stamping on, forwards to
  `_hid_onset.set_record_hash()` so the next r2_onset carries it.
- **OUTCOME lobe:** `_log_composite` stamps `_current_record_hash` into the authored composite
  (`session_screen_events` already forwards `composite.record_hash`).
- **Validation readout:** `scripts/event_bind_session_check.py` reads the session's composite + hid JSONL,
  runs `bind_session_events`, reports crypto vs temporal. Touches NO KAS record/commitment (read-only).
- **Verify:** both bridge files compile; event_bind 35/35; PV-CI **182 PASS**; flag-off byte-identical.
  Runbook handed to operator; live validation is the Session-1 rig run (success bar: crypto-bound > 0).
  0 IOTX, no 228B PoAC / FROZEN-v1 / chain contact. Remaining inc 2b: KAS `binding_mode` surfacing
  (deferred — would touch the KAS record; kept out of the commitment for now).

## AI-loop cycle 1 (2026-07-09): collaboration locked · Session-1/M18 · P0-A first OP

**Claude↔grok engineering loop LOCKED** (`docs/qortroller-ai-loop-collab-2026-07-09.md`): grok
designs/assesses → Claude audits→builds→verifies→stages → operator commits/rig/arbitrates. Neither
AI commits; rig/gameplay always notified; mutual audit both directions; this ledger is the single
append-only canonical memory. grok accepted all 5 open questions (design→build split with Claude as
integrator on capture-adjacent seams; template enforcement; disagreement→human→ledger; population-first;
one canonical ledger).

**Session 1 — EVENT-BIND inc 2b live (Match 18):** stamping wiring **VALIDATED live** (record_hash on
both HID-onset + composite lobes). Authorship blocked by an OCR handle-anchor misread (`QorTrola30` →
`q0rtr01a30`) → `KAS INSUFFICIENT_KILLS` live. Archive re-scan with the correct handle **recovered the
kills** (61/600 crops matched `Qortrola30` @conf 95.5, 8 clusters ≥ K=3, 31 verifier checks OK) but the
deferred tier returned **DEFERRED_OBSERVED_ONLY (8 observed, 0 authored)** — the kill spans didn't
intersect the 5 R2 windows. **Finding: authorship window-conjunction failure implicates RP-4
(uncalibrated cross-lobe latency) — RP-4 is now load-bearing for authorship, not just LUMEN-3.** No
authored pairs → EVENT-BIND crypto-join still unvalidated (needs a clean re-run: fixed anchor + RP-4).
Artifacts: `audits/kas_deferred_record_match18_eventbind_1783639659_2026-07-09.json`.

**P0-A presence-separation study (loop cycle-1 deliverable):** grok designed
(`docs/p0a-presence-separation-study-design.md`), Claude audited (CODE-TRUTH clean; corpus 59/32/10
verified; one self-correction: hw_nqpv is JSON not L9 .npz) + built the harness
(`l9_presence/presence_separation_study.py` + runner + `test_presence_separation_study.py` 13/13,
T1–T10). **First OP = INCONCLUSIVE** (`audits/p0a-presence-op-2026-07-09.{json,md}`): auto collapsed
(median 0.069, M4✓, causality M6✓), but human median **0.195** < TAU_HUMAN 0.20 and gap **0.126** <
GAP_MIN 0.15 on the raw 44-scored pool. **Pre-registration did its job** — refused to launder the
banked Stream-A 0.29–0.45 (a reliability-filtered subset) into a fresh OP. **Tail characterization**
(`audits/p0a-tail-characterization-2026-07-09.md`): the sub-0.20 half is **low-aim, not coupling
failure** (median stick-std 12.6 vs 46.0; 17/22 below the high group's aim p25; r(coupling,aim)=0.50;
P1 low-aim confound) → a pre-registered **aim-activity reliability gate** on positives is justified →
`p0a-presence-op-v2` (grok's §5.1 call + operator §9; do NOT retune the frozen decision constants).

- PV-CI **182**; l9 suite **679 passed** (+13 study; 2 pre-existing cocapture env failures); 0 IOTX;
  no 228B PoAC / FROZEN-v1 / chain contact; harness is offline (zero capture-path, pinned by T9).

## AI-loop cycle 2 (2026-07-09): P0-A v2 aim-active gate → first honest SEPARATED OP

grok amended the design to v2 (aim-activity inclusion gate) after Claude's tail characterization; Claude
audited (threshold principled, not outcome-tuned) + built the gate + re-ran.

**P0-A v2 = SEPARATED** (`audits/p0a-presence-op-v2-2026-07-09.{json,md}`, schema `p0a-presence-op-v2`):
aim-active positives only (gate `max(std(sx-med),std(sy-med)) >= AIM_ACTIVITY_MIN = 4×MIN_STICK_STD×255
= 10.2 LSB` — a fixed multiple of the oracle abstain gate, **pre-registered on principle, rejecting the
outcome-tuned p25/median options**). 26 low-aim positives excluded → **33 human / 99 auto**; median
human **0.374** (≥0.20), auto **0.067** (≤0.10), gap **0.307** (≥0.15), causality clean, ratio 5.6 —
**all M1–M6 pass under the frozen decision constants.** The first human-vs-modeled-automation presence
OP to clear the pre-registered floors.

**Two findings grok's mandated player histogram (D-P0A-10) surfaced — absorbed into the v2.1 doc rev
(SEPARATED unchanged):** (a) **CODE-TRUTH correction** — `sessions_l9` is a **3-player developer
corpus** (P1≈32, P2≈8, P3≈12, +7 untagged), NOT the single-operator N=1 the v1 design assumed (stronger
scope; still not population-certified). (b) **F-P0A-V2-1 heterogeneity** — even aim-active, **P1 median
coupling ≈0.09** vs P2 0.59 / P3 0.38; the pooled SEPARATED is **P2/P3-carried**, P1 a systematic
low-coupling outlier (cause TBD — not re-labeled as bot). The harness now emits
**`players_below_tau_human`** (`['P1']`) so a pooled SEPARATED can never hide a non-separating player.
No min-per-player-n veto in v2 (would move goalposts post-SEPARATED); a uniform-across-players claim is
optional v3 (operator GO). v1 raw-pool **INCONCLUSIVE** stays the permanent honest record.

- `test_presence_separation_study.py` **18/18** (v1 + v2 gate + player-skew + heterogeneity); l9 684
  passed (2 pre-existing cocapture env failures); PV-CI **182**; 0 IOTX; harness offline (zero
  capture-path, T9). grok v2.1 design rev + Claude harness aligned.

## AI-loop cycle 3 (2026-07-10): lane 1 — P1 anomaly diagnostic (F-P0A-V2-1 classified)

grok designed the diagnostic (`docs/p1-anomaly-diagnostic-design-2026-07-10.md`); Claude audited
(grok's designer kill-check **recomputed EXACT** against the real `.npz` — grounded, not confabulated)
+ built + ran (`l9_presence/p1_anomaly_diagnostic.py` + runner + `test_p1_anomaly_diagnostic.py` 9/9).

**Result (`audits/p1-anomaly-diagnostic-2026-07-10.{json,md}`, schema `p1-anomaly-diagnostic-v0`):
PRIMARY = MARGINAL_AIM, secondary HIGH_RESIDUAL, `p0a_v2_separated_unchanged: True`.** The honest
read — **P1 is a low-aim player, not a bad coupler:** P1 med aim **14.8** vs peers ~50, so its low
coupling (0.09) is mostly *insufficient aim energy* (T-H1), with high residual (T-H2) secondary; NOT a
lag regime (T-H3: |217−183|=34 < 100ms) or protocol skew (T-H5). P1 is a labeled human — low coupling
≠ automation (pinned by test T4: never emits SEPARATED).

**Two CODE-TRUTH findings (audit gate; grok design tolerated, now noted):** (a) **no
`backend`/`region`/`protocol` field exists** — `capture_governor` is a bare ndarray, `hud_json`
non-uniform; T-H5 runs only on `label`/`duration_bin` (both uniform → didn't fire), reported as
`protocol_fields_available`. (b) **T-H4 GENUINE_LOW_COUPLING is UNTESTABLE** — P1's aim band [11.8,17.7]
has **0 peer sessions** (P1 aim doesn't overlap peers), so genuine-vs-style is honest `None`, not
forced. **v3 implication:** a uniform-across-players claim isn't cleanly establishable on this corpus
(P1 needs real-aim sessions, or the gate would have to exclude P1's marginal-aim = outcome-tuning).

- `test_p1_anomaly_diagnostic.py` **9/9**; l9 study+diagnostic 27/27; PV-CI **182**; 0 IOTX; offline
  (zero capture-path). P0-A v2 SEPARATED untouched. Loop lane 2 (P0-B wedge thesis) is grok's next.

### Loop lane 2 — P0-B cloud/RP narrow-wedge THESIS (2026-07-10, grok design · Claude claim-audit · no code)

Design `docs/p0b-cloud-rp-wedge-thesis-2026-07-10.md` — a **strategy/thesis artifact**, not a deploy
runbook. The wedge: **"advisory presence attestation for cloud/RP — oracle-viable on aim-active play,
not a Ricochet replacement."** It cites the honest stack (P0-A v2 SEPARATED · P1=MARGINAL_AIM · the
PoSP/KAS/PORT-CERT/VHR/EVENT-BIND/forgery-matrix composition) at the cloud/RP kernel-AC attestation gap.

**Claude claim-audit: PASS — limits ⊆ claims.** Every *internal* number recomputed real against the
committed artifacts (SEPARATED median 0.374 / auto 0.067 / **gap 0.307** / schema `p0a-presence-op-v2`;
P1 MARGINAL_AIM; VHR block 45479067; stack modules). grok kept all 5 limits I specified and added 3
(**8 total in §5**: modeled-automation · developer_self/not-population · aim-active-only · pooled-not-
uniform · advisory · host-not-trustless · testnet-context-for-chain · no-new-FROZEN); the §5.2 copy
block keeps every limit inline; §5.1 has an OK/Not-OK guardrail table. No over-claim in any external
sentence.

**Two "verify before external use" flags — added to the doc as §5.3 so they travel with it (not
blockers):** (a) the *competitive* claims (§2 "GeForce NOW concedes a client attestation gap" /
"Ricochet input-pattern detection") are cited from a prior internal anchor and were **not re-verified
against vendor docs this session** — the only non-repo-verifiable claims in the thesis; confirm before
any organizer quote. (b) **EVENT-BIND is mechanism-proven (splice demo + tests), not live-validated on
real authored kills** (M18 blocked on handle anchor / RP-4); §3.3's "can be splice-bound" hedge is
correct — must not drift to "validated live."

- **No code** (thesis-only, grok's design). PV-CI **182** unchanged; 0 IOTX; offline. D-P0B-5 one-pager
  = **held** (operator-optional; and premature until the two §5.3 competitive claims are source-verified).
  Next in sequence: operator's call — **RP-4 (rig)** or DePIN/consent prose, or pause.

### Loop offline lane 3 — DePIN / consent LEGITIMACY thesis (2026-07-10, grok design · Claude claim-audit · no code)

Design `docs/depin-consent-legitimacy-lane-2026-07-10.md` — the adoption/legitimacy axis P0-B §7 handed
off. Claim: **the gamer holds the consent keys** (grant/revoke = gamer's own `msg.sender`; categories gate
downstream use; FSCA surfaces revoked-but-flowing); that sovereignty is the **opt-in incentive + the
legitimacy contrast vs invasive kernel AC** — explicitly **not** a token/TGE/live-reward economy, not
population-certified, not a claim the bridge can move consent.

**Claude claim-audit: PASS — claim ⊆ reality, zero over-claims.** Every "LIVE (testnet)" row confirmed
against `deployed-addresses.json` with exact status keys: `VAPIConsentRegistry 0xA82dB0eF…`
(`_phase237_status: deployed`, gamer-`msg.sender`/bridge-read-only per `_phase237_note`) · `VAPIDataMarketplace
0x15D2Ac6d…` · `…Listings 0x78Df84Cc…` · `VAPIBuyerRegistry 0x3742189e…` (`_status: LIVE (testnet)`).
The two FSCA rules confirmed in `fleet_signal_coherence_agent.py` (`CONSENT_REVOKED_BUT_DATA_FLOWING` l.489
HIGH + `CONSENT_REVOKED_LISTING_ACTIVE` l.755 CRITICAL/GDPR-Art.17). **No TGE language anywhere** (§5.1/§5.6
rigorous). Sovereignty (§5.2) + consent≠omniscient (§5.3) rails match the CLAUDE.md hard rule + Track-1
privacy lesson.

**The one drift grok flagged for me — `VAPIConsentManifestRegistry 0x5F7c8068…` — is now RESOLVED.**
Address is present (l.154) but carries **no status key** (unlike its neighbors) and the older
`data-economy-deploy-hold-and-arc5-readiness.md` marked it DEFERRED. grok handled it honestly (never quoted
it live; locked it as D-DEPIN-3). **Operator asked for the definitive check: `eth_getCode` on IoTeX 4690
(read-only, 0 IOTX) returns 3869 bytes → DEPLOYED** (control `VAPIConsentRegistry` = 2247 bytes confirms the
RPC + the empty-vs-bytecode distinction). So it **IS LIVE (testnet)**; the DEFERRED prose is stale/superseded
(mirrors the in-file `_reconciliation_2026_05_24` eth_getCode precedent). Doc §4.3 + D-DEPIN-3 upgraded to
LIVE. Follow-up (unbundled): the stale `deploy-hold` doc could get a one-line supersession note. **Audit
self-note:** I initially doubted grok's `_phase237_status: deployed` citation (first grep missed it); re-verified
— **grok was right**, key exists at l.99. Correcting before over-correcting is the audit discipline working.

- **No code** (thesis-only). PV-CI **182** unchanged; 0 IOTX; offline. Optional instruments D-DEPIN-OPT-1
  (consent-flow reporter) + OPT-2 (flywheel metrics stub) **held** (operator-gated, unbundled). Loop pause
  after commit remains: **RP-4 (rig)** or stop — no offline code-buildable surface without new captures.

### RP-4 rig session (2026-07-10) — baseline BLOCKED + latency HONEST-NEGATIVE + live-authorship FIX

**RP arm captured (`rp4_rp`, 25-kill RP match):** 1,480 R2 onsets + 600 crops + PoSP SYNCHRONIZED, but live
**authored=0** (INSUFFICIENT_KILLS) — the SAME failure as M18 (handle read `Qortrola30M`, anchor reached
CANDIDATE then never promoted). **RP-4 baseline BLOCKED:** the rig's "USB Type-C Digital AV Adapter" is
HDMI-**out**, not an HDMI capture card (`eth_getCode`-style device enumeration: only a 720p webcam + the output
adapter; no capture-in) — this IS the parked OA-RP-1 hardware gap. So a live direct-HDMI low-latency baseline is
**not capturable on this rig**.

**RP-4 latency delta = HONEST NEGATIVE** (`scripts/rp4_latency_recovery.py` + `audits/rp4-latency-recovery-2026-07-10.json`):
offline-recovered R2-onset→kill latencies (same method both sessions, onsets
window-filtered from the global log). M13 (direct-HDMI candidate) median **4.68s** vs rp4_rp (RP) median **3.31s**
— delta **−1.37s** (RP *lower* than the "baseline"), and the sign **flips to +0.46s at a 3s cap**. The ~80–300ms
RP-stream signal is buried under **seconds** of in-game trigger→kill + nearest-preceding-onset-mismatch variance
(std 2.3–3.1s) — exactly Phase C C-1.3 §6.1's UNCALIBRATED limit, now proven on fresh data. **RP-4 needs BOTH a
capture card (OA-RP-1) AND a controlled stimulus** (gunfight kills can't isolate transport). M13 is NOT a clean
offline baseline. LUMEN-3 inc-2 (gated on RP-4) stays gated.

**Live-authorship dense-candidate FIX (Option 3) — BUILT (AI-loop: grok design · Claude audit+build · operator
commit):** the recurring live-0-authored (M18 + rp4_rp) root-caused — promotion (K=3 template re-match ≥0.66) is
driven only by sparse R2-onset classify windows under loop starvation, so the candidate froze in CANDIDATE while
the offline scan found the kills. Fix (`docs/live-authorship-dense-candidate-fix-2026-07-10.md`): a dedicated
off-loop worker (`qt-dense-cand`, flag `RETINA_CANDIDATE_DENSE_SCORE`, **default-OFF**) scores the dense panel
stash against the CANDIDATE template so K-progress **and** feed_v1-raw-auth stall-recut reach even when windows
are sparse — **no OCR** on the dense path, off the event loop, K=3/0.66/FP/stall gate **UNCHANGED**. Claude audit
caught 3 code-truth corrections (C1 lock = `_inline_admission_lock`; C2 hook is the event-loop `tune()` → use a
dedicated worker, not `save_capture_crops`; C3 dense-private fresh-row) + a build refinement (`_anchor_mutation_ctx`
nullcontext-safe lock so the fold's fail-open except can't silently no-promote on partial fixtures).
`bridge/vapi_bridge/qortroller_retina_capture.py` (+134/−2) + `bridge/tests/test_dense_candidate_score.py` (9 tests).
PV-CI **182**; 75-test retina regression green; 4 broad-slice fails **proven pre-existing** (stash-verified at HEAD);
0 IOTX; no FROZEN/chain/PoAC contact. **Live validation pending** — next RP match with `RETINA_CANDIDATE_DENSE_SCORE=1`
(grok §11): expect `candidate_progress`/`promoted` (or stall-recut) + `authored_kills > 0`.

### Dense-candidate LIVE VALIDATION + Arc A deferred window-pad = FIRST verifiable RP authored session (2026-07-10)

**Dense-candidate fix live-validated (`densecand_validate`, 32-kill RP match, flag ON):** the log proves the
mechanism — `session-anchor[dense]: candidate_progress consistent=2` + `candidate_stall` fired (rp4_rp froze
with ZERO such events). But live `authored=0` again: severe **13fps lag** (41 loop-starvation events, up to
5.16s blocks) → anchor took **~9.5 min to bootstrap** → cut a weak candidate → recut right at match end, never
promoted. **The blocker moved from promotion-logic (fixed) to the capture lag** (pre-existing bridge starvation).
`inline_authored=8` in the diag — 8 kills WERE recognized, just not counted (R1 coverage gap: pre-promotion
kills don't fold).

**Arc A — deferred window-latency pad (grok design · Claude audit+build · operator commit) — DELIVERS the
verifiable authored result the live path couldn't.** Offline card-free path: under RP a kill row appears ~1-4s
after the R2 fire, but the classify-window is narrow, so `kas_deferred._classify_cluster` finds no overlap →
`DEFERRED_OBSERVED`. Fix: `window_latency_pad_ms` (default 0 = byte-identical) extends each window's END forward
by a bounded pad; **first-appearance predicate** `w0 ≤ span[0] ≤ w1+pad` (forward-only — a kill first appearing
before fire never attributes). **G-VERIFY (Claude audit elevation):** the pad is persisted on the record AND
`verify_deferred_record` **independently re-derives** each AUTHORED cluster from stored `span_ms` + `window_hit_ms`
+ the pad — so padded authorship is genuinely re-verifiable (T8: strip the pad → verify FAILS).

**Offline validation (all on saved archives, no replay):**
| Case | pad | Verdict | authored | |
|---|---|---|---|---|
| **densecand_validate** | **4000** | **DEFERRED_AUTHORED_SESSION** | **1→3** | **verify OK, 3/3 conjunctions re-derive** |
| densecand_validate | 0 | DEFERRED_OBSERVED_ONLY | 1 | byte-identical baseline |
| M14 (regression) | 4000 | DEFERRED_AUTHORED_SESSION | 3→3 | no over-attribution |
| M18 | 4000 | DEFERRED_OBSERVED_ONLY | 0 | honest — M18 lag >4s, beyond budget |

`densecand_validate` **flipped OBSERVED_ONLY→AUTHORED_SESSION** — the **first verifiable card-free RP authored
session** off a saved archive. Honest ceiling: 4000ms recovers 3 of 8 (the >4s tail needs a deferred FAR study,
not a looser pad — grok limit #3). Files: `l9_presence/kas_deferred.py` (+`_window_hit`/pad/G-VERIFY) +
`scripts/build_deferred_attestation.py` (`--window-latency-pad-ms`) + `test_kas_deferred.py` (22 = 14 byte-
identical + 8 pad/G-VERIFY) + `docs/deferred-window-latency-pad-fix-2026-07-10.md`. Result record:
`audits/kas_deferred_record_densecand_validate_pad4000.json`. PV-CI **182**; 37-test regression green; 0 IOTX;
no FROZEN/chain/PoAC. Pad is a transport-aware **operator choice**, not a frozen constant; default 0.

### Arc B — LUMEN-2b live match-state WIRED into capture (2026-07-10, grok design · Claude audit+build · operator commit)

**The operator's "seamlessly see when a match starts/ends" ask.** `LiveMatchStateTracker` (`l9_presence/match_state_live.py`)
was built stream-safe but NEVER hooked into the live daemon. Arc B wires it: `RETINA_MATCH_STATE_ENABLED` (**default-OFF,
byte-identical when off**) constructs the tracker beside the other advisory monitors; fed the signals the loop already
computes — `push_onset` from `mark_r2_onset`, `push_window` + AUTHORED-only `push_kill_span` from `_log_composite`;
`tick()` once per consumption cycle (after `flush_stale_inline_window`, dualshock L1803); `close_session()` at `RGC.stop`
flushes the final MATCH_ENDED (manifest seal > the 240s exit-gap). Emits `MATCH_STARTED`/`MATCH_ENDED` →
`retina_match_state.jsonl` + `log.info` (visible in the daemon log while playing) + 6 RGC-diag fields.

**Advisory never-gates (rail 1, load-bearing):** match-state ANNOTATES only — no authorship/PoSP/KAS/dense-candidate/
certificate branch reads it; the cryptographic session boundary REMAINS daemon start/stop (the tracker's own invariant).
Asserted by test (`test_never_gates_emit_only`): the wiring reads the composite but never mutates its authorship keys,
and `tick_match_state` returns nothing a verdict path can consume. Claude audit found **NO corrections** — grok grounded
every hook line against the current file, correctly tracking the dense-candidate line shifts (mark_r2_onset L935, RGC.stop
L1619, dualshock flush L1803).

`bridge/vapi_bridge/qortroller_retina_capture.py` (construct/feed/tick/close/diag + `_match_state_enabled`) +
`bridge/vapi_bridge/dualshock_integration.py` (tick call) + `bridge/tests/test_match_state_wiring.py` (9 tests: flag-off
no-op, live==offline parity, kill-anchor→STARTED, close_session flush, tick dedup, AUTHORED-only kill feed, onset feed,
fail-open, never-gates). PV-CI **182**; 96-test targeted + 244-test broad regression green (4 broad fails **stash-verified
pre-existing**, arc B zero-regression); 0 IOTX; no FROZEN/chain/PoAC. **B2 (noted, not built):** per-match deferred
auto-segmentation via `kas_deferred.slice_scan_by_spans`. **Live "see it while playing" validation** = next session with
`RETINA_MATCH_STATE_ENABLED=1` (MATCH_STARTED in the daemon log after real play + diag flips LOBBY↔IN_MATCH).

### Bridge capture-lag fix — D1 attribution SHIPPED (2026-07-10, grok design · Claude audit+build · operator commit)

**The lag is the last wall for LIVE `authored>0`** — the dense-candidate mechanism works, but at 13fps the anchor
bootstraps too late to promote in-match. Root (memory `[[project_retina_phase0_live_starvation_finding]]`): agent-fleet
inline DB + 5.4GB DB starve the event loop; retina is the victim. grok's design is **diagnostic-first, no big-bang** —
build **D1 (attribution) ONLY**, capture with it on to NAME the real top offenders, THEN F2 (surgical to_thread offload)
/ F1 (reversible capture-priority deferral), DB prune as a separate follow-on.

**D1 (this commit) — pure diagnostic, zero fleet/data/loop risk:** `loop_timing.timed_block` now appends each exit
`{label, dur_s, tid, wall_ns}` to a bounded 256-entry ring (`LOOP_STARVATION_ATTRIBUTION_ENABLED`, **default-OFF → one
bool check per exit, byte-identical**); on a LOOP STARVATION event `run_loop_health_monitor` dumps the **top-5
timed_block sites by dur in the window + the lean-mode posture** (D2) — so the operator NAMES the loop-blocking sync
sources instead of guessing. Un-instrumented blockers are flagged as a finding (need a new timed_block site). Claude
audit found **NO corrections** — `timed_block` verified already wrapping the cited SLOW sites (calibration_monitor /
curator / protocol_intelligence / stewards / chain_reconciler); `records` already indexed (so F2 is an offload, not an
index-add). Optional RGC-fps-on-line deferred to D1.1 (monitor gets only `cfg`).

`bridge/vapi_bridge/loop_timing.py` (ring + `top_blocks`/`recent_blocks`/`attribution_enabled`) +
`bridge/vapi_bridge/loop_health_monitor.py` (starvation dump) + `bridge/tests/test_loop_starvation_attribution.py`
(7 tests: off no-append byte-identical, on records, top_blocks names offender, since-window filter, off-warning-still-
fires, ring bounded, toggle). PV-CI **182**; 34-test loop-timing/stability regression green; 0 IOTX; no FROZEN/chain/PoAC.
**Next (rig-gated):** one capture with `LOOP_STARVATION_ATTRIBUTION_ENABLED=1` (+ `PRESENCE_LEAN_MODE=true`) names the
top 2-3 offenders → then F2/F1 (grok loop). Design `docs/bridge-capture-lag-fix-2026-07-10.md`.

## `lag_attr_validate` — 2026-07-10 — THREE LIVE VALIDATIONS IN ONE MATCH (RP Warzone, monitor 0, all 3 flags ON)

One RP match with `LOOP_STARVATION_ATTRIBUTION_ENABLED=1 RETINA_MATCH_STATE_ENABLED=1 RETINA_CANDIDATE_DENSE_SCORE=1`.

- **🎯 DENSE FIX LIVE-VALIDATED — `authored=14`, the FIRST live Remote-Play authored session** (M18/rp4_rp/densecand
  all returned live 0). The **dense worker promoted the anchor off-loop** — `session-anchor[dense]: promoted
  regime=PROMOTED sha=311a58ea consistent=3` → `inline_composite_authored=14`; the old sparse-R2-window path got only
  `inline_authored=5`. `AUTHORED_SESSION` commit `69da4fe6`; **PoSP SYNCHRONIZED** (kas_verified=True, fusion_rows=432,
  archive_verified=True, 600 crops → `retina_kf_archive/lag_attr_validate_1783721691`). Promoted because the initial
  cut was **clean** (`Qortrola30`) vs densecand's noisy `Qortrola30M`. **Landed despite the lag** (below) — the dense
  worker is off-loop, so live authorship is now robust to the starvation. RP-2c authorship gap CLOSED. Task #43 CLOSED.
- **Arc B (LUMEN-2b) MATCH_STARTED LIVE-VALIDATED:** `match-state: MATCH_STARTED` fired ~15s after match start,
  `match_state: IN_MATCH` held the whole match, `n_started=1` — the "seamlessly see when a match starts" ask, proven
  live. **F-ARCB-1 (OPEN):** MATCH_ENDED did NOT emit at stop (`close_session` wired at
  `qortroller_retina_capture.py:1712` but `n_ended=0`, no ENDED line in `retina_match_state.jsonl`) — the close-emit
  provisional-span iteration found nothing to close; the "and ends" half needs a fix (→ grok, arc-B close increment).
- **D1 lag attribution — the named offender class:** 18 loop-starvation events (worst **4.69 s** loop block), every one
  attributed `NO timed_block entries in window (lean_mode=True) → the blocker is UN-INSTRUMENTED (SQLite/RPC on the loop
  thread)`. Under lean mode the agent fleet is skipped, so **no instrumented site is the offender** — it is
  un-instrumented sync on the loop thread. fps min 12.9 / med 17.0 / max 25.8; governor maxed (downscale=8,
  region_scale=0.5). → **D1.1 (next, → grok): instrument the suspect un-instrumented loop-thread sync** (retina/dualshock
  DB writes, records inserts, chain RPC view calls, session-loop SQLite) with `timed_block` → re-capture NAMES the site
  → **F2** offloads it. Reframe: authored=14 landed *despite* this lag, so F2 is now density/precision + bridge-health,
  not the authorship blocker. Task #45 updated.

## F-ARCB-1 + D1.1 BUILD — grok design → Claude audit+build (2026-07-10) — staged for operator commit

Both from the `lag_attr_validate` findings. Hard audit gate (claim ⊆ reality vs live code) run before each build.

**F-ARCB-1 — force MATCH_ENDED on session close** (`l9_presence/match_state_live.py`). Live stop left `n_ended=0`
while `match_state=IN_MATCH`: `close_session` only emitted for IN_MATCH spans `detect_match_state` re-found at close,
and it returned nothing. AUDIT correction: grok's stated "clock mismatch" root cause is **not** it — the live
MATCH_STARTED ts (1783721835082) is a wall-clock ms, the *same* clock `close_session(time.time()*1000)` uses. Why
detect returned nothing is unpinned, but the fix is deliberately **detect- and clock-independent**: after path (A),
if `_open_match_start_ms` is still set (STARTED reliably sets it), force ONE `(MATCH_ENDED, "session_close")`
timestamped at last activity / detected at stop. Single-shot; advisory; never gates. 3 new tests (spy detect→empty
reproduces the live failure + single-shot dedup + detect-path-no-double); 10 pure-core + 9 wiring green.

**D1.1 — instrument the lean-residual loop-thread sync** (`loop_timing.py` + `loop_health_monitor.py` +
`dualshock_integration.py`). AUDIT confirmed the premise: `_session_loop` is `async` on the event-loop thread, and
**lean mode runs ONLY `loop_health_monitor` + that session loop** (main.py L1252-59), so the residual loop blocker is
definitively inside it; the frontend-polled endpoints already `to_thread` every store read (ruled out). CORRECTION:
grok's `warn_s=0.005` would spam WARNINGs on 5.4GB-DB calls when attribution is OFF (breaks byte-identical-off) — used
`warn_s=999` (never-warn; the ring records every exit when attribution is ON regardless of `warn_s`). Wraps 7 inline
loop-thread sync sites via a `_timed_loop_store` helper (get_detection_policy, cognitive read/write, frame_checkpoint,
pitl_proof, retina flush_stale + tick_match_state) + a **loop-tid filter** (monitor records the loop thread's tid; the
dump drops worker-tid blocks so qt-dense-cand/classify/HID can't mask the real offender). Default-OFF byte-identical.
3 new tests (loop-tid get/set, worker-tid excluded, recent_blocks filter); 10 attribution tests green.

**Verify:** PV-CI **182**; compile-OK ×4 modules; 29 targeted (arc-B + attribution) green; the 5 stability_9
stage4/5/7 failures proven PRE-EXISTING (stash-verified: 1 fails identically at HEAD — ChainReconciler spec-interval
order-pollution in the untouched `operator_steward_absorbed_agents.py`; other 4 pass in isolation). Zero regression.
0 IOTX; no FROZEN/chain/228B-PoAC contact. **Next:** operator commits (D-ARCB-4 / D-D11-4) → one lean capture with
`LOOP_STARVATION_ATTRIBUTION_ENABLED=1` NAMES the offender → grok designs F2 (`to_thread` that one site).

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
