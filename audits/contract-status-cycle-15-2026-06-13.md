# QorTroller contract-status audit — F-CYCLE10-1 Option (b)

- Timestamp: `2026-06-13T04:20:55Z`
- Total addr-shaped non-meta keys: 66
- ACTIVE: 58
- SUPERSEDED (explicit): 3
- DEPRECATED-INFERRED (versioning heuristic): 5

## Non-ACTIVE records (the interesting ones)

| Key | Address | Status | Reason | Superseded by |
|-----|---------|--------|--------|---------------|
| TournamentGate | `0xea9a3f30474a75f90D3B66A496907fB34cADd7C1` | DEPRECATED-INFERRED | sibling 'TournamentGateV2' exists with higher version suffix (heuristic, not explicit) | TournamentGateV2 |
| TournamentGateV2 | `0x6369C96BB98E234Df9E1a4d72843dE8C56fCe786` | DEPRECATED-INFERRED | sibling 'TournamentGateV3' exists with higher version suffix (heuristic, not explicit) | TournamentGateV3 |
| PITLSessionRegistry | `0x8da0A497234C57914a46279A8F938C07D3Eb5f12` | DEPRECATED-INFERRED | sibling 'PITLSessionRegistryV2' exists with higher version suffix (heuristic, not explicit) | PITLSessionRegistryV2 |
| PitlSessionProofVerifier | `0x07D3ca1548678410edC505406f022399920d4072` | DEPRECATED-INFERRED | sibling 'PitlSessionProofVerifierV2' exists with higher version suffix (heuristic, not explicit) | PitlSessionProofVerifierV2 |
| VAPIProtocolLens | `0x32Bf1A01a0a2629955A3Fd5ce74c0571DAd7C989` | DEPRECATED-INFERRED | sibling 'VAPIProtocolLens_v2' exists with higher version suffix (heuristic, not explicit) | VAPIProtocolLens_v2 |
| VAPIProtocolLens_v1_superseded | `0x1972bf756aFE0FFCfaF9842e2FbBb2B084352EAf` | SUPERSEDED | key contains '_superseded' substring (explicit marker) | — |
| SeparationRatioRegistry | `0xc88eDc0a07F25bC5c499d1b132Ce2Dd8d45BEC1f` | SUPERSEDED | meta-key '_separationratioregistry_superseded_note' marks supersession | — |
| SeparationRatioRegistry_superseded | `0xB39CeE732cf91c93539Bd064D9426642a095a026` | SUPERSEDED | key contains '_superseded' substring (explicit marker) | — |

## All ACTIVE keys

