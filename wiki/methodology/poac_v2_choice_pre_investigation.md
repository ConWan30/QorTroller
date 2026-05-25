# Pre-④ Investigation — PoAC-v2 ZK Proving-System Choice

**Status:** FINDINGS + operator decision (Path C, 2026-05-24). The investigation body below is
findings-only and surfaces tradeoffs faithfully without pre-judging; the operator reviewed it across
two passes (initial + a three-gap research pass, §9) and resolved **D1 = SP1**, with **D5 firing in
parallel** and **D4 + D6 deferred** to follow-on work. Decision reasoning recorded in §10 and in memory
(`poac-v2-d1-sp1-architectural-decision`). No code, no scope doc, no contract change, no wallet/on-chain
action in this artifact.

**Date:** 2026-05-24
**Item:** ④ (PoAC-v2 proving-system choice)
**Pattern:** mirrors `phase_b_freeze_ceremony_pre_investigation.md` — a committable documentation
artifact once approved as a finding, even if the ④ decision is deferred.

**Evidence-source legend (honesty rail):**
- `[WEB]` — claim depends on a web-search source (production-status / ecosystem data), retrieved
  2026-05-24. Fast-moving; re-verify before relying for a decision.
- `[WEB:2026-05-24-verified]` — claim confirmed against a **primary source** on 2026-05-24 with the
  URL + extract recorded in §9 (gap-closing research pass). Higher confidence than bare `[WEB]`.
- `[INT]` — claim from the internal corpus (CLAUDE.md / memory / committed docs), point-in-time.
- `[REAS]` — analytical reasoning over the above; not a measured fact. Where it concerns QorTroller's
  own circuits, there is **no benchmark** yet (the circuits are not built) — these are shape
  arguments, not numbers.
- `[UNCERTAIN]` — explicitly thin or contested evidence.

---

## §0 — Hold framing

This is the **pre-investigation** stage of the standard discipline:
pre-investigation → operator review → scope doc / decision → operator review → execution.

The output here is **findings**. The next step is the operator's: either (a) approve this as a finding
artifact and proceed to the ④ decision based on it, or (b) surface gaps needing more research before a
decision. The investigation deliberately stops short of recommending a system.

A V-check (`vapi_validate_proposal`) is run on this note's proposal-summary before commit-or-hold (see
end of document).

---

## §1 — Goal of ④, and a load-bearing scope clarification

**What ④ is:** choose the **zero-knowledge proving system** for QorTroller's ZK circuit layer — the
layer that currently uses **Groth16 over BN254, compiled from circom** (`contracts/circuits/`). This is
the layer behind the three exclusive forward circuits:

1. **Feature Extraction Integrity Proof** — proves biometric feature vectors were computed from
   registered (signed) raw inputs without revealing the inputs. Shape: signature/commitment
   verification + deterministic feature computation + output commitment.
2. **Calibration Integrity Proof** — proves calibration parameters were derived from declared
   (committed) calibration data following the documented procedure, without revealing raw sessions.
   Shape: commitment verification + statistical computation + threshold checks.
3. **Separation Ratio ZK Proof (ZK-SEPPROOF)** — proves the inter-person separation ratio computed
   from a feature corpus exceeds a public threshold without revealing individual feature vectors.
   Shape: Mahalanobis computation + aggregation + threshold proof. **A v1 of this already exists in
   Groth16/circom** (`ZKSepProof.circom`, 804 non-linear constraints, Poseidon(5) binding,
   BIOMETRIC-SNAPSHOT-v1 anchor). `[INT]`

**What ④ is NOT — three hard scope boundaries (to prevent a FROZEN-violation misread):**

