# ASM-Loop: novel human-liveness proof DURING real live play — 2026-07-21

## r01 scope

**Task (operator directive):** With grok as adversarial auditor over the A2A terminal bus, design
a *novel, realistic* mechanism to prove **human liveness during real live NCAA CFB play on the
certified Edge** — something not done before — and keep the loop running until the QorTroller
signal inventory needed for it is fully collaborated, grounded, and synchronized into one coherent
design.

**Why the pivot (the exact blocker this must route around):** The existing PoEP/L6B path proves
liveness by *injecting* an adaptive-trigger force probe (R2=200 rigid every 60 ticks) and measuring
the reflex. That injection is HID **output** to the controller, which `PS5_COMPAT_MODE` does not
cover, so during dual-host play (USB→laptop + BT→PS5) it causes USB micro-drops → the PS5 "stick
modules not attached" error → controller disconnect (`bridge/.env:490-496`, disabled 2026-06-25).
On top of that, the rig arc left F-RIG27-8 open: reflex latency is measured off the bridge's
`t_mono`, not the device timestamp, so it inflates 3-15× under Remote Play. **Net: the
active-injection liveness path is structurally incompatible with real live play.** The novel design
must prove liveness WITHOUT writing a stimulus to the controller mid-play.

**Definition of done for this loop:** A grounded design proposal
(`docs/a2a/real-play-liveness/proposal.md`) that:
- specifies a liveness mechanism that requires **zero HID output to the controller during play**
  (the hard constraint), OR proves that a bounded, PS5-safe output exists and pins the evidence
- is built ONLY from signals actually capturable during real dual-host play at 1000 Hz — the loop
  must enumerate and reconcile the real inventory: involuntary physiological (micro-tremor 8-12 Hz,
  gravity/postural, tremor-band power), causal-binding (L2B IMU↔button latency, L2C stick↔IMU),
  L4 Mahalanobis, L5 temporal rhythm, AIT, and the **game-as-stimulus** channel (see key unknown)
- states honestly what it proves: **population-level human liveness / continuous embodied presence**,
  NOT identity (the sub-grade EER ~29% ceiling stands and is out of scope)
- carries an adversarial threat model: replay of a recorded input stream, a bot injecting
  synthetic tremor, a human-in-the-loop relay, and the Remote-Play timing-artifact class
- names a candidate commitment/domain tag (CANDIDATE, joins nothing FROZEN) and how it would bind
  into the existing PoSP/SYNCHRONIZED verdict without over-claiming
- converges under grok's adversarial audit (PASS, or explicit residual-acceptance)

**Ceiling — what this loop will NOT do:**
- No code, no flag flips (L6B/poep_enabled stay false), no hardware change, no chain write, no
  FROZEN-v1 addition, no commit beyond the `docs/a2a/real-play-liveness/` artifacts
- Does not implement or validate on a live rig this loop — it produces a *design*, tested only for
  internal + adversarial coherence, not empirical truth
