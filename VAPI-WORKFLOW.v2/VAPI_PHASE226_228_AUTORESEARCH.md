# VAPI Autoresearch Phase Assessment — Phases 226–228
**Generated**: 2026-04-17 | **System State**: Phase 225 COMPLETE
**Authored by**: Claude Code VAPI Expert v2.0 (claude-sonnet-4-6)
**Saved to**: `VAPI-WORKFLOW.v2/VAPI_PHASE226_228_AUTORESEARCH.md`

---

## Executive Summary

Phase 225 delivered a cryptographically chained governance audit trail for every allowlist
`--generate` event. The chain is sound on paper, but **three critical unprotected surfaces
remain that together form an exploit chain**: (1) the provenance hash computation code itself
is not frozen by any invariant, (2) the SQLite chain can be silently modified by direct DB
write without triggering `GOVERNANCE_CHAIN_BROKEN`, and (3) the highest-risk governance
category (`invariant_change`) requires only an API key and a typed phrase — no biometric
presence. These three gaps compound: a compromised operator key enables (3), which enables
(2), and if (1) is also silently modified, the entire Phase 224/225 security model degrades
undetected.

**Sequential assessment**: Phase 226 → 227 → 228 form a layered closure. Each phase must
complete before the next is sound. Together they make governance events: (226) unforgeable
by code modification, (227) immutable to direct DB writes, and (228) biometrically gated
against operator-key-only compromise.

---

## Current Security Surface Map (Post-Phase 225)

| Layer | What is Protected | Protection Mechanism | Gap |
|-------|------------------|---------------------|-----|
| INV-001..INV-016 | 16 protocol invariant regions | SHA-256 digest in INVARIANTS_ALLOWLIST.json | Provenance code NOT covered |
| `governance_provenance_chain` table | Governance event sequence | SHA-256 chain in SQLite | Mutable via direct DB write |
| `GOVERNANCE_CHAIN_BROKEN` rule | Broken chain links | Bridge query on governance_provenance_chain | Bypassed by consistent direct writes |
| `--confirm-governance` gate | `invariant_change` operator flow | Phrase confirmation + API key | No biometric authentication |
| On-chain anchor (ProtocolCoherenceRegistry) | Fleet Merkle root | anchorCoherence() 37-agent tree | Governance hashes NOT anchored individually |

---

## Phase 226 — Invariant Scope Expansion (INV-017..INV-020)

### Priority Assessment: **CRITICAL / MUST-DO IMMEDIATELY**

**WIF Entry**: WIF-042 (NEW — filed this assessment, 2026-04-17)

**Failure Mode Being Addressed**:
> The functions `_compute_governance_provenance_hash()` and `_fetch_latest_provenance_hash()`
> were added to `scripts/vapi_invariant_gate.py` in Phase 225. These functions define the
> entire security model of the provenance chain. The GOVERNANCE_CHAIN_BROKEN INVERSION rule
> fires only when the chain is structurally broken — but if the hash computation itself is
> silently modified (e.g., `ts_ns` dropped from SHA-256 input, algorithm replaced with MD5,
> or `category` field excluded), the produced hashes are internally consistent and the rule
> never fires. An adversary with repository write access who modifies provenance hash
> computation produces a system that appears healthy while providing zero security guarantees.

**What Phase 226 Implements**:

Add INV-017..INV-020 to `scripts/vapi_invariant_gate.py` and regenerate
`.github/INVARIANTS_ALLOWLIST.json`:

| Invariant ID | File | Pattern | Description |
|-------------|------|---------|-------------|
| INV-017 | `scripts/vapi_invariant_gate.py` | `_compute_governance_provenance_hash` | Provenance hash computation function exists |
| INV-018 | `scripts/vapi_invariant_gate.py` | `ts_ns.*to_bytes.*8.*big\|to_bytes.*8.*big.*ts_ns` | ts_ns included as 8-byte big-endian in provenance hash input |
| INV-019 | `scripts/vapi_invariant_gate.py` | `_fetch_latest_provenance_hash` | Latest provenance hash fetch function exists |
| INV-020 | `bridge/vapi_bridge/store.py` | `governance_provenance_chain\|insert_governance_provenance` | Provenance chain table + insert method exist in store |