- ④ **does not touch the 228-byte PoAC wire format.** That record is `SHA-256(164B body) || 64-byte
  ECDSA-P256 signature` — a *signature record*, not a ZK proof. It is FROZEN ("Never modify the
  228-byte PoAC wire format"). The name "PoAC-v2" here refers to the **v2 ZK proving layer**, not a v2
  of the frozen record. `[INT]`
- ④ **is not ① composite-sig.** ① already migrated the *record-signature* layer toward PQ (composite
  ECDSA-P256 + ML-DSA / SLH-DSA). ④ is the **sibling PQ migration on the ZK-proof layer**: today's ZK
  verification anchor (Groth16/BN254) rests on pairings, which are **not** post-quantum. The two
  migrations are on different layers; both are needed for an end-to-end PQ story. `[INT][REAS]`
- ④ **is decision-only at this stage.** No circuit is being ported in this arc. The downstream
  consequence is what makes the choice worth getting right early: all three circuits inherit it.

**Why now (leverage):** building the two unbuilt circuits (Feature-Extraction, Calibration) on Groth16
and then migrating is rework. Choosing the v2 system before they are built lets them be authored once.
`[REAS]`

---

## §2 — Candidate proving systems

The candidates cluster into three execution-model classes. The PQ-posture dimension does **not**
strongly separate the STARK-family candidates from each other — SP1, Plonky3, and Stwo are all
hash-based (FRI / collision-resistance) and therefore PQ at the *proving* layer. The real
differentiators are **execution model**, **on-chain verification path on IoTeX**, and **ecosystem /
IIP-64 alignment**. `[REAS]`

| System | Vendor | Proof class | Execution model | PQ at proving layer | On-chain verify (EVM) | Maturity | Ecosystem |
|---|---|---|---|---|---|---|---|
| **Groth16 / circom** (incumbent) | — / iden3 | Pairing SNARK (BN254) | Hand-written circuit (circom DSL) | **No** (pairings) | Cheap (~200–300k gas), native | Mature, in production here | Large, but legacy for new PQ work `[REAS]` |
| **SP1** | Succinct | STARK (Hypercube = multilinear) | **zkVM** — arbitrary Rust → RISC-V | **Yes** (hash-based) | Via Groth16/Plonk wrap (non-PQ at boundary) **or** native (expensive) unless a precompile exists | Production; SP1 Hypercube live on mainnet; audited (Veridise/Cantina/Zellic/KALOS); all 62 RISC-V opcodes formally verified | Large; Rust; OP Succinct; built on Plonky3 `[WEB]` |
| **Plonky3** | Polygon | STARK / FRI (Goldilocks / Mersenne) | **Toolkit** — build your own AIR / zkVM (PIOP toolkit, *not* a zkVM) | **Yes** (hash-based FRI) | Same wrap-or-precompile story | Production-ready (Jul 2024); powers SP1 + Valida | Lower-level; most engineering effort `[WEB]` |
| **S-two / Stwo** | StarkWare | Circle STARK (M31 31-bit Mersenne) | **Cairo** programs + custom-AIR core lib | **Yes** (hash-based) | Same wrap-or-precompile story; native verify is Starknet-centric | Production; live on Starknet mainnet (Nov 2025); v2.0.0 (Jan 2026); on crates.io | Cairo-centric + Rust core lib; Scarb tooling `[WEB]` |
| **RISC Zero** | RISC Zero | STARK / FRI | **zkVM** — arbitrary Rust → RISC-V | **Yes** (hash-based) | Default path wraps in Groth16 (Bonsai) → **non-PQ at boundary** | Production, audited, established | Rust; mature; managed proving service; accelerates P-256 via 256-bit-modmul accelerator + patched crates (§9 Gap 2) `[WEB:2026-05-24-verified]` |
| **Halo2** | Zcash/PSE | PLONKish (KZG or IPA) | Hand-written circuit (Rust DSL) | **No** (KZG = pairing; IPA = discrete-log) | Cheap (KZG) | Mature (Zcash, Scroll, Axiom) | Large, but **fails the PQ premise** `[REAS]` |
| **Plonky2** | Polygon | PLONK + FRI (Goldilocks) | Circuit framework | Yes (FRI) | Wrap-or-precompile | Production, but **superseded by Plonky3** for new work | Legacy `[WEB/REAS]` |

**Reading of the field:**
- **Halo2 is effectively ruled out by the premise.** Its commitment schemes (KZG pairing / IPA
  discrete-log) are not post-quantum; choosing it would not advance the v2 PQ goal despite its
  maturity. Kept in the table for completeness. `[REAS]`
- **Plonky2 is dominated by Plonky3** for greenfield work (same vendor, newer, the one marked
  production-ready). `[WEB]`
- **SP1, Plonky3, Stwo, RISC Zero** form the live PQ-proving-layer shortlist. They are *not fully
  disjoint families*: SP1 is built on Plonky3; Circle STARK (Stwo) was a Polygon×StarkWare
  collaboration. They share FRI/hash-based PQ DNA. `[WEB]`
- The execution-model split inside the shortlist is the decision-relevant axis: **zkVM** (SP1, RISC
  Zero — write the computation in Rust) vs **toolkit** (Plonky3 — hand-write AIRs) vs **Cairo** (Stwo).

---

## §3 — QorTroller circuit shapes × per-system fit

All three circuits share a profile: **crypto-verification-heavy** (SHA-256 commitments, ECDSA-P256
record-signature or ① composite-sig verification) **+ computation-heavy** (FFT tremor features,
Mahalanobis distance, covariance, statistical thresholds). This profile is the single most important
input to the fit assessment. `[REAS]`

**Why the profile matters — arithmetization gotchas:**

- **Hand-written-circuit systems (circom/Groth16, Plonky3, Halo2):** SHA-256 is *very* expensive in
  R1CS/AIR (Poseidon is cheap — which is exactly why `ZKSepProof.circom` uses Poseidon, not SHA-256,
  for its in-circuit binding `[INT]`). **ECDSA-P256 (secp256r1) verification in-circuit is brutal** —
  non-native field arithmetic over the P-256 base field inside a BN254/Goldilocks circuit is one of the
  most expensive standard gadgets. Statistical math (Mahalanobis, FFT) needs **manual fixed-point
  scaling** (the `1e9` scale in BIOMETRIC-SNAPSHOT is exactly this pattern `[INT]`) and hand-managed
  range checks. Complex circuits hit constraint walls and ceremony-size limits fast (current ceremony
  budget is 2^11 powers-of-tau `[INT]`). `[REAS]`
- **zkVM systems (SP1, RISC Zero):** you write the feature extraction, Mahalanobis, and signature
  verification as **ordinary Rust**, test it as ordinary Rust, then prove the execution. SHA-256,
  ECDSA, fixed/float math, FFT "just work" as library calls; cost is per-VM-cycle with **precompiles**
  accelerating hot primitives. For QorTroller's statistics-heavy circuits this is a large
  developer-velocity and correctness advantage (no hand-translation of Mahalanobis into R1CS).
  **P-256 precompile coverage — RESOLVED (§9 Gap 2):** **SP1 ships a dedicated secp256r1 / P-256
  signature-verification precompile** (built for Secure-Enclave / WebAuthn / FIDO2 signatures) — so
  the in-circuit ECDSA-P256 check (the PoAC curve) is a **first-class accelerated gadget** in SP1.
  RISC Zero accelerates P-256 via its 256-bit modular-multiplication accelerator + patched `p256`/`k256`
  crates (field-arithmetic acceleration, not a single one-shot verify precompile). Plonky3 (toolkit)
  and Stwo (Cairo) have no "precompile" in the same sense; the P-256 gadget there is whatever you
  build. `[WEB:2026-05-24-verified]`
- **Plonky3 (toolkit):** maximum control, maximum effort — you author AIRs by hand. Likely overkill
  unless QorTroller needs one bespoke ultra-optimized circuit and has the engineering bandwidth.
  `[REAS]`
- **Stwo (Cairo):** Cairo is higher-level than raw AIR; you'd write circuits in Cairo or drop to the
  custom-AIR core lib. Ecosystem gravity is Starknet. `[REAS]`

**Per-circuit shape notes:**

| Circuit | Dominant cost driver | zkVM fit | Hand-circuit fit |
|---|---|---|---|
| Feature Extraction Integrity | signature verify (**which signature is UNDEFINED — see D6**) + FFT/feature math | **Strong** if ECDSA-P256-only (SP1 P-256 precompile, §9 Gap 2); **range-dependent** if composite-sig (D6 β/γ add a novel ML-DSA/SLH-DSA in-circuit gadget) | Weak — non-native sig-verify is the killer gadget; far worse for a PQ-sig half |
| Calibration Integrity | commitment verify + statistics + thresholds | **Strong** — statistics as Rust | Moderate — manual fixed-point + range checks |
| ZK-SEPPROOF (exists in Groth16) | Mahalanobis + Poseidon binding + threshold | Good — Mahalanobis as Rust; re-do Poseidon binding | **Already built** here; a direct re-impl gives an apples-to-apples benchmark |

> **Gadget-undefined caveat (D6).** The Feature-Extraction "dominant cost driver: signature verify"
> framing is **too generous until D6 is resolved**: the in-circuit cost depends entirely on *which*
> part of the ① composite-sig verifies in-circuit — the ECDSA-P256 half (cheap on SP1), the ML-DSA /
> SLH-DSA PQ half (a novel, un-precompiled gadget in *every* candidate), or both. The cost driver is a
> **range of possibilities**, not a single quantity, until the operator resolves D6 (§7). `[REAS]`

**Tradeoff axes (proving time / verify time / proof size), qualitatively `[REAS]`:**
- Groth16: tiny proof (~200 B), cheap verify, but heavy/limited circuit authoring and **not PQ**.
- STARK-family (all four): larger proofs, **transparent (no per-circuit trusted setup ceremony)** —
  this removes the ZK-SEPPROOF-style MPC ceremony per circuit, a real operational simplification —
  PQ proving, but **on-chain verify is the open cost** (see §4). zkVMs add proving overhead vs a
  hand-tuned circuit but collapse engineering cost.

**No numbers yet, by design.** QorTroller's circuits are not built, so there is no measured
proving-time/proof-size data for *these* circuits on *any* system. Getting real numbers is exactly
what a first prototype (§7, D2) would produce. Treat all §3 fit claims as shape arguments. `[REAS]`

---

## §4 — IoTeX integration story (the load-bearing dimension)

IoTeX testnet (chain 4690) is EVM-compatible; the current Groth16 verifiers (`PitlSessionProofVerifier`,
`Groth16VerifierZKSepProof` + `ZKSepProofVerifier` wrapper) verify on-chain today at normal SNARK gas
cost. `[INT]` The PQ migration runs into one hard fact:

**A STARK proof is PQ at generation, but verifying it on-chain has two paths, and only one is PQ:**

1. **Wrap the STARK in a Groth16/Plonk SNARK** for cheap EVM verification (the standard zkVM→EVM path,
   e.g. RISC Zero Bonsai, SP1's EVM-verifier output). Cheap gas, **but the on-chain verification anchor
   is once again a pairing-based SNARK → NOT post-quantum at the verification boundary.** The proof is
   PQ-generated but classically-verified. This is a *partial* PQ story. `[REAS]`
2. **Verify the STARK natively on-chain.** End-to-end PQ, **but** a raw STARK verifier in EVM bytecode
   (no precompile) costs on the order of millions of gas — impractical. It becomes practical only if
   **IoTeX ships a native STARK / SP1 verification precompile.** `[REAS]`

**This is the single most important honest caveat of the whole investigation:** PoAC-v2's *end-to-end*
PQ claim is **gated on IoTeX's precompile roadmap**, not just on the proving-system choice. Until a
STARK-verify precompile exists, the realistic deployment is "PQ proving + Groth16-wrapped classical
verification on-chain."

**Alignment signal — RE-VERIFIED against primary source (§9 Gap 1) `[WEB:2026-05-24-verified]`:**
IIP-64 #72 **§4.7 explicitly names SP1**: *"the migration proof system uses SP1 (Succinct's
STARK-native zkVM) to generate proofs that remain entirely within the STARK"* — and explicitly avoids
the *"quantum-vulnerable Groth16 final recursion step."* This is **stronger than the internal reading
and directly validates Path 2 above**: IoTeX's own stated direction is the **native-STARK,
no-Groth16-wrap** path precisely because the Groth16 recursion is the quantum-vulnerable step. So the
PQ-preserving verification route is IoTeX's declared philosophy, not a QorTroller invention.

**But one precision correction the re-verification forces (§9 Gap 1):** the **0x0B precompile is for PQ
*signature* verification** (§4.2 verbatim: *"A new precompiled contract is deployed at a designated
address (proposed: `0x0B`) implementing PQ signature verification"*) — i.e. ML-DSA / SLH-DSA signatures,
which is **①'s on-chain story, not ④'s**. The internal engagement doc conflated "0x0B = the PQ
precompile" with a STARK-*proof*-verification precompile. **§4.7's SP1 usage is about account-key
*migration* proofs**, and the extract does **not** confirm that IoTeX exposes a general **app-layer
STARK-verifier precompile** that QorTroller's *own* circuits (Feature-Extraction / Calibration /
ZK-SEPPROOF) could call on-chain. So: the **system-identity** signal (SP1) is now confirmed and the
**no-Groth16 philosophy** is confirmed, but the **app-layer on-chain STARK-verify availability** for
QorTroller's circuits remains **unconfirmed** → this keeps **D4 and D5 load-bearing** (D5 = ask IoTeX
directly whether the §4.7 SP1/STARK verification surface is reusable at the app layer or is
migration-only). `[WEB:2026-05-24-verified]` for what §4.7/§4.2 say; `[UNCERTAIN]` for app-layer reuse.

