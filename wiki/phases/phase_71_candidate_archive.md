# Archived from CLAUDE.md L628-L658 (2026-05-18 curation pass 2)

Preserved verbatim for historical reference. Live state in CLAUDE.md inline.

---

## Phase 71 — Candidate Phases (PHASE_ADVANCE Output, 2026-03-19)

After Phase 70 completes, next phases in priority order. User decision required before starting any.

| Rank | Phase | Name | Priority | Blocks |
|------|-------|------|----------|--------|
| P1 (Recommended) | 71 | Deploy Phases 69+70 + Security Audit | P1 | All on-chain functionality |
| P2 | 72 | PHGCredential SafeMultiSig Governance | P1 | Tournament Condition 3 |
| P3 | 73 | CI/CD GitHub Actions + SessionAdjudicator Live Validation | P1 | Production readiness gate |

**Phase 71 detail (deploy + audit):**
- npx hardhat run scripts/deploy-phase69.js --network iotex_testnet (~0.35 IOTX, 6 contracts)
- npx hardhat run scripts/deploy-phase70.js --network iotex_testnet (~0.13 IOTX, 2 contracts)
- Produce docs/security-audit-phase-70.md (VAPIGovernanceTimelock + VAPIProtocolLens + agent wiring + tools #41-45)
- Fix any CRITICAL/HIGH findings inline
- Update deployed-addresses.json + bridge/.env.testnet with 8 new addresses
- ~0 new tests (deploy + audit only, no new code)

**Phase 72 detail (PHGCredential SafeMultiSig):**
- SafeMultiSig.sol: 2-of-3 confirmations for suspend/reinstate on PHGCredential
- chain.py: propose_suspension() → confirm_suspension() → execute_suspension() flow
- Config: safe_signers[3], safe_threshold=2
- +6 Hardhat + 4 bridge tests
- Closes Tournament Condition 3 (governance hardened)

**Phase 73 detail (CI/CD + Live Adjudication):**
- GitHub Actions: bridge-tests.yml + hardhat-tests.yml + sdk-tests.yml + yaml-lint.yml
- Matrix: Python 3.11/3.12/3.13, Node 18/20
- POST /agent/config AGENT_DRY_RUN=false: document 100 validated sessions threshold
- +0 new tests (CI config only)