| Key | Address |
|-----|---------|
| TieredDeviceRegistry | `0x73753E916eEE0DAfEc1f6a16d98d4E4aFf9E8230` |
| PoACVerifier | `0x26178AD95DB507f0D298fAAFC19752fC86166c6C` |
| BountyMarket | `0x6B288EfbC26cDBd02d1e3735299274597242315E` |
| SkillOracle | `0xABA74481066bAdC72c6f51Fb1af3E0eD6BfbCe50` |
| ProgressAttestation | `0x822be18aC92520A7fdb4887f10BfB340edEb8AB1` |
| TeamProofAggregator | `0x0b4227CE704Ca780a9CeDD3Ab0F277E81e0008F4` |
| PHGRegistry | `0x70a35469A289949fce43d70886A27655a7033321` |
| IdentityContinuityRegistry | `0x980A28f6907f38558D946C1D0C18844c60d44ba4` |
| PHGCredential | `0x0Af852f5850f7bf50151BbBC14905f3a160f7F27` |
| FederatedThreatRegistry | `0xe837FaB5B441b37E2bA215FA14Ee11427DCd0f24` |
| TournamentGateV3 | `0x6fEe9F6fB24A3e6cEF93f0cA5cA9875625c5D4Ef` |
| VAPIioIDRegistry | `0xF7885B588718b891B2234477D031607da4a7ACfe` |
| PITLTournamentPassport | `0xa72454748A1E272Bf084bEfBd0A0fC5516685AEC` |
| TournamentPassportVerifier | `0xb95C0561EF2b1081F07B6Cd3c37f4C9dd3caa112` |
| PITLSessionRegistryV2 | `0xAfb544c09B6dec303740F2d218d6C784eB064ec3` |
| PitlSessionProofVerifierV2 | `0x5f4e30EB180Bb87c5Ad65623fA3566f838db8a38` |
| RulingRegistry | `0xa3A2356C90E642a7c510d0C726EC515EA720c621` |
| CeremonyRegistry | `0x739B5fae312834bA2a7e44525bA5f54853C5672f` |
| DataSovereigntyRegistry | `0xd928d95321Fff9b9003331082A8F6b75114793C9` |
| HumanityOracle | `0x84069312B5363Ef8ce6d1e2e312C4A1a8596a45d` |
| RulingOracle | `0xfA15e1f48B0BaC624C31E8F730713C3653Ee6E21` |
| PassportOracle | `0x7f8cE7B689Ad9bEC5D22C9F8Dc245eBD078e0917` |
| VAPIRewardDistributor | `0x8ae8B577684bf328B24C7a600D3Ba29A39d661A5` |
| VAPIDataMarketplace | `0x15D2Ac6d5802Bb8cBb8d3E35648385a7821630cC` |
| VAPIGovernanceTimelock | `0x0a44Ff57D2aeA4Ee64Cdd8FC854306a887670a34` |
| VAPIProtocolLens_v2 | `0x32Bf1A01a0a2629955A3Fd5ce74c0571DAd7C989` |
| GateAttestationAnchor | `0xA39d00D3FF8C579840Fa02C01Adf06162630a449` |
| VAPIToken | `0xaDD7C15f7C99961Bf09adE43e3f80E73aB1B2BBc` |
| VAPIOperatorRegistry | `0x48Ae65Bdf28f7C1a3B4A8e7D81cD7A1bA6E1BdCe` |
| VAPIHardwareCertRegistry | `0x1031b7840184D6c8f0EA03F051970578C3c874C2` |
| VAPIGSRRegistry | `0x1661AD0F084844ad15D5Bf56b2B6d1134Df4c2f2` |
| VAPIVerifiedHumanProof | `0xD3B2E259A4B69EF08e263e3A57B2507B7eac3dcF` |
| VAPIVerifiedHumanProofBridge | `0xEb0b6a62b0cd765878250eae3CfFE4a3b67Dd8D8` |
| AdjudicationRegistry | `0x44CF981f46a52ADE56476Ce894255954a7776fb4` |
| VAPIDualPrimitiveGate | `0xd7b1465Aad8F815C67b24681c9c022CED24FB876` |
| ProtocolCoherenceRegistry | `0xfAfe4E8BEE45be22836b90D542045510dDd927Dd` |
| VAPIBiometricGovernance | `0x06782293F1CFC1AA30C0Baee0437c2B336796A00` |
| VHPExpiresAtAdapter | `0x086a660fe457633063299F3BE9661B86c43aF053` |
| VAPIConsentRegistry | `0xA82dB0eF0bF7D15b6400EDd4A09C0D4338C948dA` |
| AgentRegistry | `0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4` |
| AgentScope | `0xc694692a69bbf1cDAda87d5bc43D345C4579FF13` |
| AuditLog | `0xb7059391323eACFcb3d150a7EBFd80275a77E25F` |
| AgentSlashing | `0x0994666D0a307968BAA3f38B59756187164155e0` |
| AgentAdjudicationRegistry | `0x4767c5Ab7ed705E810903BE764fa4090B639C10A` |
| VAPIOperatorAgentNFT | `0xa0CDD2B3E292c56030185c66a3d423278A4c467b` |
| VAPIDataMarketplaceListings | `0x78Df84Cc512EdCaC0e58a03e4852627E2F62E3bC` |
| Groth16VerifierZKSepProof | `0xD63EEf1372Cb496071bf963bEE395F7e0A3f2Ab6` |
| ZKSepProofVerifier | `0xd51a21E234a800a6621f4c23a8fcA44e3bF01002` |
| VAPIPoEPRegistry | `0x4Dcfa11d7a4d661065784Acbb1AeCC2f124C7B38` |
| VAPIManufacturerDeviceRegistry | `0x2e5B5FB110890f498e289E3045d0f54Cfb0F91b0` |
| VAPIBuyerRegistry | `0x3742189eBDC09B115FA7e841C884247E9856130B` |
| VAPISwarmOperatorGate | `0x969c0F1EFb28504a95Acf14331A59FBCb2944F98` |
| CeremonyAuditRegistry | `0xb9164E6d74Dde1508df2a39b01d3702ACC8230C2` |
| VHPReenrollmentBadge | `0x42E7A25d0E5667BBae45e5cF33a6e2CC6E42d45C` |
| Groth16VerifierVAPIReplayProof | `0xcE56404CB2e49C3D68ABc72d2941A508Cbe75608` |
| VAPIReplayProofVerifier | `0x5182372d1D033db0c9230843DFDE606733D5F91B` |
| VAPIBuyerCategoryVerifier | `0x7EEc6B7Eb843532227528F63a0bC95D6cc537E53` |
| VAPIConsentManifestRegistry | `0x5F7c8068D0e61818FCD613D47e68a9Ea906a2743` |

## Honesty rail

DEPRECATED-INFERRED is a versioning heuristic, NOT a fact. Operator confirms by checking actual contract wiring (bridge/.env, chain.py imports, SDK consumers). A future v0.2 of this auditor could cross-check those sources for higher confidence.
