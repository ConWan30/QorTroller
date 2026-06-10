# QorTroller — Disaster-Recovery Runbook

**Scope:** Total-loss recovery of the operator machine running the bridge
(`bridge.vapi_bridge.main`), the deployer wallet `0x0Cf36dB57f…`, the
Manufacturer Root CA, and the Guardian/Sentry KMS-rooted signing surface.

**Out of scope:** loss of the IoTeX testnet itself (chain-level recovery is
chain operators' problem), corruption of on-chain state (contracts are
immutable), or recovery of biometric corpus data (intentionally
ungitignored + local-only per `[CANONICAL]` privacy posture).

**Posture:** This runbook prioritizes **continuity of the existing wallet
and key material** over rebuilding under new identities. Do not rotate
keys as a recovery shortcut — every key rotation invalidates downstream
attestations on-chain and triggers per-agent re-anchoring.

---

## 0. Pre-incident operator action (do these NOW, before loss)

| Item | What | Where | Status |
|---|---|---|---|
| 1 | Back up `~/.vapi/qortroller_foundation_mfg_ca.json` (517 B) | Password manager (Bitwarden / 1Password / similar) as encrypted note **AND** encrypted USB drive **off-machine** | **CRITICAL — OPERATOR MUST CONFIRM** |
| 2 | Back up `bridge/.env` (full file, contains private key + KMS creds + GitHub OAuth secrets) | Same destinations as item 1 | **CRITICAL — OPERATOR MUST CONFIRM** |
| 3 | Back up `~/.vapi/device_*.json` + `dualshock_device_key.json` (Path A composite identity material) | Same destinations | OPERATOR MUST CONFIRM |
| 4 | Record IoTeX deployer wallet seed phrase (the one that generated `0x0Cf36dB57f…`) in offline cold storage | Hardware wallet or paper backup in safe | OPERATOR MUST CONFIRM |
| 5 | Confirm `docs/disaster-recovery-runbook.private.md` exists with: full KMS ARNs (`VAPI_KMS_GUARDIAN_ARN`, `VAPI_KMS_ANCHOR_SENTRY_ARN`), AWS account ID, off-site bridge.db backup target | Local repo (gitignored) | OPERATOR MUST CONFIRM |
| 6 | Run `python scripts/backup_store.py --verify --retain-days 30` daily (cron / Task Scheduler / manual). Backups land at `~/.vapi/backups/bridge-<unix-ts>.db` | Local machine | OPERATOR MUST CONFIRM |
| 7 | Replicate the latest `~/.vapi/backups/bridge-*.db` to off-site target weekly | Per private companion doc | OPERATOR MUST CONFIRM |

**F-DECON-3.2 / D-DECON-7 CRITICAL FINDING:** The Manufacturer Root CA
(`qortroller_foundation_mfg_ca.json`) is currently a single-copy
software-backed key on one Windows machine. CLAUDE.md acknowledges this
as "SoftwareIdentityBackend — INSECURE / DEV ONLY". Per
`path_a_arc1_complete` memory the long-term fix is rotation to a
hardware-HSM-backed CA + re-issuance of every device birth cert. That
project is months out. Item 1 is the **minimum reversible interim
mitigation**: copy a 517-byte file to two off-machine secure locations.

---

## 1. Wallet key custody

**Wallet:** `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` (bridge + deployer).

| Path | Lives at | Backup |
|---|---|---|
| `bridge/.env::BRIDGE_PRIVATE_KEY` | Operator machine `bridge/.env` | Item 2 above |
| Seed phrase | Operator-controlled cold storage | Item 4 above |
| Keystore JSON (optional, `DEPLOYER_KEY_SOURCE=keystore`) | `DEPLOYER_KEYSTORE_PATH` env points here | OPERATOR MUST CONFIRM path |

**Recovery procedure (machine lost):**

1. Provision new Windows / WSL / Linux operator machine.
2. Install Python 3.10+, Node 18+, Rust stable + `wasm32-unknown-unknown`.
3. Clone `git clone https://github.com/ConWan30/QorTroller.git` to a working dir.
4. Restore `bridge/.env` from backup (item 2). Validate `BRIDGE_PRIVATE_KEY` matches expected wallet address via:
   ```bash
   python -c "from eth_account import Account; print(Account.from_key(input('priv key: ')).address)"
   ```
   Output MUST equal `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692`.