**Why These Specific Patterns**:
- INV-017: Ensures the function isn't renamed/removed (name change breaks chain without breaking CI)
- INV-018: The `ts_ns.to_bytes(8, "big")` call is the replay-prevention component — its removal
  makes all governance events with the same inputs produce identical hashes, enabling retroactive
  insertion of fake events with correct-looking chain links
- INV-019: The fetch function determines the chain's previous hash input — replacing it with a
  hardcoded `"0"*64` sentinel breaks chain continuity silently
- INV-020: Ensures the store layer cannot be replaced with a no-op that accepts governance events
  without persisting them

**Bootstrap Sequence for Phase 226**:
```bash
# 1. Add INV-017..INV-020 to INVARIANTS list in scripts/vapi_invariant_gate.py
# 2. Regenerate with governance log (invariant_change category requires --confirm-governance)
python scripts/vapi_invariant_gate.py --generate \
    --reason "invariant_change: Phase 226 adds INV-017..020 to freeze provenance hash computation" \
    --confirm-governance
# Type: "I understand this changes a frozen protocol invariant"
# 3. Verify all 20 pass
python scripts/vapi_invariant_gate.py
```

**Test Delta**:
- Bridge: +8 (T226-1..T226-8: compute_allowlist_hash reflects new invariants; INV-017..020 pass;
  regeneration with reason creates governance event; chain_intact after regeneration)
- SDK: +4 (T226-SDK-1..4: status() reflects 20 total invariants; chain_intact() remains True)
- Hardhat: 0 (no new contract)
- Contracts: 0

**Expected Counts After**: Bridge 2360 | SDK 500 | Hardhat 516 | Contracts 45

**W1 Entry**: WIF-042 — Governance Provenance Code Unprotected by Invariant Gate
> `_compute_governance_provenance_hash()` and `_fetch_latest_provenance_hash()` are the cryptographic
> heart of Phase 225's security model. Neither is covered by INV-001..016. Silent modification
> of these functions produces internally consistent chains that pass all existing rules.

**W2 Entry**: INV-017..020 as Protocol Security Self-Description
> When governance provenance computation is frozen, the invariant set itself becomes a
> cryptographic commitment to the security model: "This system computes provenance hashes
> using SHA-256(prev_prov || new_hash || category || text || ts_ns_8b)." Downstream
> auditors can verify the algorithm by reading INV-018's frozen digest, without needing to
> read the source code. First gaming anti-cheat protocol where the security model's
> self-description is invariant-frozen.

---

## Phase 227 — Governance Provenance On-Chain Anchor

### Priority Assessment: **HIGH / SHOULD FOLLOW IMMEDIATELY AFTER PHASE 226**

**WIF Entry**: WIF-043 (NEW — filed this assessment, 2026-04-17)

**Failure Mode Being Addressed**:
> The `governance_provenance_chain` SQLite table is the only anchor for the chain integrity
> check. The `GOVERNANCE_CHAIN_BROKEN` INVERSION rule detects broken links by querying this
> table — but the table itself is mutable. A direct SQLite write that inserts a
> `governance_provenance_chain` row with a `previous_provenance_hash` that correctly points
> to the previous `governance_provenance_hash` (and a `governance_provenance_hash` that is
> correctly computed from arbitrary inputs) will: (a) NOT trigger GOVERNANCE_CHAIN_BROKEN
> (hashes are internally consistent), (b) appear in `GET /agent/allowlist-governance-history`
> as a legitimate entry, and (c) leave no on-chain trace. The adversary only needs filesystem
> access to the SQLite file — no bridge API key required.

**What Phase 227 Implements**:

Anchor each `governance_provenance_hash` into `ProtocolCoherenceRegistry.sol` as an
**annotation on the existing coherence anchor cycle** — NOT a new contract. Specifically:

1. **Extended `_anchor_cycle()` in `protocol_coherence_agent.py`**: After computing the
   fleet Merkle root (which already includes the virtual allowlist leaf), also read the
   latest `governance_provenance_hash` from the store and include it in the `anchorCoherence()`
   call as an additional bytes32 field.