### §4.A — 0x0B correction (vs internal engagement doc) — PROMINENT

> **0x0B correction.** IIP-64 **§4.2 verbatim** defines `0x0B` as the **PQ-signature verification
> precompile (ML-DSA / SLH-DSA)** — *not* a STARK-proof-verify precompile. The original engagement-doc
> interpretation **conflated two distinct precompile concepts**:
>
> - **`0x0B` = PQ-signature precompile** — relevant to **① composite-sig's** on-chain verification
>   surface (the record-signature layer).
> - **A potential STARK-verify precompile** = a *different* surface, with **no address-specific name
>   in IIP-64 §4.7**. The open **D4** question is whether/when it ships and whether it is
>   **app-layer-reusable** (vs migration-proof-specific).
>
> The **SP1 alignment argument (§6) is philosophical** — IoTeX names SP1 in §4.7 as their
> migration-proof system — **not address-specific**. The original *"SP1 + 0x0B precompile alignment"*
> framing was **incorrect on the precompile-address detail**. `[WEB:2026-05-24-verified]`

This correction does not weaken D1 (the SP1 system choice rests on §4.7's naming + circuit-shape fit +
P-256 precompile, none of which depend on 0x0B). It relocates the 0x0B fact to where it actually
belongs — ①'s on-chain story — and isolates the genuine ④ open question (app-layer STARK-verify
reuse) as D4/D5. See also the ① dependency tracked in `composite_sig_v1_scope.md`.

