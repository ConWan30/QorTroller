# Trio Readiness Loop (TRL-1) — Retina · Lumen · IoTeX

**An orchestrated, operator-paced build loop** that drives the trio-retina (OBSERVATION) and
trio-lumen (MEANING) stack up the verification ladder to **card-readiness**, with every increment
mapped to its IoTeX primitive. Grounded in `docs/trio-retina-lumen-qortroller-alignment-2026-07-07.md`.

> **The ladder (§7 of the alignment doc):** synthetic → **archive** → *live* → *calibrated*.
> The capture card unlocks the **live + calibrated** rungs. **This loop owns the ARCHIVE rung +
> the readiness that makes the card productive on day one.** Card arrival is the loop's *transition
> event*, not its end — archive-proven oracles hand off to a separate rig-gated live loop.

**Run it:** `/loop run the next open TRL-1 cycle from docs/trio-readiness-loop-trl1-2026-07-11.md`
(one increment per cycle; operator commits; stop at card-arrival or saturation).

---

## 1. The law (never crossed)

> **Observation may suggest; only assertion may claim; meaning belongs to the gamer.** (§2)

Hard rails carried into every cycle (§6 of the alignment doc):
1. **228B PoAC wire untouched**; chain hash = SHA-256(164B body). Always.
2. **Observation NEVER asserts** — no perception output opens a classification window, moves
   `presence_score`, or bypasses ABSTAIN/canon(). R2∧B2 stands.
3. **REFERENCE-AND-BIND** — perception integrity travels as referenced commitments
   (`retina_perception_root`), no new FROZEN-v1 family without its own ceremony case.
4. **Advisory-first** — every increment ships default-OFF, `cert_scope=developer_self`,
   `population_certified=False` until a population study.
5. **Sandbox is mechanical-validation-only** — `frame_grabbing=false` / `optical_capture=false` pinned.
6. **Scene data is gamer property** — φ-sanitization + consent categories + curator rails before
   anything leaves the rig; the bridge never grants/revokes consent.
7. **Certificate-path re-gating** — any increment touching the OCR→authorship→certificate path
   **re-runs the zero-false-read gate + the C1 adversarial pairing** (the B8 lesson: a better reader
   can dissolve an accidental defense). PV-CI 182 unbroken every cycle.

## 2. The three planes × IoTeX (the interconnection map)

| plane | QorTroller (shipped) | IoTeX primitive | this loop's job |
|---|---|---|---|
| **OBSERVATION** (trio-retina) | embedder/perception, `retina_state_commitment`, `retina_events_root` (Poseidon), advisory default-OFF | **W3bstream** (mechanical event validation, `frame_grabbing=false`) · **DA/sidecar** (scene payloads off-chain, 32B root on-wire — Arc 7 law) | ready capture for the card; prove perception advisories offline; keep them pointer-only at the boundary |
| **ASSERTION** (QorTroller core) | KAS + PoSP + NQPV fusion + zero-false-read OCR; `verify_posp_record.py`; `isFullyEligible()` | **Poseidon/ZK-prep** (`events_roots`: `kas_session_root` + `retina_perception_root`, named-parallel) · **`isFullyEligible()`** (verdicts only, never raw observation) | harden the assertion verifier (forge-our-own); extend the plug-and-play verifier to cover it |
| **MEANING** (trio-lumen) | *future*: queryable session intelligence, predictive dynamics | **ioID** (witness-node identity) · **marketplace + consent** (Arc 3/4 — lumen intelligence = gamer-owned listings) | begin N5 predictive-coupling **offline against archives**; design the witness node (ioID seed) |

The category claim, restated for video: *the physical-input source is the cryptographic agency-holder
over the data those interactions generate — including the data a world model derives from watching them.*

## 3. Cycle shape

```text
while not card_arrived and not saturated:
  1. Pick the next OPEN increment from §4 (readiness R > archive-rung A > interconnect I)
  2. Build OFFLINE — against the M11–M17 match archives or synthetic; NEVER live capture
  3. If it touches the certificate path → re-pass zero-false-read + C1 adversarial (rail 7)
  4. Enforce advisory-first (rail 4): default-OFF flag, no presence_score, no window-open, no K=3 change
  5. Name its IoTeX primitive (§2) in the banked artifact — the interconnection is explicit, not implied
  6. Verify: pytest slice green + PV-CI 182 + no FROZEN/228B/PoAC/Solidity/chain contact
  7. Bank: doc row (status → BANKED) + pinning test; STAGE for operator commit
```
**Honest-negative is a result.** An oracle that lands a measured negative offline (e.g. N5 with no
cross-lobe stimulus until the card) banks the harness + the baseline and moves on — the card re-runs it.

