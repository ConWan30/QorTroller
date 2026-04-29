# Phase O0 Pause Point — 2026-04-29

**Pause character**: Operator-initiated. Not blocked on technical issue.
**Phase O0 source-and-tests work**: COMPLETE.
**Section 6.2 GitHub Apps registration**: COMPLETE.
**Remaining Phase O0 work**: gated on wallet refill + KMS provider access.

The protocol's state at this pause is stable, defensible, and synchronized
with `origin/main`. This document captures the pause in a form that survives
Claude Code session disruption, so the next session can resume cleanly
without context loss.

---

## Phase O0 Implementation Arc — commit roster

### Design phase (5 commits)

| Commit | Subject |
|--------|---------|
| `30181951` | Pass 1 — three architectural conflicts resolved; scope-class agent authorization confirmed |
| `4d7cb9d6` | Verification (V1-V11 findings against architecture document) |
| `6751bf9a` | Pass 2A — four precursor work findings resolved |
| `fe4232e3` | Pass 2B — V11 conceptual alignment resolved to Path 3 (PHYSICAL_DATA_ATTESTATION v1 as seventh FROZEN-v1 primitive) |
| `b9ddeeb2` | Pass 2C — implementation plan with all eleven operator decisions resolved; Phase O0 unblocked for implementation |

### Implementation phase

#### Stream 1 — foundation (4 commits, pre-conversation)

| Commit | Subject |
|--------|---------|
| `fdee8092` | refactor: lane reorganization for Operator series Phase O0 |
| `cdfa0ae6` | feat: CODEOWNERS path-based lane discipline |
| `90c410d5` | fix: CODEOWNERS catch-all positioning for last-match-wins semantics |
| `b13e7840` | feat: path-scope gate script and workflow |

Note: the operator's earlier framing referenced "Stream 1 (3 sessions)" — the actual
git history contains 4 commits because the CODEOWNERS work needed a small fix-up
commit (`90c410d5`) to correct catch-all positioning. Sessions = 3 (lane reorg /
CODEOWNERS / path-scope gate); commits = 4.

#### Stream 2-prep — five Operator-series contracts (5 commits)

| Commit | Subject | Origin |
|--------|---------|--------|
| `b063718e` | AgentRegistry contract source + tests | pre-conversation |
| `d1453f84` | AgentScope contract source + tests | conversation |
| `6a1b30a8` | AuditLog contract source + tests | conversation |
| `447fb8d4` | AgentSlashing contract source + tests | conversation |
| `7a4ae0d8` | AgentAdjudicationRegistry contract source + tests | conversation |

All five compile and pass Hardhat unit tests. Stream 2-deploy execution against
IoTeX testnet is documented in `docs/phase-o0-stream-2-deploy-dryrun.md`
(commit `b261b546`).

#### Stream 3-prep — FROZEN-v1 primitives + PV-CI freeze (3 commits)

| Commit | Subject |
|--------|---------|
| `a7b61160` | AGENT_COMMIT v1 bridge module (sixth FROZEN-v1 primitive) |
| `412a6f0e` | PHYSICAL_DATA_ATTESTATION v1 bridge module (seventh and final FROZEN-v1 primitive) |
| `f692a48e` | PV-CI gate-extension freeze ceremony for INV-AGENT-COMMIT-001/002 + INV-PDA-001/002 (allowlist 28 → 32) |

#### Stream 4-prep — agent endpoint authentication (2 commits)

| Commit | Subject |
|--------|---------|
| `038740d2` | OAuth 2.1 client credentials issuer + HMAC request signing primitives |
| `a32c9d48` | agent_auth.py FastAPI dependency + five read-only `/agent/agent-*` endpoints |

#### Stream 5-prep — agent identity infrastructure (2 commits)

| Commit | Subject |
|--------|---------|
| `1457dec2` | Agent definition `.md` files + DID document JSON-LD templates |
| `7ad1b5ad` | IPFS pinning script (Pinata) — final source-and-tests commit |

#### Verification (1 commit)

| Commit | Subject |
|--------|---------|
| `b261b546` | Phase O0 Stream 2-Deploy: local Hardhat dry-run runbook |

### Total

- **Source-and-tests commits**: 16 (4 Stream 1 + 5 Stream 2-prep + 3 Stream 3-prep + 2 Stream 4-prep + 2 Stream 5-prep)
- **Verification commits**: 1 (dry-run runbook)
- **Phase O0 implementation total**: 17 commits
- **Plus design phase**: 5 design commits (Pass 1, verification, Pass 2A, 2B, 2C)
- **All commits public**: synchronized with `origin/main` HEAD `b261b546ff0eeb415b5a08f1aac38678143a6270`

---