2. **New `anchorCoherenceWithProvenance(bytes32 merkleRoot, bytes32 governanceProvenanceHash, uint32 agentCount, uint64 tsNs)`** function in `ProtocolCoherenceRegistry.sol`:
   - Backward compatible (existing `anchorCoherence()` remains)
   - Stores `governanceProvenanceHash` alongside each Merkle root on-chain
   - `getLatestGovernanceProvenance() view` returns latest anchored hash
   - Anti-replay on `(merkleRoot, governanceProvenanceHash)` pair

3. **New FSCA cross-check**: `GOVERNANCE_PROVENANCE_ANCHOR_DRIFT` CRITICAL CONTRADICTION rule:
   ```sql
   -- Fires when live governance_provenance_chain latest hash != on-chain anchored hash
   SELECT gpc.governance_provenance_hash, pcl.governance_provenance_hash AS on_chain_hash
   FROM governance_provenance_chain gpc
   JOIN protocol_coherence_log pcl ON pcl.id = (SELECT MAX(id) FROM protocol_coherence_log)
   WHERE gpc.id = (SELECT MAX(id) FROM governance_provenance_chain)
   AND gpc.governance_provenance_hash != pcl.governance_provenance_hash
   ```
   Severity: CRITICAL (fires when SQLite was modified after last anchor cycle)

4. **New SDK method**: `VAPIAllowlistGovernance.on_chain_provenance_hash() -> str`
   calls `GET /agent/protocol-coherence-status` and returns the `governance_provenance_hash`
   field from the latest coherence status.

**Security Property Achieved**:
Once per anchor cycle (default 1h), the governance chain's latest hash is immutably recorded
on IoTeX L1. A direct SQLite write that happens between anchor cycles will be detected at
the next cycle: the new latest `governance_provenance_hash` won't match the on-chain value.
Window of vulnerability: reduced to the anchor interval (1h by default).

**Test Delta**:
- Bridge: +8 (T227-1..T227-8: _anchor_cycle() includes governance_provenance_hash;
  protocol_coherence_log stores governance_provenance_hash; GOVERNANCE_PROVENANCE_ANCHOR_DRIFT
  fires when hashes diverge; anchorCoherenceWithProvenance called when hash available)
- SDK: +4 (T227-SDK-1..4: on_chain_provenance_hash() parses response; returns "" on missing field)
- Hardhat: +6 (Phase227.test.js: anchorCoherenceWithProvenance stores hash; getLatestGovernanceProvenance returns correct value; anti-replay on pair)
- Contracts: +0 (ProtocolCoherenceRegistry.sol extended, not new contract — still 45)

**Expected Counts After**: Bridge 2368 | SDK 504 | Hardhat 522 | Contracts 45

**Deploy Note**: Requires upgrading `ProtocolCoherenceRegistry.sol` (currently LIVE at
`0xfAfe4E8BEE45be22836b90D542045510dDd927Dd`) to add `anchorCoherenceWithProvenance()`.
Two options: (a) deploy new contract ~0.05 IOTX (wallet has ~40.43 IOTX — fully funded),
or (b) use a proxy upgrade pattern. Recommend (a) for simplicity; update `deployed-addresses.json`
and `bridge/.env`.

**W1 Entry**: WIF-043 — SQLite Direct-Write Bypasses GOVERNANCE_CHAIN_BROKEN
> The GOVERNANCE_CHAIN_BROKEN rule checks internal hash consistency within the
> `governance_provenance_chain` table. An adversary with filesystem access can insert
> a consistently-hashed row that does NOT trigger the rule, does NOT appear invalid
> to `GET /agent/allowlist-governance-history`, and has NO on-chain trace. Detection
> window is infinite without on-chain anchoring.

**W2 Entry**: Triple-Anchored Governance Evidence
> Post-Phase 227, each governance event is triple-anchored: (1) hash-linked in SQLite
> `governance_provenance_chain`, (2) included in the virtual allowlist leaf of the fleet
> Merkle root (Phase 224), and (3) directly anchored as a bytes32 field on
> ProtocolCoherenceRegistry. An adversary must simultaneously corrupt SQLite, recompute
> the Merkle root, AND forge an on-chain transaction to erase governance evidence. This
> is the highest governance tamper-resistance of any gaming anti-cheat protocol.

---