**Gas cost summary `[REAS]`:** Groth16 verify ~200–300k gas (cheap, today). Native STARK verify with no
precompile = millions of gas (impractical). Precompile = cheap + PQ (roadmap-dependent).

**Transition path from PoAC-v1 (Groth16):** a new verifier contract per circuit, selected by a version
byte in the on-chain anchor; v1 and v2 verifiers coexist. The AdjudicationRegistry sourceType-attribution
anchoring pattern already used by all FROZEN-v1 primitives extends to a v2 anchor without disturbing v1.
`[INT][REAS]`

> **CORRECTION (2026-05-24):** per the 14a seamlessness pre-validation
> (`d2_seamlessness_pre_validation.md` §1 self-correction), the actual coexistence mechanism is
> **per-verifier-contract** (each circuit = its own deployed contract), **not** version-byte routing.
> The version-byte framing in this paragraph was an abstraction, not an existing codebase mechanism.
> The architectural conclusion (additive coexistence) **holds** via the cleaner per-contract pattern.

---

## §5 — Migration-timing considerations

**Timing drivers:**
- NIST classical-crypto deprecation horizon (ECDSA/RSA): deprecate ~2030, disallow ~2035. The quantum
  threat to Groth16 (pairings/discrete-log) sits on the same horizon. `[REAS]`
- IIP-64 Phase 1 = **2027 Q3** `[INT]` — the internal engagement targets PoEP riding the IIP-64
  app-layer credential path on Phase 1. PoAC-v2 ZK does not need to ship *immediately*; there is
  runway. `[INT]`