## Section 6.2 — GitHub Apps Registration COMPLETE

Both apps registered on GitHub:

- **vapi-anchor-sentry** — Anchor Sentry (cryptographic event monitoring + provenance)
- **vapi-guardian** — Guardian (operational health + protocol stewardship)

Ten artifacts stored at canonical bridge locations as **operator-managed state**
(NOT committed; gitignored):

### bridge/.env additions (10 keys)

```
VAPI_ANCHOR_SENTRY_APP_ID
VAPI_ANCHOR_SENTRY_CLIENT_ID
VAPI_ANCHOR_SENTRY_CLIENT_SECRET
VAPI_ANCHOR_SENTRY_INSTALLATION_ID
VAPI_ANCHOR_SENTRY_PEM_PATH=bridge/secrets/vapi-anchor-sentry.pem

VAPI_GUARDIAN_APP_ID
VAPI_GUARDIAN_CLIENT_ID
VAPI_GUARDIAN_CLIENT_SECRET
VAPI_GUARDIAN_INSTALLATION_ID
VAPI_GUARDIAN_PEM_PATH=bridge/secrets/vapi-guardian.pem
```

### bridge/secrets/ (NEW directory)

| File | Size | Markers | Permissions |
|------|------|---------|-------------|
| `vapi-anchor-sentry.pem` | 1706 bytes | BEGIN/END PRIVATE KEY present | mode 600 (best-effort) |
| `vapi-guardian.pem`      | 1706 bytes | BEGIN/END PRIVATE KEY present | mode 600 (best-effort) |

### .gitignore protections (verified via `git check-ignore`)

| Path | Ignored by |
|------|------------|
| `bridge/.env` | `.gitignore:21` (`.env` pattern) |
| `bridge/secrets/*.pem` | `.gitignore:119` (`bridge/secrets/`) + `.gitignore:77` (`*.pem`) defense-in-depth |

The credential transfer file at `C:\Users\Contr\.claude\VAPI AGENTS APPS.txt` was
securely overwritten + unlinked after credentials landed in `bridge/.env` +
`bridge/secrets/`. No transient extraction artifacts remain at `.claude/`.

---

## Remaining Phase O0 Work — dependency graph

```
                                       ┌─────────────────┐
  ┌─── Stream 2-deploy ────────────────┤                 │
  │    (gated on wallet ≥3 IOTX)       │  Section 6.4    │   Section 8
  │                                    │  agent          │   exit criteria
  │                                    │  registration   │── verification
  │    Section 6.3                     │                 │   (24 testable)
  └─── KMS provisioning ───────────────┤                 │
       (gated on KMS provider access)  └─────────────────┘
       (independent of wallet refill)
```

| Activity | Gating constraint | Estimated effort |
|----------|-------------------|------------------|
| **Stream 2-deploy** | Wallet ≥3 IOTX (5 IOTX target per Pass 2A V8); current 0.5525 IOTX | 5-command sweep, ~10 min once unblocked |
| **Section 6.3 KMS provisioning** | Operator KMS provider access (AWS preferred per Pass 2C Q2) | 30-60 min, AWS console + CLI |
| **Section 6.4 agent registration** | Stream 2-deploy + Section 6.3 both complete | 1-2 hours, multi-step orchestration (ioID DID minting, ERC-6551 TBA binding, IPFS pinning of populated DID documents using `bridge/vapi_bridge/ipfs_pinning.py`, AgentRegistry.registerAgent calls) |
| **Section 8 exit criteria verification** | All prior Phase O0 work | 1-2 hours, 24 testable criteria from Pass 2C Section 8 |

---

## Path Forward on Resumption

1. **Stream 2-deploy** triggers when wallet refills to ≥3 IOTX (target 5 IOTX). Execute
   the five-command sweep from `docs/phase-o0-stream-2-deploy-dryrun.md` against
   IoTeX testnet (chain ID 4690). Each script self-aborts on insufficient balance, so
   the wallet check happens automatically per deploy.

2. **Section 6.3 KMS provisioning** runs whenever operator has provider access. AWS KMS
   per Pass 2C Q2: generate two `KeySpec=ECC_NIST_P256` keys (`alias/vapi-anchor-sentry-signing`
   and `alias/vapi-guardian-signing`), configure key policies (only bridge IAM role can
   `kms:Sign`), export public keys (one-time post-creation). Public keys feed into
   ioID DID minting in Section 6.4. Independent of wallet refill — runnable any time.

