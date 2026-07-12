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
| **F1** | **Tri-plane session manifest** (sidecar, REFERENCE-AND-BIND) | **BANKED** — `l9_presence/tri_plane_manifest.py` + `scripts/build_tri_plane_manifest.py` + 9 tests + real artifact `audits/tri_plane_manifest_match17_2026-07-11.json`. M17 federates: **assertion↔observation CRYPTOGRAPHIC, meaning↔session REFERENCE_ATTESTED** (honest, never overclaimed). Beneficial catch integrated: the **separation law is now machine-checked** (observation/meaning can't carry an asserting field), and `consent_gamer_address` on the meaning plane ties "Core Controllers" across all three planes |
| **F2** | **Tri-plane verifier + "one match, three planes" rung** | **BANKED** — `verify_wmp_ladder.py` RUNG 8 builds + verifies the tri-plane manifest (separation law machine-checked); one zero-trust command now walks the whole federated object: data economy (rung 1) + anti-cheat (rung 7) + **the three-plane federation (rung 8)**. Brief updated |
| **F3** | **Meaning-plane HARD cryptographic join** | **BANKED (mechanism) — `poac_chain_join()` in `l9_presence/tri_plane_manifest.py` + `audits/tri-plane-f3-hard-join-2026-07-11.md` + 7 tests.** F3 grounding **corrected the optimistic F1 claim**: the PoSP's KAS commitment is a SHA-256 over KAS-domain data, **NOT** the Arc-5 Poseidon PoAC-chain root — different domain, cannot byte-match. So the join **requires the PoSP to carry the SAME Arc-5 `poac_chain_root`** the WMP pipeline computes; then the meaning join **EARNS** CRYPTOGRAPHIC via a byte-equal match (rep-robust across int/decimal/0x-hex), and an unearned CRYPTOGRAPHIC claim is **REJECTED**. **Defeats the S4 splice** for any field-bearing session. **M17 stays honestly REFERENCE_ATTESTED** (`poac_chain_join: ABSENT` — its PoSP predates the field), so no fake join ships — the DeferredProver shape. **Activation (gated):** a live PoSP carries `poac_chain_root` at mint (daemon wiring), or M17 is re-derived from `bridge_match17.db` offline (DB-gated) |
| **F4** | **Adversarial: plane-splice** | **BANKED** — `l9_presence/tests/test_tri_plane_splice_ah.py` (6-vector matrix) + `audits/tri-plane-splice-matrix-2026-07-11.md`. Forge-your-own found a **real gap and fixed it**: the new `session_consistency` rail catches an internal join-key splice (top-level `session_id` disagreeing with the assertion/observation planes) **with no artifacts in hand** (S1/S2). Wrong-PoSP (S3), asserting-field-under-rehash (S5), and hash-tamper (S6) all CAUGHT. **S4 (meaning splice) is the honest ceiling** — a bundle from a different session binds `attested=True` and verifies, because the WMP bundle has no `session_id`; the manifest never overclaims it (`REFERENCE_ATTESTED`, machine-checked), and **F3 is what closes it** |

## Honest ceilings

- **Federation, not conflation** — the loop never merges the planes or lets observation/meaning assert.
- **N=1**, developer_self, IoTeX testnet, no buyer, TGE frozen.
- **The WMP↔session hard join mechanism is BUILT (F3); its DATA is gated** — the manifest EARNS a
  cryptographic meaning join the instant a PoSP carries the matching Arc-5 `poac_chain_root`. Until a
  field-bearing PoSP exists (live daemon wiring, or M17 re-derived from `bridge_match17.db`), the
  meaning plane joins by *reference + attestation*, and the manifest says so plainly (never rounds up).
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