**Coexistence vs hard cutover:** coexistence is feasible and cheaper in risk. Groth16-v1 verifiers stay
live; v2 (STARK-family) ships behind a version byte; tournaments/marketplace consult whichever the
anchor declares. *(CORRECTION 2026-05-24: "behind a version byte" is the same abstraction corrected in
§4 above — actual coexistence is per-verifier-contract, see `d2_seamlessness_pre_validation.md` §1.)*
**Operational cost of running both:** two prover code paths + two verifier contract
stacks + two ceremony/setup regimes (note: STARK-family is *transparent* — no per-circuit MPC ceremony,
which actually *reduces* one axis of the dual-stack cost vs the current Groth16 ceremony burden).
`[REAS]`

**The asymmetry that argues for an early *choice* (not early *cutover*):** the two unbuilt circuits
should be authored on the v2 system to avoid double work; the existing Groth16 ZK-SEPPROOF can migrate
on a relaxed schedule. So "decide early, build new on v2, migrate the one existing circuit later" is a
coherent low-risk posture — but it is the operator's to choose (§7, D3). `[REAS]`

---

## §6 — IIP-64 / PQ-alignment dimension

SHA-256 (QorTroller's commitment fabric — all PATTERN-017 families) is already PQ-safe. `[INT]` The two
non-PQ surfaces are: (a) the **record-signature** layer (ECDSA-P256) — being addressed by ① composite-sig;
and (b) the **ZK-proof** layer (Groth16/BN254 pairings) — the subject of ④.

**Which candidate gives the strongest PQ story?**
- At the **proving** layer, all four shortlist systems are equivalent (hash-based, PQ). So PQ-posture
  alone does **not** select among SP1 / Plonky3 / Stwo / RISC Zero. `[REAS]`
- At the **verification** layer (where the real PQ gap is, §4), the differentiator is **which system
  IoTeX aligns with.** This is now **confirmed from primary source (§9 Gap 1)**: IIP-64 §4.7 names
  **SP1** and stays **entirely within STARK, avoiding the quantum-vulnerable Groth16 recursion.** So
  SP1 is the strongest *alignment* pick — choosing it puts QorTroller on the same proving system
  IoTeX's own PQ roadmap names. `[WEB:2026-05-24-verified]`
- **Caveat that tempers the alignment strength (§9 Gap 1):** §4.7's SP1 usage is for account-key
  *migration* proofs, and the 0x0B precompile is for PQ *signatures* (§4.2), not for verifying
  app-layer STARK proofs. Whether QorTroller's *own* circuits can ride a reusable on-chain
  STARK-verify surface is **unconfirmed** — so the alignment is strong on *system identity and PQ
  philosophy* but does **not** yet guarantee a cheap PQ on-chain verify path for QorTroller's
  circuits. `[UNCERTAIN]` → **D5 becomes more load-bearing** (ask IoTeX directly).
- RISC Zero's default Groth16-wrap verification path is the weakest *end-to-end* PQ story of the
  shortlist (PQ proving, classical verify) — and is the *opposite* of IIP-64's stated no-Groth16
  philosophy — unless paired with a native STARK-verify path too. `[REAS]`

**Conditional-novelty note (honesty rail):** QorTroller's *composition* — PQ SHA-256 commitments +
composite-sig PQ record signatures + STARK ZK over biometric features + the three-zone privacy topology
(bridge sees biometrics / W3bstream sees proof / chain sees only anchor `[INT]`) — may constitute a
distinct combination claim **independent of which individual proving system is chosen**. The novelty, if
any, is in the assembled trust topology, not in adopting SP1/Stwo/Plonky3 per se. Do not overclaim the
proving-system choice as itself novel. `[REAS]`

---

## §7 — Open operator decisions (surfaced, NOT resolved)

- **D1 — Which proving system to commit to** (after reading this). The structuring sub-question:
  commit to the **zkVM execution model** (SP1 / RISC Zero — favored by the statistics-heavy circuit
  shape, §3) vs **hand-circuit toolkit** (Plonky3 — max control, max effort) vs **Cairo** (Stwo) vs
  **stay on Groth16 for now** (defer the PQ-verify gap until IoTeX precompile clarity). **After the
  gap-closing pass, two of three signals point at SP1 with primary-source backing:** §3 (circuit
  shape) leans zkVM; §3-Gap-2 confirms SP1 has the **P-256 sig-verify precompile** the
  Feature-Extraction circuit needs; and §4/§6-Gap-1 confirms **IIP-64 §4.7 names SP1 by name** and
  rejects the Groth16 recursion. The remaining open variable is the **app-layer on-chain verify**
  path (D4) — strong but not closed. The investigation now reports a **well-supported SP1 lean** but
  still **does not make the call**; that is D1, the operator's.
- **D2 — Which of the three circuits to prototype first** to validate the pick. Hook for the operator:
  **ZK-SEPPROOF already exists in Groth16**, so re-implementing it on the candidate system yields a
  direct apples-to-apples benchmark *and* a migration template for the other two. That is a strong
  "prototype-first" candidate — but it is the operator's call (Feature-Extraction exercises the
  hardest gadget — in-circuit signature verify — and might be the more informative stress test).
