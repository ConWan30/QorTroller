# PoEP P4 — Governed Activation (Scope)

**Status:** SCOPE / design-only. P4 turns PoEP from *calibrated-but-dormant* into a *live,
anchored, gamer-owned credential*, strictly behind QorTroller's established deferred-
activation + governance discipline. No activation happens in this doc.

## Mythos real-time alignment audit (2026-05-22)
- **mythos_operator_initiative_audit = 0 findings** → the Sentry/Guardian/Curator fleet
  (12 Cedar bundles, Q9 hex, Merkle sync, anchor scripts, Architect/VBDIP methodology) is
  fully synchronized. PoEP can **ride this fleet** for anchor/sign/govern without new drift.
- **mythos_frozen_drift = 1 (pre-existing INV-016)** + **mythos_crypto_drift = 1 (pre-existing
  VAPI-O3-SUPERSEDE-v1 tag)** → guardrails: P4 adds no pinned invariant / commitment family
  except via the governance ceremony, and does **not** compound either pre-existing item.

## Activation gates — ALL must hold before PoEP issues a LIVE verdict / anchors
1. **Calibration robustness** — N≥50 met, but the band [231–349 ms] is from **3 players**.
   Gate: **≥5 players** for a defensible population reflex band (the persistent more-players lever).
2. **Device-auth strengthened** — the captured force-response was incidental/weak. Gate: a
   deliberate **adaptive-trigger force-challenge** capture (its own mini de-risk) before
   device-auth is relied on in production.
3. **Two-key activation** — `poep_enabled` AND `L6_CHALLENGES_ENABLED` are per-flag operator
   opt-in (default False), mirroring the O1-D-PATH-B live-write contract (per-flag enable +
   emergency kill-all + `CHAIN_SUBMISSION_PAUSED` as the final gate).
4. **Governance ceremony** — if `QORTROLLER-POEP-v0` graduates from candidate to a registered
   PATTERN-017 commitment family + a pinned PV-CI invariant (so frozen/crypto Mythos recognize
   it), it goes through the VAPI-O3-SUPERSEDE-style ceremony (`--reason invariant_change --confirm-governance`).
5. **Born-PQ credential signing** — hybrid **ECDSA + ML-DSA-65**; the **gamer's own key signs**
   (sovereignty; bridge never signs for them); the **device PQ key** registers in IoTeX's PQ Key
   Registry. Software ML-DSA now; on-chain PQ-verify deferred until IoTeX's PQ precompile ships (IIP-64).
6. **On-chain anchoring** — Sentry anchors the PoEP SHA-256 commitment on AdjudicationRegistry
   (`0x44CF98…`), only after `CHAIN_SUBMISSION_PAUSED` lift + per-agent IOTX budget + wallet (the O3-ceremony pattern).
7. **Consent-bound** — issuance requires gamer **CONSENT v1**; per the hard rule, the bridge
   only reads consent — the gamer's wallet performs any on-chain grant.

## Phases
- **P4a — Robustness:** capture ≥5 players' enrollment (band) + build & de-risk the deliberate
  adaptive-trigger force-challenge (strengthen device-auth). *(Operator data + a small build.)*
- **P4b — Governance:** operator-authorized ceremony to register the PoEP commitment family +
  PV-CI invariant (or keep it a candidate if not anchoring yet).
- **P4c — Born-PQ credential:** hybrid ECDSA+ML-DSA-65 signer (gamer key + device PQ registry);
  software ML-DSA lib now, on-chain precompile verify when IoTeX ships it.
- **P4d — Operator-fleet wiring:** Sentry-anchor / Guardian-HSM-sign / Curator-govern the PoEP
  credential — dry-run seams (like the Witness) → live only via two-key + chain-pause lift + budget.
- **P4e — VHP integration:** PoEP becomes the **liveness gate at VHP issuance/renewal** (the
  natural moment — prove the human is live + on the certified device when the credential is minted).
- **P4f — Kill-switch + audit:** single-flip `poep_enabled=False` emergency hatch + an issuance/
  spending audit log (mirrors the operator-initiative kill-all + chain-spending log).

## Honest constraints / risks
- **3-player band is narrow** → ≥5 players before any live liveness verdict (count met, robustness not).
- **Device-auth weak as captured** → strengthen (force-challenge) before relying on it.
- **ML-DSA on-chain + anchoring blocked** on IoTeX PQ primitives + `CHAIN_SUBMISSION_PAUSED` lift (designed-for).
- **Graduating the commitment = a FROZEN governance event** — deliberate, operator-authorized.
- **Liveness latency band is the FLOOR** (a band-aware forger) — the nonce, device-auth, and the
  deliberate force-challenge are the real anti-forgery layers.

## What stays frozen / untouched
PoAC 228-byte format untouched; `CHAIN_SUBMISSION_PAUSED=true` held; `poep_enabled` /
`L6_CHALLENGES_ENABLED` default False; no pinned invariant or commitment-family registration
except via ceremony; INV-016 + O3-SUPERSEDE remain operator-gated (not compounded). Mythos
(frozen + crypto + operator_initiative) re-run as the gate at each P4 step.