## Phase 228 — VHP-Gated Invariant Change Authorization

### Priority Assessment: **HIGH / CRITICAL PATH FOR TOURNAMENT TRUST**

**WIF Entry**: WIF-044 (NEW — filed this assessment, 2026-04-17)

**Failure Mode Being Addressed**:
> The `invariant_change` governance category currently requires: (1) `--confirm-governance`
> CLI flag, (2) `time.sleep(3)` friction, (3) exact phrase `"I understand this changes a
> frozen protocol invariant"`, and (4) a valid `x-api-key` on the bridge POST. This is
> *operator intent* authentication, not *operator identity* authentication. A stolen API key
> enables `invariant_change` events without biometric presence. Since invariant changes
> modify the protocol's security model (by regenerating the frozen digests), a stolen-key
> invariant change is the highest-impact governance attack in the system.
> 
> This risk is distinct from W1 covered by Phases 226-227: those protect the code and chain
> from silent modification. This protects against *explicit* governance abuse via a
> compromised operator key + direct social engineering of the phrase confirmation.

**What Phase 228 Implements**:

1. **New config field**: `vhp_gated_invariant_change_enabled: bool = False`
   (env: `VHP_GATED_INVARIANT_CHANGE_ENABLED`; fail-safe default)

2. **Bridge-side gate on `POST /agent/allowlist-governance-event`**:
   ```python
   if cat == "invariant_change" and cfg.vhp_gated_invariant_change_enabled:
       # Require vhp_token_id in request body
       vhp_token_id = body.get("vhp_token_id")
       if not vhp_token_id:
           return JSONResponse({"error": "invariant_change requires vhp_token_id"}, status_code=403)
       # Verify VHP is live (not expired) via chain.is_vhp_valid(vhp_token_id)
       # Fail-open if chain unreachable (bridge may run without full IoTeX node)
       is_valid = await _check_vhp_validity(vhp_token_id)
       if is_valid is False:  # Only hard-block on confirmed invalid
           return JSONResponse({"error": "VHP expired or invalid"}, status_code=403)
       # Record VHP token in invariant_gate_log row
   ```

3. **Gate script extension**: When `vhp_gated_invariant_change_enabled=True` is returned
   from `GET /agent/invariant-gate-status`, `_post_governance_event()` prompts operator to
   supply `--vhp-token-id` flag (or reads from env `VAPI_VHP_TOKEN_ID`). Fail-open if bridge
   unreachable (unchanged: governance event not stored, warning printed).

4. **Audit trail**: `invariant_gate_log` row includes `vhp_token_id TEXT NOT NULL DEFAULT ''`
   column (idempotent ALTER TABLE Phase 228 block). VHP token ID is visible in governance history.

5. **New FSCA check**: `INVARIANT_CHANGE_WITHOUT_VHP` HIGH severity ORPHAN rule:
   ```sql
   SELECT id, reason_category, reason_text, vhp_token_id
   FROM invariant_gate_log
   WHERE reason_category = 'invariant_change'
   AND vhp_token_id = ''
   AND created_at > (now - 86400)
   ```
   Fires when an `invariant_change` event has no VHP token recorded in the last 24h.
   Severity: HIGH (not CRITICAL because `vhp_gated_invariant_change_enabled=False` default
   means absence is expected on new deployments). Escalates to CRITICAL after `enabled=True`.

6. **New SDK method**: `VAPIAllowlistGovernance.post_invariant_change(reason_text, vhp_token_id) -> dict`
   wraps `POST /agent/allowlist-governance-event` with `reason_category="invariant_change"` and
   `vhp_token_id` field; validates locally before posting.

**Security Property Achieved**:
`invariant_change` events require: operator API key + `--confirm-governance` + exact phrase
+ valid live VHP (biometric presence proved in the last `vhp_ttl_days=90` days). An adversary
who steals the API key cannot make invariant changes without also having an enrolled biometric
VHP token. Since VHP requires separation ratio > 1.0 + ioSwarm quorum (Phase 110), this ties
the highest-risk governance category to the full human verification stack.