5. Restore `~/.vapi/` from backups (items 1, 3, 6).
6. Continue to §5 (post-restore assertions).

**Never** generate a new wallet as a recovery shortcut. The chain-side
identity is bound to this address across 55+ deployed contracts.

---

## 2. Bridge SQLite DB (`~/.vapi/bridge.db`)

**Canonical location:** `~/.vapi/bridge.db` (~1.5 GB live).
**NOT canonical:** `bridge/vapi_store.db` (small dev/test fixture; orphaned).

### Backup

```bash
python scripts/backup_store.py --verify --retain-days 30
```

Uses sqlite3's online `.backup()` API — safe to run while the bridge
process holds the WAL. File-copy alternatives (cp / copy / xcopy)
**will produce a corrupt snapshot** when run against a live DB; do not
use them.

The `--verify` flag rechecks row counts on 8 representative tables
(`devices`, `records`, `ruling_validation_log`, `consent_ledger`,
`corpus_snapshot_log`, `biometric_snapshot_log`, `agent_commit_log`,
`watchdog_event_log`). File SHA-256 comparison is intentionally NOT done
— the backup API rewrites page boundaries so digests differ even when
contents match. Row count is the correct integrity signal.

### Restore

1. Stop the bridge process if running.
2. `cp ~/.vapi/backups/bridge-<unix-ts>.db ~/.vapi/bridge.db` — plain file
   copy is safe here because the DB is offline.
3. Delete stale WAL companions: `rm -f ~/.vapi/bridge.db-shm
   ~/.vapi/bridge.db-wal`.
4. Start the bridge: `python -m bridge.vapi_bridge.main`.
5. Confirm via `GET /bridge/grind-chain-status` that `chain_intact=True`.

---

## 3. AWS KMS (Guardian + Sentry HSM-rooted signing)

**Public identifiers** (operationally needed in restore commands):
- Region: see `docs/disaster-recovery-runbook.private.md` (gitignored).
- Aliases: `VAPI_KMS_GUARDIAN_ALIAS`, `VAPI_KMS_ANCHOR_SENTRY_ALIAS` (env-keyed in bridge/.env, values held in private companion doc).
- Full ARNs (`arn:aws:kms:<REGION>:<ACCOUNT>:alias/...`): private companion doc only — full ARN reveals AWS account ID.

**Recovery procedure (KMS keys intact, machine lost):**

