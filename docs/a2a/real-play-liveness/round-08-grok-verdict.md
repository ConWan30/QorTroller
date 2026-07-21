# A2A round 08 — Grok RESIDUAL-ACCEPTED PASS verdict: Composite-B v2.2

**Role:** grok (adversarial auditor / residual-accepted PASS check)  
**Prior:** `docs/a2a/real-play-liveness/round-07-claude-residual-accept.md`  
**Body integrity of prior:** sha256 `6d81649bb2cd60f3d2380a3f738949a849f6d691cc102d1f4a0a2e80096421ce` — **MATCH** (recomputed on disk)  
**Prior re-verify integrity:** `round-06-grok-reverify.md` sha256 `902488f0c625f64138cddb7668697087fc3c79f7354ea3373a5c7fb4d66d3d85` — **MATCH**  
**Envelope in:** `a4ace75e33a29a50`  
**Posture:** design-only residual-accepted PASS check — no code, no flag flips, no FROZEN edits, no chain, no commit.  
**Rails held:** 228B PoAC · FROZEN-v1 · PV-CI 184 · `CHAIN_SUBMISSION_PAUSED` default · single-committer=operator · zero mid-play HID output.

---

## verdicts

| Item | r06 | r07 disposition | One-line |
|------|-----|-----------------|----------|
| **F19 paced-dump residual** | WARN | **ACCEPTED as design ceiling** | Layers 1–2 honestly do not defeat 1× dump re-injection; optical MANDATORY for `CONTINUOUS_PRESENT` with `replay_resistant=true`. No residual over-claim remains on layers 1–2. |
| **F20 rail-thin vs rail-absent** | WARN (minor) | **CLOSED** | Layer-1 absent → UNVERIFIABLE; layer-1 present + optical absent → max PARTIAL; all layers → CONTINUOUS. Unambiguous. |
| **F1 anti-replay structure** | CLOSED:STRUCTURE | **HOLDS + elevated** | Rail layered; G3/G4 demoted correctly; optical elevated from optional flavor to load-bearing for strong verdict. |
| **F2 / F3 / F4 / F5 / F6 / F7 / F10 / F13 / F17** | CLOSED | **STILL CLOSED** | No regression in r07 wording. |
| **F16 U2 RP robustness** | REMAINS WARN (honest) | **REMAINS (honest residual)** | Still unmeasured hypothesis — correctly labeled. |
| **C11 live-now / optical** | HOLD w/ residual | **CLOSED under residual-accept** | C11 revised r07 matches F19 ceiling; optical load-bearing for CONTINUOUS. |
| **C9 Thesis C optional (stale)** | stood (old) | **SUPERSESSION DEBT (residual)** | C9 + §7 title + Q3 + `optional_phase2` machine flag still say "optional Phase-2" while load-bearing paths say MANDATORY for CONTINUOUS. **Does not reopen design ceiling** — load-bearing verdicts/§2.5/matrix#1/C11 are correct. Must supersede before BUILD. |
| **NEW structural break from optical-mandatory?** | n/a | **NO (mechanism)** | Verdict enum + rail + adversary matrix consistent; only claim-table hygiene lag (C9). |
| **Overall** | HOLD | **PASS (residual-accepted)** | Operator-accepted F19+F20 design ceiling met; residuals listed below. |

**ONE VERDICT: PASS (residual-accepted)**

**Reason:** r07 adopts the honest F19 conclusion as design ceiling rather than chasing pure-passive replay resistance that zero-injection cannot deliver. (1) F19 is stated without over-claim — layers 1–2 only block stored-artifact reuse; dump re-injection remains open without optical. (2) F20 tiering is unambiguous. (3) No mechanism-level structural break: CONTINUOUS requires human-shape + layer-1 + optical; PARTIAL is pure-passive honest max with `replay_resistant=false`; UNVERIFIABLE is fail-closed on missing ticks. (4) With F19+F20 explicitly accepted, residual-accepted PASS is warranted.

**Accepted residuals (must travel with any implementation brief):**

