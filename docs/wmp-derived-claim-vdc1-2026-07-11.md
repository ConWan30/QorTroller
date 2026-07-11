# WMP Verifiable Derived-Claim Loop (VDC-1) — 2026-07-11

**The rung this is on.** WMP proved the data is *real + consented*; AH-1 proved the verification is
*robust*. VDC makes the certified data yield **verifiable derived value the gamer controls** — a
derived CLAIM about their play that a stranger recomputes and confirms without trusting QorTroller.
Purest "Core Controllers of their Data": the gamer publishes a claim *about* their session; the raw
post-φ matrix is not contained in the claim record.

Sole designer/auditor/builder: Claude (this turn, no external design). Loop shape mirrors AH-1 and
skill-strata: one derivation per cycle → one banked claim + one pinning test; REFERENCE-AND-BIND;
verification is re-derivation.

## The value ladder (honest about which rung v0 is on)

| rung | what it gives | status |
|---|---|---|
| **today** | to trust "trigger engagement was 10%", a buyer obtains the raw matrix AND trusts the seller's math | — |
| **VDC v0 (this)** | the property is a PURE function of the certified bundle, BOUND to its hash, and RE-DERIVED by the verifier (recompute + byte-compare). The seller cannot lie about it; it cannot be swapped onto another session. A party *with* the bundle confirms it independently; a party *without* it sees a claim bound to a certified-human session. | **LIVE** |
| **VDC + ZK (next)** | prove the derivation *without disclosing the matrix* (zero-knowledge) — the "withhold + prove" rung | named, **ceremony-gated**, not a v0 claim |

## What a VDC is

`sdk/wmp_derived.py` — a pure module (I/O in `scripts/build_wmp_derived_claim.py`).

- **Record** (`vapi-wmp-derived-claim-v1`): `derivation_id`, `parent_bundle_hash` (binds to the exact
  certified bundle), `value` (the derived property + `channels_read` + in-band `definition`),
  `ceiling` (shipped verbatim), `claim_hash`.
- **Verify** (`verify_claim(claim, bundle)`, fail-closed): schema · parent-schema · `claim_hash`
  integrity · **parent_binding** (claim ↔ this exact bundle) · **data_floor** (bundle carries no
  forbidden column — reuses the AH-1-hardened `_forbidden_hits`) · `ceiling_verbatim` ·
  `channels_allowed` (derivation read no forbidden channel) · **`value_rederive`** (recompute the
  derivation and byte-compare — the crux; the stored value is never trusted).

## Banked derivations

| id | derivation | value on M17 (real UC-1) | honest at N=1? |
|----|-----------|--------------------------|----------------|
| **TRIGGER_ENGAGEMENT_FRACTION_v1** | fraction of ticks with a trigger pressed (`trigger_L_state>0 OR trigger_R_state>0`) — the Phase 235-GAD `ACTIVE_GAMEPLAY` signal made verifiable | `active_ticks=173 / ticks=1730 = 0.10` | ✅ property of THIS session; grounded in an existing protocol signal, not invented |
| **ACTION_ENTROPY_v1** | per-channel Shannon entropy (integer millibits) over the 5 player-action channels — imu excluded (postural); measures input variety | sticks 3373 / 3300 mb (norm 0.83 / 0.81) · triggers 651 / 536 mb (0.16 / 0.15) · buttons 125 mb (0.05) — a real fingerprint: steering-dominant, sparse triggers/buttons | ✅ property of THIS session's input distribution; never a cross-player comparison |
| **INPUT_TEMPO_v1** | per-channel input-state transition count + rate per 1000 ticks (cadence) — imu excluded; rate-AGNOSTIC (no wall-clock asserted — bundle carries no verified sample rate) | sticks 870 / 936 transitions (503 / 541 per 1000) · triggers 203 / 183 (117 / 106) · buttons 33 (19) · total 2225 | ✅ the cadence of THIS session; integer, deterministic |
| **STICK_ENGAGEMENT_FRACTION_v1** | fraction of ticks with either stick displaced from the deadzone sentinel (NEUTRAL_SECTOR=16; sectors 0..15 are active directions — value 0 is "east", not idle) | `engaged_ticks=1726 / 1730 = 0.9977` — only 4 ticks have both sticks centered (constant steering) | ✅ steering/aim engagement of THIS session |
| **BUTTON_PRESS_COUNT_v1** | button interaction volume — total press events (per-bit 0→1 rising edges across the 16-bit button_mask; a held button is one press) + distinct buttons + active ticks | `press_events=17 · distinct_buttons=5 · active_ticks=23` | ✅ interaction volume of THIS session; integer, deterministic |

Together they form the **input fingerprint** of the session — *engagement* (triggers), *variety* (entropy), *tempo* (cadence), *steering* (stick displacement), *interaction* (button volume) — each independently re-derivable, none a cross-player rank.

**Determinism rail:** derivations using transcendentals (entropy's `log2`) store **integer millibits** (bits×1000), never raw floats — so `value_rederive` byte-compares exactly, no cross-platform ULP hazard (confirmed byte-identical across builds).

Reproduce:
```bash
python scripts/build_wmp_derived_claim.py                               # trigger-engagement, build+verify → exit 0
python scripts/build_wmp_derived_claim.py --derivation ACTION_ENTROPY_v1
pytest bridge/tests/test_wmp_derived_vdc.py -q                          # pinning tests (both derivations)
```

## Tamper rails (test-pinned)

- swap the parent → `parent_binding` FAIL · lie about the value → `claim_hash` FAIL · lie + re-hash →
  `value_rederive` FAIL · taint the bundle with a forbidden key → `data_floor` FAIL (build refuses;
  verify fails) · strip the ceiling → `ceiling_verbatim` FAIL.

## Saturation

**VDC-1 v0 is SATURATED** (2026-07-11) — the meaningful N=1 derivations over the post-φ action matrix
are banked (the 5-dimension input fingerprint). A full pass adds no new honest per-bundle derivation.

**Out of scope for v0 (breadth-gated):** percentile ranks / cross-player comparison (population gate
stands). **Out of scope for v0 (different surface):** authored-kill count (lives in KAS/PoSP, not the
action-only WMP matrix). **Named next directions:** (1) **selective disclosure** — commit to the set
of claims, reveal a chosen subset with a binding proof (desk-buildable, no ceremony); (2) **ZK
property proof** — prove "value ≥ threshold" WITHOUT revealing it (the "withhold + prove" rung;
ceremony-gated).

## Claim ceiling (carry with every mention)

Derived-not-raw · **N=1** (never a population rank) · deterministic+bound, **not yet zero-knowledge**
· action-only (forbidden columns refused) · no buyer implied · TGE frozen.

---

*WMP VDC-1 — opened + SATURATED 2026-07-11 (C1 trigger-engagement, C2 action-entropy, C3 input-tempo, C4 stick-engagement, C5 button-press-count — the 5-dimension input fingerprint). Living doc; one derivation per cycle. Next: selective disclosure (desk) → ZK property proof (ceremony-gated).*