1. Restore `bridge/.env` (contains `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, `VAPI_KMS_*_ALIAS`, `VAPI_KMS_*_ARN`).
2. Verify access: `aws kms describe-key --key-id <alias from private doc>`.
   Expected: 200 OK with key metadata.
3. Verify signing capability:
   ```bash
   python scripts/guardian_kms_sign_proof.py --dry-run
   ```
   Expected: HSM-verified signature + independent local verify both PASS.

**Recovery procedure (KMS keys ALSO lost — e.g., AWS account compromise):**

This is **not a recovery — it's a key rotation event** with on-chain
consequences. Do NOT execute without operator deliberation. The protocol
maintains the Guardian/Sentry pubkey commitments on-chain via the Cedar
bundle anchors. Rotating the underlying KMS keys requires:
1. Generating new KMS keys (new ARNs).
2. Issuing new Cedar bundle versions (e.g.,
   `guardian_o3_acting_v2.json`) with the new pubkeys.
3. Anchoring new bundles on-chain (governance event — not silent).
4. Updating `bridge/.env` to point at the new aliases.
5. Accepting that pre-rotation signatures remain verifiable (the old
   pubkey commitment is on-chain forever) but new signatures use the
   new keys.

**CRITICAL FINDING (F-DECON-3.5):** `AWS_ACCESS_KEY_ID` /
`AWS_SECRET_ACCESS_KEY` in `bridge/.env` are root-grade IAM creds. If
the `.env` file leaks, the attacker has full KMS access including
**KMS:Sign** on the Guardian + Sentry keys. Future hardening:
IAM-policy scope down to `KMS:Sign` + `KMS:GetPublicKey` on the two
specific key ARNs only.

---

## 4. GitHub App OAuth (Guardian + Sentry git-lane authority)

Guardian's audit-lane write authority on `lane://audits/**` is gated by
`github_app_oauth_tokens_valid=True` in the protocol state attestation
(see VAPI-O3-SUPERSEDE-v1 primitive). If the OAuth tokens expire or are
revoked, Guardian's autonomous KMS signing **still works** (off-chain) —
but its git-lane writes will start failing silently.

| Identifier | Location | Backup |
|---|---|---|
| `VAPI_GUARDIAN_APP_ID` | `bridge/.env` | Item 2 |
| `VAPI_GUARDIAN_INSTALLATION_ID` | `bridge/.env` | Item 2 |
| `VAPI_GUARDIAN_CLIENT_ID` / `VAPI_GUARDIAN_CLIENT_SECRET` | `bridge/.env` | Item 2 |
| `VAPI_GUARDIAN_PEM_PATH` | Points at GitHub App private key PEM | OPERATOR MUST CONFIRM PEM is backed up off-machine |
| Same for `VAPI_ANCHOR_SENTRY_*` | `bridge/.env` | Item 2 |

**Recovery:** restore `bridge/.env` + the PEM files at the paths it
references. Test: run a Guardian draft-submission cycle (per
`operator_initiative_completion_roadmap.md`); expected log line confirms
OAuth success before any chain write.

**Token-expiry recovery (no machine loss):** GitHub App OAuth installation
tokens are short-lived; the private PEM + App ID are persistent. If
tokens are denied with `401`, the bridge re-mints them automatically
from the PEM — no manual step needed unless the PEM itself was rotated
in the GitHub App settings.

---

## 5. Post-restore assertions (proves environment integrity)

After completing §§1-4 on the new machine, run these checks. ALL must
PASS or the environment is not yet restored:

| Check | Command | Expected |
|---|---|---|
| PV-CI invariant gate | `python scripts/vapi_invariant_gate.py` | `PASS - 174 invariants verified` |
| Wallet derives correctly | `python -c "from eth_account import Account; print(Account.from_key(open('bridge/.env').read().split('BRIDGE_PRIVATE_KEY=')[1].split()[0]).address)"` | `0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692` |
| Bridge DB row counts | `python scripts/backup_store.py --src ~/.vapi/bridge.db --dst /tmp/restore-check.db --verify && rm /tmp/restore-check.db` | All 8 tables match between source and copy |
| Live contract count | `python -c "import json; d=json.load(open('contracts/deployed-addresses.json')); print(len(d))"` | 55 (or current value — confirm matches expected at time of incident) |
| MFG CA round-trip | `python scripts/verify_device_cert.py <known-device-id>` | `VERDICT VALID` (cert sig OK + on-chain birthCertHash byte-match + isActive=True) |
| KMS reachable | `aws kms describe-key --key-id <guardian alias from private doc>` | 200 OK |
| GIC chain tip integrity | `curl -s http://localhost:8080/bridge/grind-chain-status \| jq .chain_intact` | `true` |
| Watchdog event chain | `curl -s http://localhost:8080/operator/watchdog-status \| jq .chain_intact` | `true` |

If any check fails, **DO NOT START GRIND** until the specific finding is
resolved. Grinding with a corrupted GIC chain back-fills the broken
state into Cedar bundle anchors — irrecoverable.

---

## 6. MCP servers + Claude Code

**MCP server config:** `vapi-mcp/server.py`, `vapi-mcp/knowledge_server.py`
in the repo. Re-provisioning is automatic on `claude code` startup —
no separate config file needed beyond the repo + claude code installation.

**Claude Code installation:** download from
https://claude.com/claude-code or via the OS package; sign in with the
operator's Anthropic account (not stored in repo).

---

## 7. Pinata / IPFS

`PINATA_JWT` in `bridge/.env` pins ZKBA + VPM artifact JSON CIDs. If
the JWT rotates or leaks:
1. Generate new JWT in Pinata dashboard.
2. Update `bridge/.env::PINATA_JWT`.
3. Re-pin all CIDs referenced in `bridge/vapi_bridge/cedar_bundles/*.json`
   (operator action; no scripted recovery in this stream).

---

## 8. Recovery drill cadence

Run a full restore drill against a scratch machine (or VM) **once per
quarter**. The drill is the only proof that this runbook is current.
Drift between runbook + reality is the disaster the runbook is supposed
to prevent.

---

**Authoring:** DECON-1 Stream 3, 2026-06-10. See
`audits/decon-store-map.md` for the parallel Stream 2 work and
`memory/project_decon1_stream3_dr_runbook.md` for the architectural
reasoning.
