# Trio-Retina / Trio-Lumen x QorTroller — Perception, Assertion, Meaning

**Design note, 2026-07-07. Advisory scoping — no code, no flag flips, no FROZEN-v1 change.**
Supersedes-in-spirit the generic "perception layer + proof layer" framing (grok draft,
2026-07-07) by grounding it in what QorTroller has already shipped and what V.A.P.I.
is actually for.

## 1. Thesis — the correction that changes the architecture

The generic framing says: "QorTroller should design its outputs so a future world-model
layer can consume them; create a clean integration point."

The reality: **that integration point already exists and is already load-bearing.**

- The trio-retina stack is BUILT in this repo (advisory, default-OFF, through Phase 3):
  embedder / perception / `retina_state_commitment` / `retina_events_root` (Poseidon,
  off-chain ZK-prep) / `retina_pda_attestation`, W3bstream validation (`INV-W3S-006`,
  `INV-RETINA-001/002`), DA bulk + witness sidecar. Wired read-only via
  `session_adjudicator._enrich_retina_evidence`. It does not touch the 228B PoAC wire.
- PoSP's `events_roots` dict carries **two NAMED parallel roots** by design (§2.3 of the
  D-CERT-5 doc): `kas_session_root` (screen kill outcomes + device-clock HID onsets) and
  `retina_perception_root` (the trio-retina perception vocabulary) — structurally
  parallel, never conflated, either honestly None.

So the task is not "design a seam." The seam is shipped. The task is to scope **what
flows across it, in which direction, under which rails** — and to say what is exclusive
to QorTroller when it does.

## 2. The three-plane model, defined through gaming

```
  MEANING     Trio-Lumen direction (future): queryable session intelligence,
              predictive dynamics, plain-language replay queries.
              THE GAMER OWNS THIS PLANE. It is data, priced on the marketplace,
              released only through consent categories.
                          ^  structured scene events (sanitized)
  ASSERTION   QorTroller core (shipped): KAS + PoSP + NQPV fusion + L9/B2 coupling
              + zero-false-read OCR. Narrow, cryptographic, enforceable.
              THE PROTOCOL OWNS THIS PLANE's integrity. It is what a tournament
              operator verifies (scripts/verify_posp_record.py, isFullyEligible()).
                          ^  input-anchored evidence windows
  OBSERVATION Trio-Retina tier (built, advisory): rich, fallible, DEFAULT-OFF
              structuring of the stream — ROI persistence, temporal event clusters,
              game-state buffer. May SUGGEST; may never ASSERT.
```

The one-line law that makes this QorTroller-exclusive rather than generic:

> **Observation may suggest; only assertion may claim; meaning belongs to the gamer.**

Every vision system in gaming does observation. No vision system in gaming has an
assertion plane bound to a certified controller's device clock. And no anti-cheat
anywhere treats the meaning plane as gamer-owned sellable property. The trio is the
category claim of V.A.P.I. restated for video: the physical-input source is the
cryptographic agency-holder over the data those physical interactions generate —
*including the data a world model derives from watching them*.

## 3. What is exclusive (novel claims, each grounded in shipped machinery)

**N1 — Causality-anchored perception.** Every other perception system watches pixels
unconditionally. QorTroller's assertion plane is gated by physical input (the R2∧B2
invariant: B2 alone NEVER opens classification — no live input, no window, no claim).
A trio-retina tier inherits the split cleanly: it may *observe* everything, but its
observations only *become claims* inside input-anchored windows. A world model that can
only assert when a human hand moved is a new object in the vision landscape — and it is
splice-resistant by construction, not by classifier.