3. **Section 6.4 agent registration** follows after both Section 6.3 + Stream 2-deploy
   complete. Multi-step orchestration:
   - Register agent project on ProjectRegistry (per agent)
   - Mint ioID DID via ioIDRegistry (per agent)
   - Bind ERC-6551 TBA via the ERC-6551 Registry (per agent)
   - Populate the DID document templates from `agents/did_templates/` with real
     addresses + KMS public keys + ISO-8601 createdAt
   - Pin populated DID documents to IPFS via `bridge/vapi_bridge/ipfs_pinning.py`'s
     `PinataClient.pin_did_document()` (requires `PINATA_JWT` env var)
   - Call `AgentRegistry.registerAgent()` for each agent with the Q9 agentId encoding
     (`keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address))`)
   - Set initial AgentScope.scopeRoot per agent (Phase O0 ships `bytes32(0)` —
     "no operational authority" per Pass 2C Section 7)

4. **Section 8 exit criteria verification** closes Phase O0. Cross-check the 24 testable
   criteria documented in Pass 2C Section 8 against the deployed state.

---

## First-Session Resumption Checklist

Before starting the next Phase O0 session, re-verify:

1. **Wallet balance** via `eth_getBalance` against `https://babel-api.testnet.iotex.io`
   for `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`:
   ```bash
   curl -sX POST https://babel-api.testnet.iotex.io \
     -H "Content-Type: application/json" \
     --data '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692","latest"],"id":1}'
   ```
   If balance ≥3 IOTX (`0x29A2241AF62C0000` in hex = 3 × 10^18 wei), Stream 2-deploy is unblocked.

2. **Bridge pytest baseline** matches the regression-clean state captured here:
   ```bash
   python -m pytest bridge/tests/ --ignore=bridge/tests/test_e2e_simulation.py -m "not hardware" -q
   ```
   Expected: **2692 passing / 148 failing** (per Stream 5-prep Session 2 async regression
   completing in 1:50:16 on 2026-04-28). The 148 failures are pre-existing baseline
   noise predating Phase O0 (Phase 58 evasion-cost suite, Phase 69 curator field defaults,
   etc.) — they are NOT introduced by Phase O0 work.

3. **bridge/.env contains the ten Section 6.2 credentials**:
   ```bash
   grep -cE "^VAPI_(ANCHOR_SENTRY|GUARDIAN)_(APP_ID|CLIENT_ID|CLIENT_SECRET|INSTALLATION_ID|PEM_PATH)=" bridge/.env
   ```
   Expected output: `10`

4. **bridge/secrets/ contains both PEM files**:
   ```bash
   ls bridge/secrets/
   # Expected: vapi-anchor-sentry.pem  vapi-guardian.pem
   for f in bridge/secrets/*.pem; do
     echo "$f: $(wc -c < "$f") bytes, BEGIN=$(grep -c BEGIN "$f"), END=$(grep -c END "$f")"
   done
   # Expected: each 1706 bytes, BEGIN=1, END=1
   ```

5. **HEAD synchronized with origin/main**:
   ```bash
   git fetch origin main
   git rev-list --left-right --count origin/main...HEAD
   # Expected: 0  0
   ```

6. **Read this pause-point document** to confirm context.

---

## References

- **Design phase commits**: `30181951` (Pass 1) / `4d7cb9d6` (verification) / `6751bf9a` (Pass 2A) / `fe4232e3` (Pass 2B) / `b9ddeeb2` (Pass 2C)
- **Stream 2-deploy execution reference**: `docs/phase-o0-stream-2-deploy-dryrun.md` (commit `b261b546`)
- **AGENT_COMMIT v1 module**: `bridge/vapi_bridge/agent_commit.py` (commit `a7b61160`)
- **PHYSICAL_DATA_ATTESTATION v1 module**: `bridge/vapi_bridge/physical_data_attestation.py` (commit `412a6f0e`)
- **PV-CI invariant allowlist**: `.github/INVARIANTS_ALLOWLIST.json` (commit `f692a48e`, 32 entries with INV-AGENT-COMMIT-001/002 + INV-PDA-001/002)
- **OAuth + HMAC primitives**: `bridge/vapi_bridge/oauth_issuer.py` + `bridge/vapi_bridge/hmac_middleware.py` (commit `038740d2`)
- **agent_auth FastAPI dependency**: `bridge/vapi_bridge/agent_auth.py` (commit `a32c9d48`)
- **Agent definitions**: `.claude/agents/vapi-anchor-sentry.md` + `.claude/agents/vapi-guardian.md` (commit `1457dec2`)
- **DID templates**: `agents/did_templates/vapi-anchor-sentry.did.template.json` + `agents/did_templates/vapi-guardian.did.template.json` (commit `1457dec2`)
- **IPFS pinning client**: `bridge/vapi_bridge/ipfs_pinning.py` (commit `7ad1b5ad`)
- **Section 6.2 credential storage** (operator-managed, not committed): `bridge/.env` + `bridge/secrets/`