- **D3 — Migration-timing posture:** aggressive cutover vs gradual coexistence (build-new-on-v2,
  migrate-existing-later) vs deferred-until-IoTeX-precompile-clarity.
- **D4 — On-chain verification strategy (the load-bearing one, §4):** wait for an IoTeX app-layer
  STARK-verify surface (end-to-end PQ, **and aligned with IIP-64 §4.7's confirmed no-Groth16
  philosophy** — but availability for app-layer circuits is unconfirmed, §9 Gap 1) vs Groth16-wrap now
  (ships sooner, classical verification boundary, partial PQ, **against** IIP-64's stated direction).
  Refined by the gap pass: IoTeX *does* declare a native-STARK philosophy, so the "wait" option is
  better-founded than before — but it is **migration-proof** evidence, not **app-layer-verify**
  evidence. Interacts with D1, D3, and D5.
- **D5 — External engagement (now more load-bearing, §9 Gap 1):** whether to engage Succinct /
  StarkWare / Polygon / the IoTeX core team. The IIP-64 #72 thread (a prepared engagement comment
  already exists, operator-posted) is the natural venue to ask IoTeX the **one question the gap pass
  could not resolve from the document**: is the §4.7 SP1/STARK verification surface **reusable at the
  app layer** for downstream protocols' own circuits, or is it **migration-only**? The answer
  collapses D4's uncertainty. This question is more specific — and more decision-critical — than the
  pre-gap version.
- **D6 — Composite-sig in-circuit verification gadget (NEW, §9 Gap 3):** if the Feature-Extraction
  circuit verifies the ① composite-sig (not bare ECDSA-P256), *which* half(s) verify in-circuit is
  undefined and materially changes the cost driver (§3 gadget-undefined caveat). Three options:
  - **Option α — ECDSA-P256 half only in-circuit; PQ half verified out-of-circuit.** Simplest gadget
    (SP1 P-256 precompile, §9 Gap 2). **Weakest in-circuit PQ binding** — the ZK proof attests only
    the classical half; the PQ half's validity is asserted elsewhere, outside the proof's guarantee.
  - **Option β — ML-DSA (PQ) half only in-circuit; ECDSA half out-of-circuit.** **Stronger in-circuit
    PQ story.** But ML-DSA verification in-circuit = NTT polynomial arithmetic over `Z_q`
    (q=8380417, n=256) + SHAKE-256 sampling + norm/range checks — a **novel gadget with no standard
    precompile in *any* candidate** (SP1/RISC Zero keccak precompiles help the SHAKE part; the NTT
    is custom). Tractable in a zkVM (write the NTT in Rust); brutal in a hand-circuit. For the
    **SLH-DSA device tier**, the in-circuit cost is instead an enormous *hash count* (hypertree =
    thousands of SHA-256 calls) — well-suited to a zkVM with a SHA-256 precompile but large.
  - **Option γ — both halves in-circuit.** **Strongest end-to-end binding**; **most expensive** (two
    non-standard gadgets at once: accelerated P-256 + novel ML-DSA/SLH-DSA).
  D6 **interacts with D1** (the chosen system constrains which gadgets are even feasible — a zkVM
  makes β/γ tractable; a hand-circuit system makes them near-prohibitive) and **with D2**
  (Feature-Extraction is where the gadget choice manifests, so prototyping that circuit first would
  force D6 early). `[REAS]`

---

## §8 — Cross-refs (protocol surface ④ would touch)

- **FROZEN, untouched by ④:** 228-byte PoAC wire format (`SHA-256(164B) || 64B ECDSA-P256`). ④ is the
  ZK-proof layer, not the record. (Hard Rules: "Never modify the 228-byte PoAC wire format.")
- **Migration surface (existing ZK stack):** `contracts/circuits/` (`ZKSepProof.circom`,
  `TeamProof.circom`, `TournamentPassport.circom`); on-chain verifiers `PitlSessionProofVerifier`
  (`0x07D3ca15…`), `Groth16VerifierZKSepProof` (`0xD63EEf13…`) + `ZKSepProofVerifier` wrapper
  (`0xd51a21E2…`); `PITLSessionRegistry` (`0x8da0A497…`). All Groth16/BN254 today.
- **BIOMETRIC-SNAPSHOT-v1** (6th FROZEN-v1 primitive, Poseidon(5) binding, 1e9 scale, AdjudicationRegistry
  anchor) — the existing ZK-SEPPROOF commitment fabric; directly relevant to the Feature-Extraction and
  ZK-SEPPROOF circuits. `[INT]`
- **① composite-sig** (`l9_presence/composite_sig.py`) — sibling PQ migration on the record-signature
  layer; ④ is the ZK-layer sibling. If the Feature-Extraction circuit verifies the *composite-sig*
  (not bare ECDSA-P256) in-circuit, that gadget choice couples ④ to ①. `[INT][REAS]`
