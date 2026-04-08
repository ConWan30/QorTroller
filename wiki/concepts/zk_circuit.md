# CONCEPT: ZK Circuit — Groth16 Biometric Commitment

[VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

## FROZEN — DO NOT MODIFY

The ZK circuit parameters are cryptographically sealed by the MPC ceremony
anchored to IoTeX block #41723255.

## Circuit Parameters [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

| Parameter | Value | Status |
|-----------|-------|--------|
| Proving system | Groth16 | FROZEN |
| Curve | BN254 | FROZEN |
| Constraints | ~1,820 | FROZEN |
| Powers-of-tau | 2^11 | FROZEN |
| nPublic | **5** | FROZEN |
| Ceremony contributors | 3 | FROZEN |
| Ceremony beacon | IoTeX block #41723255 | FROZEN |

## Feature Commitment Formula [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

```
featureCommitment = Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody)
```

- Poseidon hash function, 8-input variant
- Inputs: scaled biometric features [0..6] plus inferenceCodeFromBody
- Circuit constraint C3: `inferenceResult === inferenceCodeFromBody`
- This binds the ZK proof to the actual L3/L4 inference result in the PoAC body

## Constraint C3 [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

```
C3: inferenceResult === inferenceCodeFromBody
```

Prevents a prover from generating a valid ZK proof with a different inference
result than what is recorded in the 164-byte PoAC body. The commitment is
cryptographically bound to the on-chain ruling.

## circuitId Derivation [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

```python
circuitId = sha3_256(circuitName.encode())
```

Must be consistent across three locations:
1. `bridge/vapi_bridge/chain.py`
2. `contracts/scripts/run-mpc-ceremony.js`
3. `sdk/vapi_sdk.py` — `verify_ceremony_integrity()`

Any divergence between these three is a critical integrity failure.

## MPC Ceremony Status [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

- 3 circuits × 3 contributors
- Beacon: IoTeX block #41723255
- `verifyCeremony()` on `CeremonyRegistry.sol`: PASSES
- `CeremonyRegistry.sol` deployed LIVE on testnet

## Deployed Contracts [VAPI:Phase166:VAPI_INVARIANTS.md:FROZEN]

| Contract | Address |
|----------|---------|
| PITLSessionRegistry | `0x8da0A497234C57914a46279A8F938C07D3Eb5f12` |
| PitlSessionProofVerifier | `0x07D3ca1548678410edC505406f022399920d4072` |
| CeremonyRegistry | `0x739B5fae312834bA2a7e44525bA5f54853C5672f` |

## Related Pages

- [[poac_wire_format]]
- [[l4_thresholds]]
- [[agent_fleet]]