| ID | Residual | Class |
|----|----------|-------|
| **R-F19** | Pure passive HID is inherently replayable; layers 1–2 do not defeat 1× dump re-injection | **Design ceiling** (operator-accepted) |
| **R-OPT** | `CONTINUOUS_PRESENT` / `replay_resistant=true` requires optical co-presence (Thesis C / layer 3); without optical max is PARTIAL | **Design ceiling** (operator-accepted) |
| **R-COORD** | With optical: residual narrows to coordinated HID+video re-encode — measurement-gated (U2), not claimed defeated | **Honest residual** |
| **R-C7** | Human-relay proves *a* live human, not which human | **Accepted ceiling** (prior) |
| **R-F16** | G3/G4 RP-robustness unmeasured | **Honest residual** |
| **R-ML** | Good ML bots OPEN (G5 = timer-quantized macros only) | **Honest residual** (F7) |
| **R-C9** | C9 / §7 title / Q3 / `optional_phase2` still frame Thesis C as optional Phase-2 — **supersede before BUILD** so implementers cannot miss optical-mandatory for CONTINUOUS | **Doc hygiene residual** (not design-mechanism flaw) |
| **R-HYP** | W_min / ε / thresholds remain hypotheses (H_W*, U2/U3) | **Measurement residual** |

---

## build-results

| Surface | Result |
|---------|--------|
| Integrity check r07 body | **PASS** (sha256 match) |
| Integrity check r06 prior | **PASS** (sha256 match) |
| F19 honesty check | **PASS** — no residual over-claim that layers 1–2 defeat dump replay |
| F20 tiering check | **PASS** — three-tier pin unambiguous |
| New structural-break hunt | **PASS** — mechanism clean; R-C9 doc supersession debt listed |
| Composite-B code | **NOT BUILT** (design-only; residual-accepted PASS check is not a build) |
| BUILD-NOW items | **none** (mandate: residual check, not new build) |
| Flag flips (L6B / poep_enabled / CHAIN_SUBMISSION_PAUSED) | **UNTOUCHED** |
| Tests this round | **none required** |
| Artifact | `docs/a2a/real-play-liveness/round-08-grok-verdict.md` (skeleton first, then filled) |
| Stage/commit | auditor does not commit; stage-only allowed for this doc |

---

## open-questions

| # | Question | Owner |
|---|----------|-------|
| Q-R1 | **CLOSED by r07 + this verdict:** residual-accepted PASS = F19 design ceiling + optical-mandatory for CONTINUOUS. | closed |
| Q-R2 | Session-freshness remains evaluation-metadata only (still does not kill dump re-host without optical) — intentional under R-F19? Confirm no silent strengthening to nonce-challenge without operator GO. | operator (explicit accept) |
| Q-R3 | **CLOSED by F20 pin:** layer-1 absent → UNVERIFIABLE; optical absent → PARTIAL. Gate-thin → PARTIAL (separate from rail-absent). | closed |
| Q-R4 | ε for device_ts↔wall rate lock — still measurement-gated (U2). | U2 |
| Q-R5 | First code under `l9_presence/` default-OFF vs bridge operator surface? Prefer `l9_presence`, default-OFF, `advances_poep_enabled=false`. | builder (when BUILD authorized) |
| Q-R6 | F16 U2 desk capture with `sensor_ts_ticks` end-to-end under dual-host RP. | operator hardware |
| Q-R7 | **Before first BUILD:** supersede C9 / §7 / Q3 / machine-readable `optional_phase2` so they cannot be read as "optical optional for CONTINUOUS." Split: continuous co-presence = MANDATORY for CONTINUOUS; event-spike appendix (§7 mechanism) may remain Phase-2 optional. | builder (doc hygiene, R-C9) |
| Q-R8 | Optical layer-3 acceptance criteria: continuous game-state consistency vs §7 event-timed spikes — pin which is sufficient for CONTINUOUS (recommend: continuous co-presence required; spikes optional co-signal). | builder before BUILD |

---

## 0. Integrity + method

1. SHA-256 of `round-07-claude-residual-accept.md` and `round-06-grok-reverify.md` — both **MATCH** envelope/prior pins.
2. Wrote this file's skeleton **first** (mandate), then filled after adversarial pass.
3. Mandate framing honored: residual-accepted PASS check, not residual-free PASS; operator accepts F19+F20 as design ceiling.
4. Four confirmation axes walked (F19 honesty / F20 tiering / new break / residual-accepted eligibility).
5. Design-only rails held: no code, no flags, no FROZEN, no chain, no commit.

---

## 1. Confirmation axes (mandate)

### (1) F19 stated honestly — **YES**

r07 §2.5 + F19 block + adversary matrix #1 + C11 all state without hedging:

- Layers 1–2 do **NOT** defeat faithful 1× real-time HID dump re-injection into a fresh session.
- Layer 1 passes on original device_ts at true rate; layer 2 passes because `session_id` is bridge-minted for the live session (not inside the dump).
- G3/G4 pass on any real recording (physiology *inside* stream).
- Pure passive ⇒ inherently replayable (zero injection ⇒ no challenge).
- Optical is MANDATORY for replay-resistant CONTINUOUS; without optical max PARTIAL with `replay_resistant=false`.

**No residual over-claim** of the kind that caused r06 HOLD.

### (2) F20 tiering unambiguous — **YES**

| Condition | Verdict |
|-----------|---------|
| Layer-1 absent (no device ticks) | `UNVERIFIABLE` |
| Layer-1 present, layer-3 optical absent | max `PARTIAL_PRESENT` (`replay_resistant=false`) |
| All layers present (+ human-shape gates) | `CONTINUOUS_PRESENT` (`replay_resistant=true`) |
| G4 missing | cannot reach CONTINUOUS; max PARTIAL (F6) |

"Rail thin" no longer conflates with rail-absent. Gate-thin → PARTIAL is orthogonal and correct.

### (3) No NEW structural break from optical-mandatory tiering — **YES (mechanism)**

Checked for:

| Risk | Result |
|------|--------|
| CONTINUOUS without optical reachable by wording loophole | **No** — explicit all-three requirement |
| PARTIAL over-claiming replay resistance | **No** — `replay_resistant=false` pinned |
| UNVERIFIABLE vs PARTIAL collapse | **No** — F20 three-tier |
| GIC / consecutive_clean mutation reopened | **No** — F13 parallel advisory only |
| PoSP commitment mint / FROZEN freeze | **No** — C8 separate CANDIDATE record |
| Tournament hard-code mapping | **No** — `is_pass=false`, advisory leaf |
| Zero-injection violated by optical | **No** — optical is non-HID (capture card), not HID write |
| Thesis A reopened | **No** — U1 CLOSED:NO stands |

**Doc hygiene only (R-C9):** C9 still says "Thesis C is optional Phase-2"; §7 titled "optional Phase-2, non-blocking"; Q3 "non-blocking appendix"; machine block `optional_phase2 = C_external_event_timed`. Load-bearing surfaces (verdict table, §2.5, matrix #1, C11) correctly elevate optical for CONTINUOUS. This is **supersession debt**, not a mechanism hole — listed as residual; **must fix before BUILD**.

### (4) Residual-accepted PASS? — **YES**

Operator mandate accepts pure-passive = advisory/replayable and optical-required = replay-resistant. Under that acceptance class, surviving residuals are **listed**, not automatic HOLD. No remaining BLOCK or unaccepted over-claim.

---

## 2. What this PASS does and does not authorize

**Authorizes (design-complete under residual-accept):**

- Composite-B v2.2 as the **canonical design brief** for a future BUILD phase.
- Three-verdict machine enum + optical-mandatory CONTINUOUS + PARTIAL pure-passive ceiling.
- Separate `realplay_liveness_v0` CANDIDATE record + PoSP named-root reference (no freeze this loop).

**Does NOT authorize:**

- Code land, flag flips (`L6B_ENABLED` / `poep_enabled` / campaign), chain writes, FROZEN-v1 domain-tag freeze.
- Treating PARTIAL as tournament-green or aliasing CONTINUOUS to PoSP SYNCHRONIZED.
- Claiming layers 1–2 alone are replay-resistant.
- Skipping R-C9 supersession before first implementation PR.
- Shipping CONTINUOUS without a real optical co-presence check (that would re-open F19 as a **defect**, not residual).

---

## 3. Recommended next step (operator-paced)

1. **Doc hygiene PR (optional, pre-BUILD):** supersede C9/§7/Q3/`optional_phase2` per Q-R7/Q-R8.
2. **BUILD authorization** (separate operator GO): `l9_presence/` default-OFF advisory leaf; tests first; no GIC mutation; no HID mid-play write.
3. **U2/U3 measurement** before any threshold promotion or freeze ceremony.

---

## 4. Rails attestation

| Rail | Status |
|------|--------|
| 228B PoAC wire | untouched |
| FROZEN-v1 formulas / domain tags | untouched (CANDIDATE only) |
| PV-CI 184 | not run (docs-only round; no gate surface change) |
| `CHAIN_SUBMISSION_PAUSED` | default held; no chain |
| single-committer=operator | auditor did not commit |
| L6B / poep_enabled | false posture held |
| Zero mid-play HID output | design invariant held |

---

**End of round-08 grok residual-accepted PASS verdict.**
