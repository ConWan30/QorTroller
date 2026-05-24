# D2 Seamlessness Pre-Validation (Phase 14a) — Findings

**Status:** FINDINGS ONLY — held for operator review. Read-only + docs + design pass. No code, no
prototype, no toolchain installed in this step. This is the **evidence gate** the operator set on
2026-05-24 before committing to the D2 SP1 circuit-build arc (14b).

**Date:** 2026-05-24
**Gate question:** Does substantial evidence align that SP1 prototype work can be **seamlessly
integrated within QorTroller's already-established architectural foundational bridge** — *before* we
commit effort to building on that assumption?

**Verdict (headline):** **GREEN — no architectural blockers found.** The bridge is genuinely
prover-additive (proven 6× already); SP1's invocation surface matches the existing subprocess pattern;
mock-mode is native to the convention; the anchor and FROZEN wire-format surfaces are untouched by an
additive new prover + verifier. Integration follows the *established additive path*, not a new
framework. Caveats below are AMBER notes **within** the green — none is a blocker; several are
toolchain/ops facts to plan around. The remaining true-seamless proof is 14b's minimal
produce-and-verify slice; 14a establishes nothing blocks it.

**Evidence-source legend:** `[CODE]` cited file:line (read-only, 2026-05-24). `[WEB:2026-05-24]`
web source (re-verify before relying). `[DESIGN]` analytical assessment over the above.

---

## Criterion 1 — Prover abstraction is genuinely pluggable — **GREEN (convention, not framework)**

**Evidence `[CODE]`:** the bridge already runs **six coexisting prover modules**, each a standalone
class following the same dual-mode shape:
- `bridge/vapi_bridge/zk_prover.py:94` `ZKProver`
- `bridge/vapi_bridge/continuity_prover.py:36` `ContinuityProver`
- `bridge/vapi_bridge/passport_prover.py:97` `PassportProver`
- `bridge/vapi_bridge/pitl_prover.py:103` `PITLProver`
- `bridge/vapi_bridge/zk_sepproof_prover.py:134` `ZKSepProofProver`
- (+ `bridge/zk_prover.py:94` legacy `ZKProver`)

Each is invoked **directly at its call site**, not via a registry/dispatcher:
`dualshock_integration.py:2369` (`self._pitl_prover.generate_proof(...)`), `passport_prover.py:103`,
`transports/http.py:466`. Adding a prover = a new module + wiring at the call site(s) that need it;
**existing provers are not modified.**

**Honest nuance:** this is **convention-pluggability, not framework-pluggability.** There is no abstract
base class / registry enforcing the prover contract — each prover is hand-written to the same shape
(`generate_proof(...) -> ...Result`, module-level `*_ARTIFACTS_AVAILABLE` flag, mock/real branch). So a
new `zk_sp1_prover.py` *follows the proven convention*; it does not "register into" a framework. For
seamless-integration purposes this is still GREEN — the "add a prover" path is established and additive
(done 6×) — but the contract is discipline-enforced, not type-enforced. `[CODE][DESIGN]`

**Coexistence at the contract layer — SELF-CORRECTION:** `ZKSepProofVerifier.sol` has **no
version/proofType routing** (grep: no matches). Coexistence is achieved by **a separate verifier
contract per circuit** (ZKSepProofVerifier, PitlSessionProofVerifier, Groth16VerifierZKSepProof are
distinct deployed contracts). The "version-byte routing" mechanism named in
`poac_v2_choice_pre_investigation.md` (§4 transition path, §5) was an **abstraction, not an existing
codebase mechanism.** The real model is per-circuit modularity: an SP1 verifier is simply **another
contract**, deployed alongside. This is cleaner than a router and means **nothing version-router needs
to exist or be built.** Future sessions: do not go looking for a version-byte router — there isn't one,
by design. `[CODE]`

---

## Criterion 2 — SP1 exposes a bridge-compatible invocation surface — **GREEN via subprocess; AMBER on Python-native**

**Evidence `[WEB:2026-05-24]`:**
- **`cargo prove` CLI + `sp1-sdk` crate** automate setup, key generation, proof production, and
  verification — locally *or* via the Succinct Prover Network. This is a **stable subprocess surface**
  that maps directly onto the bridge's existing pattern (the `snarkjs groth16 fullprove` subprocess in
  `zk_sepproof_prover.py` real mode). Same shape: shell out → produce proof artifact → parse.
- **Succinct Prover Network API** is the alternative (outsource proving over HTTP) — a second, network
  integration path if local proving is too heavy.
- **No native Python bindings yet** — SP1 is Rust-first; Python support is "future / via LLVM," not
  shipping. → integration is **subprocess (CLI) or HTTP (Prover Network)**, exactly like the current
  snarkjs-subprocess approach. Acceptable; not a blocker.

**Framing note:** the Python-native AMBER is **informational, not a deficit** — no current ZK prover in
the bridge uses Python-native bindings either (snarkjs is also subprocess-based, `zk_sepproof_prover.py`
real mode). SP1 **matches the existing pattern**; it does not introduce a new integration deficit.

**Hard version fact (plan around it):** **SP1 v5 was deprecated on the Prover Network 2026-05-19; v6 is
the current target.** Any SP1 work must pin **v6+**. The toolchain is a moving target — version-pin
explicitly. `[WEB:2026-05-24]`

Sources: `https://github.com/succinctlabs/sp1`, `https://docs.succinct.xyz/docs/sp1/what-is-a-zkvm`
(accessed 2026-05-24).

