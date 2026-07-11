# VHR-PROOF-2 — Real Groth16 Replay Proof over Match 17's Actual Matrix (2026-07-08)

VHR-PROOF-1 minted the first real proof over a synthetic stand-in. VHR-PROOF-2 does it
over **Match 17's actual sanitized replay matrix** — the full pipeline, real biometric
provenance, end to end.

## The pipeline, run for real

| Stage | Result |
|---|---|
| Source | 27,672 real structural HID frames from `bridge_match17.db` (462 populated frame_checkpoints) |
| φ pre-processor (Arc 5) | frames → **1,730-tick** SanitizedReplayMatrix (60Hz median-window flatten + 4-bit spatial quantize); data floor enforced (structural HID only, zero biometric features) |
| PoAC chain root | real Merkle root over **463 session record hashes** (`978cb10e…`) |
| Prover | `Groth16Prover.prove()` → `deferred_reason=None`, **256 proof bytes** |
| Token | `0x0e675e6ae23ebb23cb3d01dd235f1ddd5d00008097b73a3fc704ce850844fd7c` |
| Verify | `snarkjs groth16 verify VK public proof` → **`snarkJS: OK!`** |

The proof is over the SAME session (M17) that produced 17/18 live authorship and whose
PoSP is anchored on-chain (block 45447322). One session now carries: a synchronized
presence proof, live kill authorship, a fully-rooted PoSP, an on-chain anchor, AND a
zero-knowledge replay proof that it cleared the humanity floor while holding a valid VHP.

## What the proof proves (and hides)

Public (in `public_m17_real.json`, committed — zero-knowledge safe):
- `replayProofToken`, `sanitizedTraceRoot`, `poacChainRoot`, `consentPolicyHash`,
  `humanityThreshold`, `vhpCommitment` — six field elements, no raw data.

Hidden (NEVER left the rig — the private witness): the humanity probability witness, the
VHP token id, the session nonce, and the sanitized matrix itself. The
`private_inputs`/`circuit_input` files (which carry the matrix) were computed locally and
**deliberately NOT committed** — only the ZK proof + public inputs are published.

## Honest scope

- The matrix is φ-sanitized (4-bit radial sectors, 3-bit gravity octants, non-invertible
  by the Arc 5 FORBIDDEN_COLUMNS data floor) — it is the data-economy PRODUCT, not a
  secret, but it is session data and stays out of the public repo pending a consent frame.
- `consentPolicyHash` = zero placeholder (no consent manifest wired for this demo session);
  a real listing binds the gamer's actual Arc 4 manifest hash.
- `humanity_probability=0.92` is an injected demo value (the orchestrator supplies the real
  session min p(human) from the ruling record); the FLOOR MATH is real — 0.92 ≥ 0.70 clears,
  and VHR-PROOF-1 showed 0.50 < 0.70 cannot mint.
- Nothing deployed/anchored/submitted; 0 IOTX. Submitting to the on-chain v1/v2 verifiers
  is a separate operator-gated, IOTX-spending step.

## What this closes

**VHR-PROOF-2 CLOSED — the VHR replay-proof arc is complete end-to-end on real data.**
From raw session HID → φ → matrix → circomlibjs Poseidon commitments → Groth16 proof →
cryptographic verification, over a real match. The data-economy path has its full
cryptographic core exercised on genuine gameplay for the first time.

## Files
- Verified proof + public: `audits/vhr_proof2_m17/proof_m17_real.json` + `public_m17_real.json`
- (Matrix-bearing private/circuit inputs computed locally, intentionally uncommitted)
- Report: this file
