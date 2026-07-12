# Tri-Plane Fusion Loop (TPF-1) — one match, three planes, one IoTeX-anchored object

**An orchestrated novelty loop** to make QorTroller's three planes — OBSERVATION (trio-retina),
ASSERTION (KAS/PoSP core), MEANING (trio-lumen / WMP data economy) — **operate as one federated,
verifiable session object on IoTeX**, WITHOUT ever conflating them. Grounded in
`docs/trio-retina-lumen-qortroller-alignment-2026-07-07.md` and the just-closed TRL-1 loop.

> **The law (never crossed): federation, NOT conflation.** *Observation may suggest; only assertion
> may claim; meaning belongs to the gamer.* The fusion binds the three planes under one `session_id`;
> it never lets one plane assert in another's lane. Each plane stays independently verifiable.

## F0 finding (grounded on real M17, 2026-07-11) — the loop's target

| plane | artifact | IoTeX organ | joined by `session_id`? |
|---|---|---|---|
| **ASSERTION** | PoSP record (`kas_session_root`) | Poseidon · `isFullyEligible()` | ✅ carries `session_id` |
| **OBSERVATION** | PoSP `retina_perception_root` | W3bstream · DA sidecar | ✅ same `session_id` (in the PoSP) |
| **MEANING** | WMP bundle (VDC / SD) | ioID · marketplace · consent | ❌ **ORPHAN — no `session_id` field** |

**The novelty made concrete:** assertion + observation are already federated inside the PoSP record.
The MEANING plane is disconnected — the WMP bundle binds to its own matrix (`parent_bundle_hash`) but
carries nothing that proves it is the *same session* as the presence proof. **Closing that orphan is
the fusion.** Today a buyer can verify "certified-human data" and a tournament can verify "synchronized
presence," but no one can prove they came from one match. That is the gap this loop exists to close.

## Cycle shape

```text
while not saturated and not operator_interrupt:
  1. Pick the next F-cycle (below)
  2. Build OFFLINE against the real M17 artifacts (PoSP record + WMP bundle + VDC claims)
  3. FEDERATE, never conflate: bind by reference under the shared session_id; no plane asserts
     in another's lane; each plane's own root/proof stays intact + independently verifiable
  4. Respect every artifact's immutability: the published WMP bundle re-hashes if mutated, so a
     HARD join to it is a schema-v2 operator decision (F3) - the soft manifest (F1) never mutates it
  5. Verify (pytest + PV-CI 182) + bank + STAGE for operator commit
```

## Backlog

| id | cycle | what it does | gate |
|----|-------|--------------|------|
| **F1** | **Tri-plane session manifest** (sidecar, REFERENCE-AND-BIND) | one object citing the PoSP (by `session_id`), the WMP bundle (by `bundle_hash`), and the VDC claims — federating the three planes **without mutating any artifact**. Honest about the WMP↔session soft-join (reference + attestation now; hard join is F3) | desk-buildable |
| **F2** | **Tri-plane verifier + "one match, three planes" rung** | machine-checks the separation law (no plane asserts out of lane) + the joins that ARE cryptographic; adds a rung to `verify_wmp_ladder.py` | desk-buildable |
| **F3** | **WMP-bundle `session_id` hard-join (schema-v2)** | the meaning plane's HARD cryptographic join — add `session_id` to a v2 bundle so it provably ties to the PoSP. **Re-hashes the published bundle → breaks VDC/SD/AH-1 bindings → OPERATOR DECISION** (like the U1 KAS-`to_dict`-only precedent, but the WMP hash covers the whole dict) | **HOLD for operator GO** |
| **F4** | **Adversarial: plane-splice** | forge a cross-plane inconsistency (assertion from session A, meaning from session B) → the verifier must REJECT; the forge-your-own discipline (AH-1 / A3) applied to the fusion | desk-buildable |

## Honest ceilings

- **Federation, not conflation** — the loop never merges the planes or lets observation/meaning assert.
- **N=1**, developer_self, IoTeX testnet, no buyer, TGE frozen.
- **The WMP↔session hard join is F3-gated** — until then the meaning plane joins by *reference +
  attestation*, not cryptographic proof; the manifest says so plainly (never rounds up).
- Advisory planes stay advisory; no PoAC / 228B / FROZEN-v1 / chain-write contact; PV-CI 182 every cycle.

## Why this is the real "operate itself altogether"

Each plane already speaks to its own IoTeX organ (W3bstream / Poseidon+`isFullyEligible` / ioID+DA+
consent). TRL-1's I1/I2/I3 proved each interconnect *separately*. TPF-1 makes a single session a
**cross-plane object** an outsider walks end-to-end — one match that is provably, simultaneously, a
presence proof, a rich-observation commitment, and a certified-human data bundle, each in its lane.
That federated object, anchored across three IoTeX primitives under one join key, is the thing no
screen-only, input-only, or data-only system can produce — QorTroller's defining position, made whole.

---

*TPF-1 orchestrator — opened 2026-07-11. Operator-paced; F0 grounded (meaning plane is the orphan);
F1 next (non-breaking sidecar manifest); F3 is the operator-decision hard-join. Federation, never conflation.*