---

## Criterion 3 — SP1 mock-mode is feasible (CI stays green without the Rust toolchain) — **GREEN**

**Evidence `[CODE]`:** the dual-mode convention is **universal** and explicitly designed for "boot
before artifacts exist." `zk_sepproof_prover.py:89-107` — `_artifacts_available()` returns False →
mock mode "silently selected — no error raised … same pattern PITLProver uses; lets the bridge boot
cleanly before the trusted setup ceremony runs." `is_mock` flag on the result dataclass
(`zk_sepproof_prover.py:128`); module-level `ZKSEP_ARTIFACTS_AVAILABLE` (line 107) lets callers branch.

**Assessment `[DESIGN]`:** an `zk_sp1_prover.py` replicates this exactly — mock mode when the SP1 ELF /
proving key / toolchain is absent; structural mock proof for CI round-trip tests. Real SP1 proving
(cargo prove + Rust toolchain, or Prover Network) is heavy → gate it out of CI behind the
mock-default + a `@pytest.mark`-style marker, the same way hardware tests and the current real-mode ZK
tests are gated (Hard Rule: heavy deps excluded from CI). **CI green is preserved by construction.**

---

## Criterion 4 — Proof artifact fits the anchor pattern with ZERO FROZEN break — **GREEN**

**Evidence `[CODE]`:** the on-chain anchor family — `chain.py:3171` `anchor_biometric_snapshot` and its
siblings (`anchor_corpus_snapshot` 2785, `anchor_zkba_artifact` 3060, `anchor_listing_commitment` 3274,
`anchor_pda_attestation` 3510, …) — all anchor a **32-byte commitment** via the AdjudicationRegistry
`record_adjudication` (2702) sourceType-attribution pattern. **The full proof is NOT stored on-chain —
only a 32-byte commitment.** Therefore proof *size/format* is irrelevant to the anchor; an SP1 proof
(whatever its size/mode) anchors via the same 32-byte commitment.

**FROZEN wire formats — none touched `[DESIGN]`:**
- **228-byte PoAC record** — untouched (④/D2 is the ZK-proof layer, not the record; Hard Rule intact).
- **256-byte Groth16 proof wire format** (`zk_sepproof_prover.py:72` `PROOF_SIZE=256`) — SP1 introduces
  a **NEW** proof format *alongside* it; the v1 256-byte format is not modified.
- **BIOMETRIC-SNAPSHOT-v1** (26-byte tag), **448-byte W3bstream** wire format — additive new prover
  reuses or parallels these; does not alter them.

An SP1 verifier is a new contract (Criterion 1 self-correction), so the on-chain surface is additive,
not a modification. **No FROZEN break on any axis.**

---

## What 14a does NOT cover (scope honesty)

- **On-chain VERIFY economics/PQ (D4) is out of scope.** 14a validates that the **bridge can produce +
  locally-verify** SP1 proofs through the established seam. Whether IoTeX verifies an SP1 proof cheaply
  *and* end-to-end-PQ is **D4/D5** (the app-layer STARK-verify-reuse question), separate and still open.
  14a's GREEN is about **bridge integration**, not on-chain verification economics.
- **The ultimate "seamless" proof is 14b's produce-and-verify slice.** 14a shows nothing in the
  architecture *blocks* it and the path is the proven additive convention. It does not itself run SP1.

---

## Recommendation (for operator decision — not resolved here)

**Gate result: PASS (GREEN).** Evidence supports that SP1 integrates via the established additive
prover-module convention with no FROZEN break and a CI-safe mock-mode. The operator's precondition for
14b ("substantial evidence aligns") is **met at the architectural level.**

If 14b fires, the lowest-risk first slice (converts assertion → evidence):
1. Add `bridge/vapi_bridge/zk_sp1_prover.py` in **mock-mode only** following the 6-prover convention
   (no toolchain yet) → proves the module/call-site wiring is truly additive, CI stays green.
2. Then a **single minimal SP1 guest** (e.g. re-implement the ZK-SEPPROOF Mahalanobis+threshold check
   — apples-to-apples vs the existing Groth16 circuit) targeting **SP1 v6**, **produce + locally-verify
   off-chain** via `cargo prove` subprocess.
3. Circuit choice (ZK-SEPPROOF benchmark vs Feature-Extraction stress) and **D6** (composite-sig
   in-circuit gadget) resolve inside 14b step 2+.

**Toolchain/ops facts to carry into 14b:** Rust toolchain + `cargo prove` (heavier than circom/snarkjs;
local vs Prover-Network is a cost/ops choice tied to D3); pin **SP1 v6+**; gate real proving out of CI.

---

## Proposal-summary for V-check

> D2 seamlessness pre-validation (Phase 14a): a read-only + docs + design findings note assessing
> whether SP1 integrates seamlessly with QorTroller's established bridge before committing to the D2
> circuit-build arc. Four criteria assessed against actual bridge code (6 coexisting prover modules,
> dual-mode mock convention, 32-byte-commitment anchor pattern, per-verifier-contract coexistence) and
> SP1 docs (cargo prove CLI subprocess surface; no Python bindings; target v6). Verdict GREEN — no
> architectural blockers; integration is the proven additive prover-module convention; no FROZEN
> wire-format break (228-byte PoAC record untouched; SP1 proof is a new format alongside the 256-byte
> Groth16 one). On-chain verify economics (D4) explicitly out of scope. No code, no prototype, no
> toolchain installed; no contract change, no wallet/on-chain action. Documentation artifact.