- **IIP-64 #72** — RE-VERIFIED from primary source (§9 Gap 1): **§4.7 names SP1, stays within STARK,
  rejects the Groth16 recursion**; **§4.2's 0x0B precompile is for PQ *signatures* (ML-DSA/SLH-DSA),
  not STARK-proof verification** — relevant to ①, not directly to ④. §2.4 = SHA-256 PQ-safe. §4.1
  alg-ID table present (ML-DSA-44=0x01, ML-DSA-65=0x02, + ML-DSA-87 / SLH-DSA / FN-DSA-512). Prepared
  engagement comment: `docs/qortroller-iip64-pr72-engagement.md`. **Open question for D5:** is the
  §4.7 verification surface app-layer-reusable or migration-only? `[WEB:2026-05-24-verified]` /
  `[UNCERTAIN]` for the app-layer-reuse question.
- **AdjudicationRegistry** sourceType-attribution anchoring pattern — extends to a v2 verification
  anchor without disturbing v1. `[INT]`
- **Ceremony note:** STARK-family is transparent → a v2 path **removes** the per-circuit MPC ceremony
  (Step E `ZKSepProof_final.zkey` style) that Groth16 requires. `[REAS]`

---

## §9 — Gap-closing research pass (2026-05-24, operator-directed)

The operator approved this note as a finding artifact contingent on closing three gaps before the ④
decision. Each finding below is re-verifiable: URL + access date recorded. Where a source contradicts
the internal engagement doc, the contradiction is surfaced, not reconciled.

### Gap 1 — Re-verify IIP-64 #72 §4.7 against the live PR text — **OUTCOME: CONSISTENT + one correction**

- **Method note (honesty):** the GitHub *PR-page* fetch (`github.com/iotexproject/iips/pull/72`)
  returned mostly **QorTroller's own engagement comment** (ConWan30) echoing the internal "SP1/STARK +
  0x0B" reading — a **circular source**, explicitly *not* a confirmation. The raw `.patch` host
  refused connection. Primary text was obtained from the **GitHub files API** instead.
- **Primary source:** `https://api.github.com/repos/iotexproject/iips/pulls/72/files` (accessed
  2026-05-24).
- **§4.7 verbatim:** *"the migration proof system uses SP1 (Succinct's STARK-native zkVM) to generate
  proofs that remain entirely within the STARK"* — and it avoids the *"quantum-vulnerable Groth16
  final recursion step."* → **SP1 named; native-STARK / no-Groth16 philosophy confirmed.**
- **§4.2 verbatim:** *"A new precompiled contract is deployed at a designated address (proposed:
  `0x0B`) implementing PQ signature verification."* → **CORRECTION:** 0x0B = PQ *signature* precompile
  (ML-DSA/SLH-DSA), **not** a STARK-proof-verify precompile. The internal doc conflated the two.
  Relevant to ①, not directly ④.
- **§4.1 alg-ID table:** present — ML-DSA-44=0x01, ML-DSA-65=0x02 (+ ML-DSA-87, SLH-DSA variants,
  FN-DSA-512). §2.4 (hash security), §4.6 (DePIN device migration), §4.8.5 (iPACT rescue) all present.
- **Residual `[UNCERTAIN]`:** §4.7's SP1 usage is for **account-key migration** proofs; the extract
  does **not** establish an **app-layer-reusable** on-chain STARK-verify surface for QorTroller's own
  circuits. → maps to the operator's "partially underspecified" branch on the *app-layer-reuse*
  question → **D5 more load-bearing.**
- **Corroborating author-research (non-specific but supportive):** the IIP-64 author Xinxin Fan has
  *published* the "attach a hash-based zk-STARK proof to each transaction" PQ direction — Cointelegraph,
  *"Hash-based zero-knowledge tech can quantum-proof Ethereum — XinXin Fan"*
  (`https://cointelegraph.com/news/zero-knowledge-proofs-quantum-proof-ethereum-xin-xin-fan`); ICBC
  2024 Best Paper *"Enabling a Smooth Migration towards Post-Quantum Security for Ethereum"*
  (`https://pqcee.github.io/Enabling_a_Smooth_Migration_towards_Post_Quantum_Security_for_Ethereum.pdf`).
  Confirms the *hash-based zk-STARK family* at author-research level; does not itself name SP1 in §4.7
  (that came from the files-API extract above).

### Gap 2 — Verify SP1 / RISC Zero P-256 (secp256r1) precompile coverage — **OUTCOME: FAVORABLE**

- **SP1:** ships a **dedicated secp256r1 / P-256 signature-verification precompile** (built for
  Secure-Enclave / Android-Keystore / WebAuthn / FIDO2 signatures); request tracked in
  `https://github.com/succinctlabs/sp1/issues/230`, shipped per Succinct's optimized-precompiles
  announcement (`https://blog.succinct.xyz/succinctshipsprecompiles/`). SP1 also has secp256k1,
  bn254, bls12-381, keccak, sha256 precompiles. (accessed 2026-05-24) → **§3 "zkVM-Strong" for the
  in-circuit ECDSA-P256 gadget holds for SP1.**
- **RISC Zero:** accelerates P-256 via its **256-bit modular-multiplication accelerator + patched
  `p256`/`k256` crates** (field-arithmetic acceleration; not a single one-shot sig-verify precompile)
  — `https://dev.risczero.com/api/zkvm/precompiles` (accessed 2026-05-24). → Moderate-Strong; the
  P-256 sig-verify is accelerated but less turnkey than SP1's dedicated precompile.