**N2 — The assertion boundary is cryptographic, not organizational.** The generic
framing's "dual output model" is our shipped REFERENCE-AND-BIND design: the perception
plane's integrity note travels as a *commitment referenced by PoSP* (`retina_perception_
root`), never inlined into the proof, never a new FROZEN-v1 family until it earns one.
Rich outputs can iterate freely; the proof surface stays frozen. Arc 7's sidecar-pointer
pattern (bulky payload on the DA node, 32B commitment on the wire) is the same law —
scene-stream payloads are DA-class data, pointer-only at the boundary.

**N3 — The witness box is the perception node (the OA-RP-1 convergence).** RP-CLOSE-1
measured that same-machine capture contends with Remote Play's GPU decoder (process
isolation refuted live); the deployable answer is a sidecar DEVICE (D-RP-1, Option A).
That box is not just a capture card: it is the natural physical home of the trio-retina
perception tier — its own silicon, off the gamer's hot path, observer-effect-free by
construction. Registered with ioID, validated through W3bstream, it becomes a **new
DePIN device category: the gaming witness node** — and it is the long-term answer to
the `verifier_independence=False` rail (RP-7), because an independent witness device
with its own identity is exactly what "independent verifier" means physically. This is
maximal IoTeX alignment expressed as hardware: the controller is the trusted thing that
*acts*; the witness node is the trusted thing that *sees*.

**N4 — The sovereignty pipeline already has rails for scene data.** A structured scene
stream is a new data class, and it flows through machinery that exists: φ-class
sanitization (Arc 5's pre-processor with its FORBIDDEN_COLUMNS data floor — non-invertible
by design), consent categories (Arc 4 manifests, gamer-wallet-signed, bridge read-only),
curator packaging (Arc 3), marketplace listing (Phase 238). Nothing about "world model
output" is exempt: if Lumen can answer "how does this player clear corners," that answer
is biometric-adjacent gamer property and moves only through consent. The generic framing
has no privacy story; QorTroller's is already load-bearing.

**N5 — Predictive dynamics as an anti-GCAP oracle (the Lumen-direction payoff).** A
world model that predicts expected-next-frame *given input* turns coupling from
correlation into physics: the recoil-precognition channel already sketches this (a
trigger-synced macro's compensation LEADS the on-screen kick under stream delay — Δ≤0,
impossible for a screen-reactive human at Δ∈[+80,+280]ms). Lumen-style dynamics
generalize it: deviation between predicted and observed causality is a replay/injection
signal that no screen-only and no input-only system can compute, because it requires
holding BOTH lobes — which is QorTroller's defining position.

## 4. IoTeX alignment map — through the gaming lens

| IoTeX primitive | Generic meaning | QorTroller gaming meaning | Status |
|---|---|---|---|
| Internet of Trusted Things | devices produce verifiable data | the certified controller is the trusted thing; gameplay is the real-world data | LIVE (VMDR, PoAC) |
| W3bstream | off-chain compute, verified | mechanical validation sandbox for retina events; `frame_grabbing=false` pinned — perception compute NEVER biometric capture inside the sandbox | BUILT (`INV-W3S-006`) |
| DA / sidecar pointer | bulk off-chain, commitment on-chain | scene-stream payloads live on DA; PoSP/chain sees 32B roots only | PATTERN SHIPPED (Arc 7) |
| Poseidon / ZK-prep | provable computation | `retina_events_root` is already Poseidon — the meaning plane can be *queried with proofs* later without re-architecture | BUILT (Phase 3) |
| ioID | device identity | the witness node's identity; the physical basis of verifier independence | COULD (N3) |
| `isFullyEligible()` | one composable call | tournament gate consumes assertion-plane verdicts, never raw observation | LIVE |
| Data marketplace + consent | data economy | Lumen-derived session intelligence = gamer-owned listings through Arc 3/4 rails | RAILS LIVE, class NEW |

## 5. Scoping — aligns NOW vs COULD align

**Aligns now (no new build):** the named-root seam in PoSP; the retina evidence enrich
path (read-only, default-OFF); the DA witness sidecar; the event-schema discipline
(timestamped, session_id-joined, commitment-referenced) that RP-CLOSE-1 artifacts
already follow.

**Could align, cheap (post-Match-14 candidates):** a structured game-state buffer
(ROI persistence + temporal event clusters) as an *advisory* input to kill-row location
under sparse RP sampling — the honest use is raising *where to look*, never lowering
the K=3 floor or the canon() bar; every recall gain re-passes the zero-false-read gate
and the C1-class adversarial pairing (the B8 lesson: a better reader can dissolve an
accidental defense — engine/tier changes touching a certificate path re-run their gates).

**Could align, structural (Option-A era):** the witness node as perception hardware
(N3); ioID registration of the node; Lumen-direction predictive-coupling studies (N5)
run OFFLINE against archived matches first, exactly like every other oracle earned its
place (synthetic -> archive -> live -> calibrated).

**Does not align (out of scope by design):** general scene understanding as a product;
any perception output feeding `presence_score` without a measured calibration study
(the anti-GCAP weight rail); any scene-stream data leaving the rig unsanitized or
unconsented; any inline payload crossing the PoAC/PoSP boundary.

## 6. Hard rails (unchanged by everything above)

1. 228B PoAC wire untouched; chain hash = SHA-256(164B body). Always.
2. Observation NEVER asserts: no perception-tier output opens a classification window,
   moves `presence_score`, or bypasses ABSTAIN/canon(). R2∧B2 stands.
3. REFERENCE-AND-BIND: perception integrity travels as referenced commitments
   (`retina_perception_root`), no new FROZEN-v1 family without its own ceremony case.
4. Advisory-first: every new tier ships default-OFF behind measured calibration,
   `cert_scope=developer_self`, `population_certified=False` until a population study.
5. Sandbox is mechanical-validation-only (`frame_grabbing=false` / `optical_capture=
   false` pinned) — the W3bstream plane validates events, it never captures them.
6. Scene data is gamer property: φ-class sanitization + consent categories + curator
   rails before anything leaves the rig. The bridge never grants/revokes consent.

## 7. Sequencing — where this sits in RP-CLOSE-1

This note displaces nothing. Match 14 (Option B) runs exactly as runbooked — it needs
no perception tier. The convergence point is **Match 15 / Option A**: the capture-card
witness box acquired for full-density RP capture (OA-RP-1) is the seed hardware of the
trio-retina perception node (N3). One purchase, two roadmaps: the RP recall ceiling now,
the DePIN witness-node category later. Lumen-direction work (N5) begins offline against
the existing match archives whenever a session wants it — zero rig, zero risk, same
verification-first ladder every oracle has climbed.