## 4. Backlog (ordered; one per cycle)

### Readiness (R) — necessary before the card, desk-buildable now
| id | increment | IoTeX | status |
|----|-----------|-------|--------|
| **R1** | Card-arrival **UVC smoke harness + runbook** — enumerate devices the daemon's exact way (CAP_DSHOW→fallback, MJPG, prove-a-frame), GO/NO-GO on the target index; honest NO-DEVICE with no card | — (capture) | **BANKED** — `scripts/retina_card_smoke.py` + `docs/retina-card-arrival-runbook-2026-07-11.md` (9 tests; ASCII-clean) |
| **R2** | **OCR crop-recalibration harness** — validate crops + pixel-rects at 1080p + one-glance overlay to check content-framing on a card frame | — (capture) | **BANKED** — `scripts/retina_crop_recalibrate.py` (10 tests). **Refined finding:** crops are FRACTIONAL (`RETINA_KILLFEED_ROI`/`RETINA_CAPTURE_PANEL_ROI`) → resolution-independent; the WGC→card shift is content-framing, not resolution (corrected R1's runbook) |
| **R3** | **Witness-node (N3) design note** — the card as "one purchase, two roadmaps" (RP recall now, DePIN witness-node seed later) + ioID-registration readiness | **ioID** | OPEN |

### Archive-rung (A) — enhance/additive, offline against M11–M17
| id | increment | IoTeX | gate | status |
|----|-----------|-------|------|--------|
| **A1** | **LUMEN N5 increment 2 — lag DIRECTIONALITY** (the recoil-precognition Δ≤0 signature generalized; orthogonal to inc1 coherence). `l9_presence/predictive_coupling.py` `assess_directionality` — genuine causal lag → DIR_CAUSAL, replay/precognition → DIR_NONCAUSAL. Full cross-lobe form card-gated (RP-4) | **Poseidon/ZK-prep** | advisory | **BANKED** — pre-registered bar (2026-07-11); metric proven-to-SEPARATE on synthetic (9 tests + demo); genuine baseline on archive, decoupled/replay class card-gated; inc1 untouched (8 tests still green) |
| **A2** | **Retina game-state buffer** (ROI persistence + temporal event clusters) as an ADVISORY OCR-recall aid — raises *where to look*, never lowers K=3 or opens a window | **W3bstream** | **re-run zero-false-read + C1** | OPEN |
| **A3** | **Assertion-plane adversarial hardening** — extend AH-1's forge-our-own discipline to `verify_posp_record` / `retina_events_root` / `kas_session_root` | **Poseidon** | advisory | OPEN |

### Interconnect (I) — the IoTeX through-line, desk-buildable
| id | increment | IoTeX | status |
|----|-----------|-------|--------|
| **I1** | Extend the **plug-and-play verifier** (`scripts/verify_wmp_ladder.py`) with an ASSERTION rung — an outsider verifies the anti-cheat proof *and* the data economy in one command | **Poseidon** + `isFullyEligible()` | **BANKED** — RUNG 7 verifies the M17 PoSP (SYNCHRONIZED) offline via `verify_posp_record.py`; same session as the WMP bundle → "one match, two engines"; brief updated |
| **I2** | **DA sidecar-pointer conformance** for scene payloads — Arc 7's law (bulk on DA, 32B commitment on the wire) applied to scene-stream; a check that nothing inline crosses the boundary | **DA/sidecar** | OPEN |
| **I3** | **W3bstream retina-event applet parity** — confirm the mechanical-validation sandbox validates events and never captures them (`frame_grabbing=false` pinned) | **W3bstream** | OPEN |

## 5. Card-transition (saturation → handoff)

The archive rung **saturates** when: the readiness pack (R1–R3) is shipped, the N5 baseline (A1) is
banked, and the advisory recall aid (A2) is proven offline with its gates re-passed. At that point the
loop **hands off** to a separate rig-gated **live loop** (the card's `live → calibrated` rungs):
plug the card → UVC source → R1 smoke GO → R2 recalibrate crops → A1 re-run with controlled stimulus →
promote advisories from `developer_self` toward a population study. **The card is the transition event.**

## 6. What this loop deliberately does NOT do

General scene understanding as a product · any perception output feeding `presence_score` without a
calibration study (the anti-GCAP weight rail) · any scene data leaving the rig unsanitized/unconsented ·
any inline payload crossing the PoAC/PoSP boundary · any live-capture-dependent build before the card
(it would re-tune the moment the card changes the feed).

---

*TRL-1 orchestrator — opened 2026-07-11. Operator-paced; one increment per cycle; operator commits.
Backlog order: readiness → archive-rung → interconnect. Saturates at card-arrival, then hands off live.*