- **Plonky3 / Stwo:** no "precompile" in the zkVM sense (toolkit / Cairo); the P-256 gadget is whatever
  is hand-built. Gap is zkVM-specific, as the operator noted.

### Gap 3 — Composite-sig in-circuit gadget undefined — **OUTCOME: surfaced as D6**

- Analysis only (no web source). Added **D6** to §7 (options α/β/γ) and a **gadget-undefined caveat**
  to the §3 per-circuit table. Key technical finding: an in-circuit **ML-DSA** verify (Option β/γ) is a
  **novel gadget with no standard precompile in any candidate** (NTT over `Z_q` + SHAKE-256 + norm
  checks); an in-circuit **SLH-DSA** (device tier) is hash-count-dominated (hypertree). Both are
  tractable in a zkVM, near-prohibitive in a hand-circuit — which **reinforces the zkVM lean** if the
  operator wants a strong in-circuit PQ binding (β/γ) rather than the classical-only α.

### Net effect on the investigation's directional signal
- **D1 SP1 lean: strengthened** — now backed by primary-source §4.7 (system named) + confirmed SP1
  P-256 precompile (the hardest Feature-Extraction gadget) + the no-Groth16 philosophy matching §4's
  PQ-preserving route.
- **D4/D5 uncertainty: relocated, not eliminated** — the open question sharpened from "is the SP1
  reading real?" (now answered: yes) to "is IoTeX's STARK-verify surface app-layer-reusable?" (still
  open; D5 is the path to close it).
- **D6: new** — the composite-sig in-circuit binding strength is an unresolved design axis that
  interacts with D1 and D2.

---

## §10 — Decision: Path C (operator, 2026-05-24)

**Decision: commit to D1 = SP1; fire D5 in parallel; defer D4 + D6 to follow-on work.**

**Reasoning (the architectural rationale, preserved in the permanent record):**
1. **D1 = SP1 is well-supported by three *independent* signals:** circuit-shape fit (§3 + Gap 2 P-256
   precompile), philosophical alignment (§4.7 primary-source, SP1 named, "entirely within the STARK",
   no Groth16 recursion), and in-circuit ML-DSA tractability (Gap 3 zkVM-vs-hand-circuit asymmetry).
   Three independent legs, not one.
2. **D1's support is independent of D4's outcome.** Even if D4 resolves "migration-only" and QorTroller
   must Groth16-wrap for on-chain verify, SP1 is still the right zkVM for the *proving* layer — the
   on-chain verification path is then a **deployment** question, not a **proving-system** question.
3. **Deferring D1 pending D5 = decision-paralysis without architectural benefit.** The two unbuilt
   circuits (Feature-Extraction-Integrity, Calibration-Integrity) need an anchor system to be authored
   against; SP1 provides that anchor independently of D4's resolution.
4. **D5 fires in parallel** (engage IoTeX on the app-layer STARK-verify reusability question via
   IIP-64 PR #72). It informs **deployment posture (D3 timing)** without blocking the proving-system
   commitment.
5. **D6 (composite-sig in-circuit gadget α/β/γ) is an operator design decision best made when
   Feature-Extraction-Integrity scope work begins** (sequenced with D2). Resolving D6 prematurely would
   lock the gadget architecture before the bridge-layer-vs-circuit-layer binding-strength tradeoff is
   concrete.

**Status of each decision after Path C:**
- **D1 — RESOLVED:** SP1.
- **D2 — open (follow-on):** first SP1 circuit prototype; operator picks which circuit
  (ZK-SEPPROOF apples-to-apples vs Feature-Extraction hardest-gadget stress).
- **D3 — open:** timing posture; informed by D5's answer.
- **D4 — open (follow-on, fed by D5):** on-chain verify strategy (app-layer STARK-verify if reusable,
  else Groth16-wrap as a deployment choice).
- **D5 — firing in parallel (operator-timed):** IoTeX engagement on app-layer STARK-verify reuse.
- **D6 — deferred to D2:** composite-sig in-circuit gadget choice.

---

## Proposal-summary for V-check (updated post-gap-pass)

> ④ pre-investigation (gap-closed): a findings-only investigation note comparing ZK proving systems
> (SP1, Plonky3, S-two/Stwo, RISC Zero, Halo2, Groth16 incumbent) for QorTroller's three forward ZK
> circuits (Feature-Extraction-Integrity, Calibration-Integrity, ZK-SEPPROOF). After a three-gap
> research pass: §4.7 re-verified from primary source (names SP1, stays within STARK, no Groth16);
> 0x0B corrected to a PQ-signature precompile (relevant to ①, not ④); SP1 P-256 precompile confirmed;
> composite-sig in-circuit gadget surfaced as new decision D6. The note surfaces operator decisions
> D1–D6 and does not select a system. ④ targets the ZK-proof layer only; it does NOT modify the FROZEN
> 228-byte PoAC wire format (SHA-256 of 164-byte body + 64-byte ECDSA-P256 signature) and is distinct
> from the ① composite-sig record-signature migration. "PoAC-v2" = the v2 ZK proving layer, not a v2
> of the frozen record. No code, no contract change, no wallet operation, no on-chain action.
