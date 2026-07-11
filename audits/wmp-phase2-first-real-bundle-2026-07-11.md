# WMP Phase-2 — The First Real Provenance Bundle (UC-1 LIVE) — 2026-07-11

**The claim this artifact earns:** one real Warzone match (M17, `match17_rp_fixb3_1783550435`) is
packaged as a human action-demonstration bundle such that a stranger — with one script and zero trust
in QorTroller — cryptographically confirms: **a real human played it** (Groth16), **the human consented
on-chain with their own wallet** (live view-call), and **the data is exactly what the proof was about**
(Poseidon matrix↔root). Recency is honestly deferred (see limits).

## The ceremony (operator-fired, all gates green)

| Step | Result |
|---|---|
| INC-0 kill-check | Matrix regeneration DETERMINISTIC: 463 checkpoints → 27,672 frames → 1,730 ticks; recomputed Poseidon root == the real proof's `public[1]` digit-for-digit; PoAC root `978cb10e…` exact |
| WMP-4 deploy | `VAPIWorldModelConsentRegistry` **`0x06836Fb87B64A05D81ebec9C9e234c01c2DEc5C4`** · tx `0x5456e576…eaafa8f1` · block 45534708 · gasUsed 127229 · post-deploy asserts clean |
| Gamer consent | `setWorldModelConsent(true)` signed by the GAMER wallet `0x0Cf36dB5…` · tx `0x8f70bca3…658a22` · block 45534743 · readback `true` (developer_self: operator IS the gamer — `VAPI_ALLOW_BRIDGE_WALLET_AS_GAMER=1` stated loudly, per the Arc 4 precedent rail) |
| Cost | **0.247443 IOTX measured** (`eth_getBalance` 29.118262 → 28.870819) — within the 0.15–0.45 estimate |
| First real export | `wmp_export.py --real` — the consent gate performed the LIVE `isWorldModelConsentGranted` view-call (no mock); 1 bundle → `wmp_corpus_real/wmp_corpus.jsonl` (+ PII-free manifest) |
| Full verify | `wmp_full_verify.py --allow-deferred recency` → **`VERIFIED — 5/5, zero stubs` · exit 0** |

## What each check proved (per-check, no rounding up)

| Check | Grade | Detail |
|---|---|---|
| Scope honesty | PASS | FROZEN values verbatim (`ACTION_ONLY`, observation `ABSENT_BY_DESIGN_DATA_FLOOR`, `is_full_pomdp_tuple=false`) |
| Matrix↔root | **PASS, cryptographic (POSEIDON_BN254, unstubbed)** | Recomputed over the bundle's own matrix hex == the root the proof verified against. Closes the long-open Arc 5 off-circuit-root finding on REAL data. Tamper drill: one flipped matrix byte → REJECTED |
| Humanity | **PASS, cryptographic (snarkjs, unstubbed)** | proof.json reconstructed FROM the bundle's 256-byte ABI wire; public.json from the bundle's own inputs (FROZEN INV-VHR-005 order); `snarkJS: OK!` — the same proof accepted on-chain at block 45479067 |
| Consent | **PASS, on-chain (unstubbed)** | Live `isWorldModelConsentGranted(gamer)` == true — the gamer's own `msg.sender` signature is the only thing that can flip it; the bridge structurally cannot |
| Recency | **DEFERRED, explicitly allowed** | Only one beacon (45026880) is anchored near M17's window — no honest open/close pair exists; the bundle carries the empty-registry deferral, never a fabricated pair. **Next-match upgrade:** keeper-anchor a fresh pair around a new session → true 5/5 including recency |

Bundle extras: `extra_metadata.skill_strata_band = AUTHORED_HIGH_DENSITY` (the UC-2→UC-1 hook: the
session's demonstration band rode through the `DataFloorViolationError` guard — labels only).

## Claim ceilings (carry with every mention)

- Action channel only — the observation channel (what the human saw) is absent by design; `is_full_pomdp_tuple=false`
- Macro-intent post-φ (60Hz, 4-bit) — NOT biomechanics; the anti-cheat's micro-signal moat never exports
- `developer_self` scope — operator and gamer are the same person, stated on-chain-adjacent and here
- N=1 corpus (one bundle, one session) — a demonstration of the lane, not a dataset business
- **No buyer implied** — this promote was an explicit positioning choice (blueprint's own rule); demand remains thesis
- Recency deferred on this bundle (above) — never claim beacon-bound recency for it
- TGE frozen — nothing here is purchasable; no token exists

## Reproduce / re-verify (anyone)

```bash
python scripts/wmp_full_verify.py --bundle wmp_corpus_real/wmp_corpus.jsonl --allow-deferred recency
# exit 0 = VERIFIED (scope + Poseidon rehash + snarkjs Groth16 + live consent view-call)
```

Build-side determinism: `scripts/wmp_regen_matrix.py --expect-public audits/vhr_proof2_m17/public_m17_real.json`
(exit 0 = the matrix regenerates byte-identically from `bridge_match17.db`).

*WMP Phase-2 first-real-bundle report — 2026-07-11. Plan: `.claude/plans/build-the-top-2-abundant-muffin.md`;
code commit `12cbbe5c`; blueprint `docs/world-model-provenance.md` §7 now executed 5/5 legs.*
