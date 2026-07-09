# VHR-PROOF-1 — First Real Groth16 Replay Proof Minted + Verified (2026-07-08)

**The last dormant arc awoke.** From this session's genesis (Arc 5, 2026-05-29) the VHR
replay-proof pipeline shipped end-to-end with `DeferredProver` as an honest stand-in —
"no fake proofs until the ceremony lands + the circomlibjs helper is wired." Both
landed (A4: ceremonies verified-complete-prior); today the real prover ran for the first
time and produced a cryptographically valid proof.

## What ran

`Groth16Prover.prove()` — the real snarkjs-backed path — over a matrix labeled with
Match 17's session_id, humanity 0.92 vs threshold 0.70:

| Output | Value |
|---|---|
| `deferred_reason` | **None** (NOT deferred — real proof) |
| `proof_bytes` | **256 bytes** (snarkjs Groth16 wire format) |
| `replay_proof_token` | `0x22f3c60d663e197cb482c96991856228000e95cd3b2a4a5515283dfdf9c30f8b` |
| `sanitized_trace_root` | `1174051900095972775869022261643854936478…` (circomlibjs Poseidon) |
| `vhp_commitment` | `1552798019944416507607423836266614620782…` (Poseidon(2)(tokenId, nonce)) |

**Cryptographic close-out: `snarkjs groth16 verify VK public proof` → `snarkJS: OK!`**
The proof verifies against the ceremony verification key. The full circomlibjs → snarkjs
fullprove → verify chain works on this Windows rig.

## Both rails held

- **Positive:** humanity 0.92 ≥ 0.70 → proof mints + verifies.
- **Negative (the honesty rail):** humanity 0.50 < 0.70 → `compute_h_gap` pre-flight
  raises, prover returns `deferred_reason="humanity floor not cleared"`, `proof_bytes`
  empty. **A sub-threshold session cannot mint a proof** — the C1 in-circuit floor
  (Num2Bits(10) on h_gap) is enforced Python-side before any subprocess, and would fail
  in-circuit too. No fake proof is ever producible for a session that didn't clear the
  consent-manifest humanity floor.

## Honest scope

- The proven matrix is an **8-tick synthetic stand-in** carrying M17's session_id, NOT
  M17's actual sanitized replay matrix (that requires the Arc 5 pre-processor run over
  `bridge_match17.db`, a separate wiring step). This demonstration proves the PROVER and
  the cryptography are real and correct; a full M17-matrix proof is the natural next
  increment (VHR-PROOF-2).
- `sanitizedTraceRoot` is a PUBLIC input, not constrained in-circuit (§C3 comment) — its
  integrity vs the published matrix is checked off-chain by recomputation. The
  `compute_inputs_replay_proof.js` helper defines the canonical VAPI-VHR-MATRIX-v1 sponge;
  the verifier recomputes it identically.
- Nothing deployed, nothing anchored, 0 IOTX. The v1 + v2 verifiers are already on-chain
  (A4); submitting a proof to them is an operator-gated, IOTX-spending step (not taken).

## What this closes

- **VHR-PROOF-1 CLOSED** — DeferredProver is no longer the only working prover; the real
  one produces verifiable Groth16 proofs. Arc 5's genesis promise ("no fake proofs until
  ready") is discharged honestly: it was deferred until real, and now it's real.
- The data-economy path gains its cryptographic core: a listable, zero-knowledge proof
  that a session cleared the humanity floor while holding a valid VHP — without revealing
  the token, nonce, or raw replay.

## Files
- Verified proof + public inputs: `audits/vhr_proof1_demo/proof_m17.json` + `public_m17.json`
- Prover: `bridge/vapi_bridge/replay_proof_pipeline/groth16_prover.py` (pre-existing, now exercised)
- Helper: `.../zk_artifacts/compute_inputs_replay_proof.js` (circomlibjs Poseidon, VAPI-VHR-MATRIX-v1)
- Ceremony zkey/vkey/wasm: `.../zk_artifacts/` (from the verified 2026-05-30/06-25 ceremonies)
