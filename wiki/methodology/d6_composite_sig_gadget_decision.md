# D6 — Composite-sig In-Circuit Verification Gadget (decision-only)

**Status:** DECISION (Sequence C — decision-only, no prototype evidence; native SP1 infeasible on
Windows, WSL prototype deferred). Fired /goal-style (V-check + this reasoning as the audit trail; no
mid-way hold; operator reviews retrospectively and may override the threat-model axis — it's a doc
decision, refinable when the WSL prototype + Feature-Extraction circuit are built). Pattern: ④'s
D1=SP1 decision-only commit.

**Date:** 2026-05-24 · **Item:** D6 (spawned by ④ / `poac_v2_choice_pre_investigation.md` §7).

**Evidence legend:** `[WEB:2026-05-24]` web source · `[REAS]` reasoning · `[INT]` internal corpus.

---

## §1 — The decision

**D6 = γ (verify BOTH composite halves in-circuit) is the production target for a PQ-sound binding.
α (ECDSA-P256-only, using SP1's secp256r1 precompile) is the validated *first-prototype slice* —
toolchain/wiring validation only, NOT production. β (PQ-half-only) is rejected.**

**Operator override lever (the threat-model axis, §5):** if the threat model treats the on-chain
composite-pubkey registry (② P4b `VAPIPoEPRegistry`) as a *trusted PQ-verification surface*, then α is
acceptable as production (proof classically-sound; PQ guaranteed at the system level via the registry,
not inside the proof). That is the operator's call to flip.

This is a **directional anchor** (like D1=SP1), refinable when the Feature-Extraction circuit is
actually built (WSL prototype). It does not lock byte-level circuit details.

---

## §2 — Toolchain-capability axis — RESOLVED: all three options are buildable in SP1

The 14a note flagged in-circuit ML-DSA/SLH-DSA as a "novel un-precompiled gadget." Research resolves
this in SP1's favour:

- **In-circuit ML-DSA-65 in SP1 has a public reference implementation** — `sp1-ntt-gadget` (the NTT
  gadget for Dilithium / ML-DSA-65 polynomial arithmetic) produces **production SP1 proofs at ~22
  seconds / 260 bytes, on-chain-verifiable**. A pure-Rust FIPS-204 (ML-DSA) crate (no_std + WASM-ready)
  runs in the SP1 guest. `[WEB:2026-05-24]` (sources: the `sp1-ntt-gadget` / "Dilithium ZK" writeups;
  `crates.io` ml-dsa / dilithium-rs).
- **α (ECDSA-P256)** is trivially feasible — SP1 ships a dedicated secp256r1 sig-verify precompile
  (§9 Gap 2 of the ④ investigation). `[WEB:2026-05-24]`
- **Net:** β/γ are *demonstrated*, not hypothetical. **Feasibility no longer constrains D6** — the SP1
  (zkVM) choice from D1 is exactly what makes the expensive PQ gadget tractable (write the verifier as
  Rust). The decision is now purely posture (binding strength vs cost). `[REAS]`

**Cost shape `[REAS]`:** α ≈ cheap (P-256 precompile). β/γ add the ML-DSA NTT gadget (~22s-class proving
per the reference). γ ≈ α + β. Real but tractable; the v2 SP1 migration's whole premise is paying
proving cost to gain transparency + PQ.

---

## §3 — Architectural-posture axis — why γ (not α, not β)

The Feature-Extraction circuit proves a feature vector was computed from an input **signed by the
registered device** (the ① composite-sig). The question: which half(s) of the AND-composite does the
in-circuit verification bind?

- **α (ECDSA-P256 only):** the proof cryptographically forces only the **classical** half. The ECDSA
  half is the **quantum-vulnerable** one. So a quantum adversary could forge ECDSA and produce a valid
  proof binding to a registered device **without possessing the PQ half** → **the v2 proof is
  quantum-forgeable at the binding layer.** This *reintroduces a classical break at the exact layer the
  SP1 migration exists to make PQ* — it undercuts the PoAC-v2 purpose. `[REAS]`
- **β (ML-DSA only):** attests the PQ half but **not** the classical half → it does **not** attest the
  full AND-composite (the registered identity is the *composite*; verifying one arm doesn't prove the
  composite is valid). Asymmetric and incomplete. Rejected. `[REAS]`
- **γ (both):** attests the full composite-sig; quantum-forgeable only if BOTH arms break (ML-DSA is
  PQ → not). **PQ-sound and complete** — consistent with the v2 end-to-end-PQ goal IIP-64 §4.7 frames
  ("entirely within the STARK," no classical recursion). `[REAS]`

**Conclusion:** for a binding that is actually post-quantum (the reason v2 exists), **γ is the
principled target.** α is a classical-only binding; choosing it as production would mean "PQ proof
system, classical binding" — a half-measure.

---

## §4 — Why α is still the first *prototype* slice (not production)

When the WSL prototype runs (Phase 14b step 2, env-gated), the **first** slice should still be **α**:
it's the cheapest, uses the P-256 precompile, and validates the entire SP1 toolchain + the
`zk_sp1_prover.py` real backend end-to-end with the *least* moving parts — before adding the ML-DSA NTT
gadget. The `sp1-ntt-gadget` reference (22s/260B) then de-risks the **α → γ** upgrade. So: **prototype
α first (validation), ship γ (production binding).** β is never a milestone. `[REAS]`

---

## §5 — The operator override (threat-model axis)

γ assumes the proof must be **self-contained-PQ** — verifiable by a third party who does **not** trust
the bridge *or* the on-chain registry as a PQ surface. If instead the threat model treats the **on-chain
composite-pubkey registry (② P4b) as a trusted PQ-verification surface**, then:
- the proof need only be **classically-sound** (α in-circuit), and
- the **PQ guarantee is provided at the system level** (verifier checks the proof's α-binding **plus**
  the registered composite's PQ half via the on-chain registry).

This is a legitimate, cheaper posture — it trades proof-self-containment for a registry-trust
assumption. **It is the operator's threat-model call.** QorTroller's stated thesis leans against it
("verify directly against L1 + gamer-held cert, no intermediary needed" `[INT]`) — which favours γ —
but if the L1 registry *is* accepted as the PQ anchor, α-production is defensible. Flip lever:
operator declares "registry is a trusted PQ surface" → D6 becomes α-production.

---

## §6 — Tier nuance (ML-DSA vs SLH-DSA)

① composite-sig tiers `[INT]`: credential = ECDSA-P256 + **ML-DSA-65**; user = ECDSA-P256 + **ML-DSA-44**;
device = ECDSA-P256 + **SLH-DSA-128s**. γ's PQ gadget differs by tier:
- **ML-DSA tiers** → the **NTT gadget** (`sp1-ntt-gadget` reference, ML-DSA-65; ML-DSA-44 is the same
  shape, smaller params). `[WEB:2026-05-24]`
- **device tier (SLH-DSA-128s)** → a **hash-tree verify** (no NTT; SHAKE/SHA-256-heavy → SP1's
  keccak/sha precompiles accelerate it). Distinct gadget, also zkVM-feasible, no public SP1 reference
  found this pass `[UNCERTAIN]`. If the device tier is what verifies in-circuit, budget the SLH-DSA
  hash-tree gadget separately from the ML-DSA NTT gadget.

---

## §7 — What this anchors / refinement point

- **Anchors:** future Feature-Extraction circuit work targets **γ** (full composite in-circuit) for the
  production binding; first prototype slice is **α**; β is not a milestone.
- **Refines at:** WSL prototype time (14b step 2) — measure α then γ proving cost on QorTroller's actual
  circuit; the 22s/260B `sp1-ntt-gadget` figure is the reference, not a QorTroller measurement.
- **Coupling:** D6 couples to D1 (SP1 makes γ feasible) and D2 (the prototype that yields γ's real cost).
  D4 (on-chain verify) is separate — γ's 260B-class proof still verifies via whatever D4 resolves.

---

## §8 — Cross-refs
- ④ investigation `poac_v2_choice_pre_investigation.md` (§7 D6 origin; §9 Gap 2 P-256 precompile).
- 14a `d2_seamlessness_pre_validation.md` (in-circuit ML-DSA tractability flag — now confirmed).
- ① composite-sig `composite_sig_v1_scope.md` (the AND-composite tiers γ must verify).
- ② P4b `VAPIPoEPRegistry` (the on-chain composite-pubkey registry — the §5 override's trust anchor).
- Backlog #15 (D6) → resolved by this note; #14 step 2 (WSL prototype) is where α/γ get measured.

---

## Proposal-summary for V-check
> D6 decision-only doc (Sequence C, /goal-style): the composite-sig in-circuit verification gadget =
> **γ (both halves) production target / α first-prototype-slice / β rejected**, with an operator
> override to α-production if the on-chain registry is treated as a trusted PQ surface. Feasibility
> resolved (in-circuit ML-DSA in SP1 is demonstrated by sp1-ntt-gadget, 22s/260B); the choice is purely
> architectural posture (γ = PQ-sound binding consistent with v2; α = classical-only, quantum-forgeable
> at the binding layer; β = asymmetric/incomplete). Directional anchor, refinable at WSL-prototype time.
> No code, no contract, no wallet/on-chain action, no FROZEN change.