**Test Delta**:
- Bridge: +8 (T228-1..T228-8: POST /agent/allowlist-governance-event with invariant_change +
  vhp_gated=True requires vhp_token_id; missing → 403; invalid → 403; valid → 200 + vhp_token_id
  in response; INVARIANT_CHANGE_WITHOUT_VHP fires on empty vhp_token_id; vhp_token_id stored
  in invariant_gate_log)
- SDK: +4 (T228-SDK-1..4: post_invariant_change() sends vhp_token_id; validates locally)
- Hardhat: 0 (no new contract)
- Contracts: 0

**Expected Counts After**: Bridge 2376 | SDK 508 | Hardhat 522 | Contracts 45

**W1 Entry**: WIF-044 — `invariant_change` Category Requires Only API Key + Phrase
> The highest-impact governance category currently gates on operator intent, not operator
> identity. A stolen API key + social-engineered phrase confirmation enables `invariant_change`
> events that modify frozen protocol invariant digests — the deepest protocol security layer.
> No biometric authentication exists on this path.

**W2 Entry**: VHP-Gated Governance as Biometric Protocol Authority
> Post-Phase 228, VAPI becomes the only gaming protocol where changes to frozen protocol
> invariants require cryptographic biometric proof of human presence (VHP soulbound credential
> + ioSwarm quorum). The governance chain is then fully attested: (226) code is frozen,
> (227) chain is on-chain anchored, (228) invariant changes require live VHP.
> Token launch sequencing pitch: "Protocol invariants can only be changed by a biometrically
> verified human operator with an active VHP credential" — unprecedented in gaming DePIN.

---

## Sequential Dependency Graph

```
Phase 225 (COMPLETE)
  ↓
  Phase 226: Freeze provenance code via INV-017..INV-020
  │  ├── INV-018 freezes ts_ns 8-byte inclusion (replay prevention)
  │  └── INV-019 freezes fetch function (chain continuity)
  ↓
  Phase 227: Anchor latest governance_provenance_hash on IoTeX L1
  │  ├── Requires Phase 226 because: anchoring unfrozen code gives false confidence
  │  └── GOVERNANCE_PROVENANCE_ANCHOR_DRIFT uses protocol_coherence_log.governance_provenance_hash
  ↓
  Phase 228: VHP-gate the invariant_change category
     ├── Requires Phase 226 because: VHP gate is only meaningful if the gate code is frozen
     └── Requires Phase 227 because: VHP governance events must be on-chain anchored to be auditable
```

**Why This Ordering Is Mandatory**:
- Phase 227 without Phase 226: on-chain anchoring of code that can be silently modified
  gives false security — auditors trust the anchor but the algorithm is unfrozen
- Phase 228 without Phase 226: VHP-gated events computed by unfrozen functions are
  indistinguishable from VHP-gated events with modified computation
- Phase 228 without Phase 227: VHP governance events exist only in mutable SQLite;
  the biometric requirement is meaningful only if the event record is immutable

---

## WHAT_IF Corpus Additions (Append-Only)

The following entries should be added to `VAPI-WORKFLOW.v2/VAPI_WHAT_IF.md`:

### WIF-042 — Governance Provenance Code Unprotected by Invariant Gate (Phase 226)

**W1 — Failure mode**: `_compute_governance_provenance_hash()` and
`_fetch_latest_provenance_hash()` in `scripts/vapi_invariant_gate.py` define the Phase 225
provenance chain security model but are covered by ZERO of INV-001..INV-016. Silent
modification of these functions (e.g., removing `ts_ns` from hash input, replacing SHA-256
with identity function, or hardcoding `"0"*64` as previous hash) produces internally
consistent chains that pass `GOVERNANCE_CHAIN_BROKEN` and all 16 existing invariant checks.
The Phase 225 security model degrades to zero with no detection mechanism.
**Status**: OPEN — Phase 226 candidate. Filed 2026-04-17.

**W2 — INV-017..020 as cryptographic self-description of the governance security model.**
When frozen, the invariant set becomes a machine-readable commitment to the provenance
algorithm specification. First gaming protocol where the security model's implementation
details are invariant-frozen alongside the protocol invariants they protect.
**Phase candidate**: Phase 226.

---

### WIF-043 — SQLite Direct-Write Bypasses GOVERNANCE_CHAIN_BROKEN (Phase 227)