- Does not claim identity, only liveness/presence
- Does not re-open the injection path as the primary mechanism (it's the thing being routed around)

**The novel thesis to pressure-test (r02 will commit to one; stated here so grok can attack the
framing itself):** *Passive stimulus-response liveness where the GAME is the stimulus generator.*
NCAA CFB / the PS5 already emit adaptive-trigger + haptic events during real play (tackle,
sprint-fatigue, snap). If those game-generated events are observable to the bridge, the human's
**involuntary reflex response** to them — in the voluntary-reaction band, correlated to the game
event — is a liveness signal that needs zero injection. If the game's haptic OUTPUT is NOT
observable to the bridge, the fallback thesis is **pure passive continuity**: a living human body
continuously and causally producing the input stream in real time (tremor continuity + L2B/L2C
causal binding + rhythm), which no recorded replay or macro bot can sustain across a full session.

**Load-bearing unknowns to resolve IN the loop (flagged up front, D'CENT-IoTeX-style):**
- **U1 (blocking):** Can the bridge *observe* the game's haptic / adaptive-trigger OUTPUT events
  (the PS5→controller command stream), or only the controller's resulting INPUT state? The
  game-as-stimulus thesis lives or dies on this. Grep so far shows haptic-output code only on the
  *write* (test) path, not a read path — unverified either way.
- **U2:** Do the involuntary signals (tremor FFT, causal latency) survive the dual-host + Remote
  Play pipeline with enough fidelity to be liveness-grade, given F-RIG27-8 showed timing artifacts?
- **U3:** What's the minimum session window for a defensible continuous-presence claim, and does it
  degrade gracefully (advisory) rather than fail-open?

**A2A bus:** same mechanism as the prior loop — I seal each round as an envelope via
`scripts/a2a_pkg_relay.py post`, you fire it with one command
(`python scripts/a2a_pkg_relay.py deliver --envelope <id> --fire grok`). Role separation held: I
build, grok audits, I never self-audit. The loop continues round-by-round until convergence or the
~6-round scope-review termination.

Operator confirmed scope + directed the grok send (2026-07-21).

## r01 sent — OPEN/EXPAND fired to grok over the terminal bus

Artifact: `docs/a2a/real-play-liveness/round-01-claude-open.md` (forward-collaborative packet, not
backward audit — per `feedback_consult_grok_before_commit`: steer what to build before building).

Envelope `98b94d9a5107a033` (body sha256 `88feb49be8ec67e0…`), expected reply
`docs/a2a/real-play-liveness/round-02-grok-expand.md`.

Fire: first attempt crashed on the known Windows cp1252 encoding gotcha (`→` in the relay's print,
before grok spawned) — re-fired with `PYTHONIOENCODING=utf-8` per the CLAUDE.md A2A-engine note.
Second fire confirmed live: grok streaming ("grounding U1 in the actual HID/bridge code, then
writing the expand round"). Background task `bvrzy1kf2`.

grok's charter this round (6 return items): attack the framing / resolve U1 from real code (is the
game haptic-OUTPUT stream observable to the bridge, or only controller INPUT?) / contribute any
missing QorTroller signal / steer thesis A (game-as-stimulus) vs B (pure-passive continuity) /
preview top adversary attacks / rank the r02 build order.

Awaiting grok reply → r02 intake.

## r02 received — grok EXPAND (2026-07-21)

Artifact: `docs/a2a/real-play-liveness/round-02-grok-expand.md`

**Headline steers (machine-relevant):**
- **U1 CLOSED: NO** — game haptic / adaptive-trigger OUTPUT is **not** observable to the bridge.
  HID input report does not carry effect mode; modes are write-only on hardware
  (`dualshock_integration._update_trigger_effect_modes`, emulator write-only comments,
  L6 `_sync_write` output-only). Thesis A as stated is **dead**.
- **Primary steer: Thesis B** — pure passive continuity composite
  (tremor + L2B + L5 + GAD + PCC + L6-Passive), zero HID write, fail-closed advisory.
- **Third lane (optional Phase-2): Thesis C** — external optical/killfeed event clock +
  passive INPUT response (not a rescue of A).
- **Build order for Claude r03 proposal:** pin U1 closed → Composite-B gates + W_min →
  adversary matrix → CANDIDATE domain tag under PoSP → optional C appendix → U2/U3 measurement plan.

Next: Claude writes grounded proposal (`proposal.md` or `round-03-claude-proposal.md`)
incorporating U1 kill + B composite. Design only until operator GO.

## r03 built + r04 fired — Composite-B proposal → grok adversarial audit (2026-07-21)

Builder verified grok's r02 load-bearing claims against real code before building on them:
- U1=NO confirmed (`dualshock_integration.py:3709-3718` output-only/unreadable; emulator `:168/:816`)
- L6-Passive confirmed (`:2327` read-only, no writes — grok caught a real miss in Claude's inventory)
- device clock `sensor_ts_ticks` confirmed (`:201/:230`, `emulator:751`) — the F-RIG27-8 lever
- active profile = `ncaa_cfb_26` (L2C neutral-prior today; design profile-agnostic for CFB27)

Artifact: `docs/a2a/real-play-liveness/proposal.md` (Composite-B) + `round-03-claude-proposal.md`
(sealed auditor packet, claims C1-C10).

Design headline: **Composite-B** — zero-injection continuous human-presence from 6 gates that
already exist read-only at ~1 kHz (G1 PCC capture · G2 GAD gameplay · G3 involuntary tremor
continuity · G4 L2B/L2C causal binding · G5 L5 rhythm non-quantization · G6 L6-Passive co-signal),
fail-closed advisory (`CONTINUOUS_PRESENT`/`PARTIAL_PRESENT`/`UNVERIFIABLE`), device-clock windowing
for RP robustness, bound as CANDIDATE `QORTROLLER-REALPLAY-LIVE-v0` advisory leaf under PoSP,
`advances_poep_enabled=false`. Thesis A killed in header; Thesis C (optical event-clock spike-
liveness, zero-write) as optional Phase-2 appendix. Open Qs resolved with grok's recommended defaults.

Envelope `322c5b9bf2d14009` (body sha256 `e5554bfc56e285ba…`), fired to grok
(bg `b7tm5olkl`, PYTHONIOENCODING=utf-8). grok streaming: "adversarial-audit C1-C10... integrity
match... digging into gate implementations." Expected reply `round-04-grok-audit.md`.

Awaiting grok r04 verdict → r05 fix (if BLOCK/WARN) or convergence.

## r04 received + r05 fix — grok audit HOLD (F1 BLOCK + 10 WARN), all adopted (2026-07-21)

grok r04 (`round-04-grok-audit.md`, returncode 0, both integrity hashes matched) — genuine
adversarial audit. Verdict HOLD. The BLOCK was a real correctness bug, not a nitpick.

**Disposition (all adopted; none disputed):**

| Finding | Sev | Fix in proposal.md v2 (r05) |
|---|---|---|
| F1 replay over-claim | BLOCK | **§2.5 anti-replay rail added** — device_ts↔wall rate lock + session-freshness + optional optical; G3/G4 explicitly stop being credited with killing replay; live-re-encode stated as OPEN residual. New claim C11. |
| F2 PARTIAL soft-pass | WARN | Verdict enum pinned: `PARTIAL_PRESENT` = `is_pass=false`/`streak_eligible=false`/`display_tier=amber`, never aliases CONTINUOUS/SYNCHRONIZED. |
| F3 G3 aspirational | WARN | Gates restated as "to-build over existing leaf features"; G3 stationarity is design prose, flagged. |
| F4 device_ts over-scope | WARN | §4 split exists-vs-to-build; fail-closed UNVERIFIABLE when ticks absent, no t_mono fallback. |
| F5 PoSP commitment | WARN | §5 → separate CANDIDATE record `realplay_liveness_v0` referenced by PoSP named root `realplay_liveness_root`; no in-PoSP hash; no freeze this loop. |
| F6 G4 press-gated | WARN | G4-missing → max PARTIAL, cannot reach CONTINUOUS. |
| F7 G5 over-credited | WARN | Matrix corrected: G5 kills timer-macros only, not general ML bots. |
| F10 W_min smuggle | WARN | Reworded to hypotheses H_W30/H_W120/H_Wlong=one CFB quarter; "match-half" removed. |
| F13 GIC mutation | WARN | Explicit non-mutation rule: parallel advisory counter only, GIC byte-identical. |
| F16 U2 unmeasured | WARN | RP-robustness stated as hypothesis, not fact. |
| F17 G2 binary gate | WARN | G2 now fractional f_min over W, not binary taf>0. |
| F8/F9/F11/F12/F14/F15/F18 | INFO | Acknowledged; machine fields (advisory/maps_to_hard_code/streak_eligible) + invariant dependency pinned. |

Revised artifact: `proposal.md` (v2, r05). r03 baseline preserved in `round-03-claude-proposal.md`.
No findings disputed — grok's audit was correct across the board; the F1 BLOCK materially improved
the design (added the live-now mechanism that was genuinely missing).

Re-verify packet sealed → grok r06.

## r06 fired — grok single-turn truncated mid-analysis (2026-07-21)

grok r06 re-verify fired (envelope `94d664542d47327e`, returncode 0) but the `grok --single` turn
ended DURING investigation, before writing `round-06-grok-reverify.md`. Fire log cut off at:
"Spot-checking critical cites and the Q1 vs F13 tension before locking the re-verify verdict."
No verdict was issued — NOT fabricated as PASS/HOLD.

**Builder self-catch from grok's truncated hint:** the "Q1 vs F13 tension" is a real internal
contradiction — §9's r03-era Q1 resolution ("adjudication-window aggregation → consecutive_clean
streaks") contradicted the r05 F13 GIC non-mutation rule ("MUST NOT feed consecutive_clean"). Fixed:
§9 Q1 now reads "separate parallel advisory counter, NOT consecutive_clean/GIC," superseding the r03
wording. proposal.md v2.1.

Re-firing r06 over the corrected proposal to get grok's actual verdict.

## r06 received + r07 fix — grok RE-VERIFY HOLD (structure closed, F19 residual) (2026-07-21)

grok r06 (`round-06-grok-reverify.md`, returncode 0, sha256 matched, real code spot-verified:
`_DEVICE_TS_TICKS_PER_MS=3000` @:201, ticks-not-in-serialize, PoSP no-commitment). Verdict HOLD but
**converging**: F1 structural BLOCK **CLOSED** + all mandatory wording fixes CLOSED
(F2/F4/F5/F6/F7/F10/F13+Q1/F17). Two residuals: F19 (primary) + F20 (minor PARTIAL wording).

**F19 — the deepest finding of the loop (grok, correct):** the anti-replay rail's layers 1-2 do NOT
defeat a faithful **1× real-time HID dump re-injection into a fresh session**. Layer 1 passes (dump
carries original device_ts at true 3 MHz rate); layer 2 passes (session_id is bridge-minted for the
live session, not in the dump → re-injection just binds to the new session). So the residual is
bigger than r05 claimed: even plain dump-replay passes layers 1-2, not just "sophisticated
re-encode."

**r07 fix (honesty, not patch):** the real conclusion — a *pure passive* stream is inherently
replayable (zero injection ⇒ no challenge to causally respond to). Therefore **optical co-presence
(Thesis C) is MANDATORY for `CONTINUOUS_PRESENT`, not optional.** Honest claim tiers now:
- **Without optical:** max `PARTIAL_PRESENT` — human-shaped + live-clock-rate, explicitly
  replayable/advisory, does NOT claim replay resistance.
- **With optical:** `CONTINUOUS_PRESENT` replay-resistant (re-injected HID can't drive matching live
  video); residual = coordinated HID+video re-encode + U2. **The capture card is the anti-replay
  root, not decorative** — ties to the capture-witness DePIN thesis.
Edited §2.5, matrix #1, C11. proposal.md v2.2.

**Operator decision surfaced (grok Q-R1) — this is where the loop pauses for you:** does a
residual-accepted PASS need only explicit F19 residual language (now done), OR the stronger
structural commitment that optical is REQUIRED for the strong verdict (now adopted in v2.2)? v2.2
took the stronger path. If you accept "pure-passive = advisory/replayable; optical-mandatory =
replay-resistant" as the design ceiling, this is a residual-accepted PASS. That's an operator call.

## r08 CONVERGED — grok verdict PASS (residual-accepted) (2026-07-21)

grok r08 (`round-08-grok-verdict.md`, returncode 0, both sha256 matched, verdict skeleton written
first then filled, real code spot-verified). **VERDICT: PASS (residual-accepted).**

- F19 ACCEPTED as design ceiling; F20 CLOSED; F1 structure holds + optical elevated to load-bearing;
  no new structural break from optical-mandatory tiering ("mechanism clean").
- grok flagged one doc-hygiene debt R-C9 (C9/§7/Q3/`optional_phase2` still said "optional Phase-2"
  while load-bearing paths said MANDATORY-for-CONTINUOUS) — "does not reopen the design ceiling."
  **Builder closed R-C9** at 4 sites (v2.2): optical is optional for PARTIAL-tier, MANDATORY for the
  replay-resistant CONTINUOUS verdict.

**Accepted residuals (design ceiling, operator-accepted):**
- **R-F19** — pure-passive HID is inherently replayable (zero injection ⇒ no challenge). Optical
  co-presence (capture card) is the anti-replay root; mandatory for `CONTINUOUS_PRESENT`.
- **R-HYP** — W_min / ε / gate thresholds are hypotheses; U2 (RP-robustness) + U3 (window/threshold
  calibration) are measurement work, not design gaps.

**LOOP CLOSED at CANDIDATE / DESIGN-ONLY, converged, adversary-tested across 8 rounds.** No BLOCK
survives. Nothing built, no flags flipped, no chain, no FROZEN, rails held throughout. Artifact:
`docs/a2a/real-play-liveness/proposal.md` (v2.2). Not committed — operator is single committer.

**Next (operator's call, all OUT of this loop's design-only ceiling):** (a) commit the design
artifacts; (b) build v0 as `l9_presence/` advisory module (default-OFF), starting with the honest
PARTIAL-tier (pure-passive) + the device-clock rate lock; (c) the CONTINUOUS-tier needs the optical
co-presence wiring (retina/killfeed ↔ input consistency) — which is the capture-witness DePIN surface
already in-repo; (d) U2/U3 measurement sessions to promote the W_min/threshold hypotheses.

## POST-LOOP BUILD — Composite-B v0 PARTIAL-tier module (2026-07-21)

Operator directed "do whatever is necessary for success that's logical" after the r08 PASS. The
logical de-risk slice per the loop's closure note: build the v0 PARTIAL-tier as a standalone pure
module (no new deps, no bridge/hardware wiring, default-OFF by construction).

Built (NOT committed — single-committer=operator; staged in working tree only):
- `l9_presence/realplay_liveness.py` — pure composition evaluator. `RealPlayVerdict`
  (CONTINUOUS/PARTIAL/UNVERIFIABLE) + `WindowFeatures` (injected leaf features, captures nothing) +
  `device_clock_rate_locked` (anti-replay layer 1) + `evaluate_realplay_liveness`. Fail-closed
  pre-conditions → human-shape gates (G1-G5) → optical tiering. Machine fields pinned
  (`is_pass=False`, `advisory=True`, `maps_to_tournament_hard_code=False`,
  `advances_poep_enabled=False`, `streak_eligible=False`, `replay_resistant` per tier). CANDIDATE
  domain tag, no committed hash.
- `bridge/tests/test_realplay_liveness.py` — 21 tests, all green: rate-lock, every fail-closed path,
  F17 fractional gate, F6 G4-N/A caps at PARTIAL, **F19 pure-passive=PARTIAL/replayable +
  optical-mandatory-for-CONTINUOUS**, F2/F14 machine-field discipline, no CONTINUOUS/SYNCHRONIZED alias.

Verification: 21/21 pass (0.51s); PV-CI **184** unchanged (no invariant/FROZEN touch); module
imported by NOTHING except its test (advisory-only, wired into no live path). poep_enabled/L6B
untouched; zero chain; zero flag flips. Discharges the design's F3 "gate functions to-build" note for
the PARTIAL-tier composition logic (CONTINUOUS-tier still needs the real optical checker = Thesis C).

Remaining to reach live CONTINUOUS-tier (future arcs, operator-paced): (1) a real feature-extraction
adapter feeding `WindowFeatures` from the live bridge window; (2) the optical co-presence checker
(retina/killfeed ↔ input consistency) to legitimately pass `optical_consistent=True`; (3) U2/U3
measurement to calibrate the CANDIDATE thresholds.