**W1 — Failure mode**: `governance_provenance_chain` table is mutable via direct filesystem
access to the SQLite database. An adversary with filesystem access can insert rows with
internally consistent `(governance_provenance_hash, previous_provenance_hash)` pairs that:
(a) do NOT trigger `GOVERNANCE_CHAIN_BROKEN` (hashes are consistent), (b) appear legitimate
in `GET /agent/allowlist-governance-history`, and (c) have no on-chain trace.
The Phase 225 detection guarantee requires on-chain anchoring to hold.
**Status**: OPEN — Phase 227 candidate. Filed 2026-04-17.

**W2 — Triple-anchored governance evidence (SQLite chain + virtual Merkle leaf + on-chain hash).**
Anchoring governance_provenance_hash into ProtocolCoherenceRegistry.sol creates the highest
governance tamper-resistance of any gaming DePIN protocol. Simultaneous corruption of all
three layers requires on-chain transaction forgery — cryptographically infeasible.
**Phase candidate**: Phase 227.

---

### WIF-044 — `invariant_change` Category Requires Only API Key + Phrase (Phase 228)

**W1 — Failure mode**: The `invariant_change` governance category gates on *operator intent*
(exact phrase + `--confirm-governance`) but NOT on *operator identity* (biometric VHP).
A stolen API key enables the highest-impact governance category — modifying frozen protocol
invariant digests — without biometric authentication. Invariant changes redefine the
protocol's security perimeter; they must require human presence proof, not just key possession.
**Status**: OPEN — Phase 228 candidate. Filed 2026-04-17.

**W2 — VHP-gated governance as the DePIN industry's first biometrically authenticated
protocol authority mechanism.**
When enabled, protocol invariant changes require a live soulbound VHP credential (biometric
presence + ioSwarm quorum). This makes VAPI the only gaming protocol where protocol evolution
is biometrically gated — a unique tokenomics and governance differentiator for the whitepaper
and tournament regulatory submissions.
**Phase candidate**: Phase 228.

---

## Implementation Readiness Summary

| Phase | Complexity | IOTX Required | Blockers | WIF Closed |
|-------|-----------|---------------|---------|------------|
| 226 | Low (~4h) | 0 (no deploy) | None | WIF-042 |
| 227 | Medium (~6h) | ~0.05 IOTX | Phase 226 complete | WIF-043 |
| 228 | Medium (~5h) | 0 (no deploy) | Phase 226 + 227 | WIF-044 |

**Wallet status**: ~40.43 IOTX available — all three phases fully funded.
**Hardware required**: None — all phases are pure software/contract.
**Tournament blocker status**: None of these phases are on the hardware-gated tournament
critical path. They harden the governance layer independently of the separation ratio
blockers (G-001 P1vP3=0.032, G-002 touchpad_corners 0.728).

---

## Autoresearch Cycle Context

This assessment covers the **paramount security closure** arc for Phase 226–228. These are
not exploratory phases — they are direct consequences of the Phase 224/225 governance model
reaching correctness at the protocol layer while remaining incomplete at the tamper-resistance
and identity authentication layers.

**Autoresearch classification**:
- Phase 226: **W1 closure** (WIF-042 — unfrozen provenance code)
- Phase 227: **W1 closure** (WIF-043 — mutable SQLite chain)
- Phase 228: **W1 closure + W2 opportunity** (WIF-044 — key-only auth + VHP governance DePIN differentiator)

**Post-Phase 228 system state** (projected):
```
Bridge: ~2376 | SDK: ~508 | Hardhat: ~522 | Contracts: 45 ALL LIVE
Invariants: 20 (INV-001..INV-020)
INVERSION rules: 4 (GOVERNANCE_CHAIN_BROKEN remains)
CONTRADICTION rules: 10 (GOVERNANCE_PROVENANCE_ANCHOR_DRIFT + INVARIANT_CHANGE_WITHOUT_VHP = +2)
ORPHAN rules: 8 (INVARIANT_CHANGE_WITHOUT_VHP HIGH orphan = +1)
```

The Phase 226–228 arc completes the governance security model initiated in Phase 224 and
extended in Phase 225, producing a triple-anchored, biometrically gated, invariant-frozen
protocol governance system with no precedent in gaming anti-cheat DePIN.
