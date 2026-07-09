# PORT-CERT — Portable, Independently Re-Verifiable Match Certificate

**Status:** DESIGN + increment 1 BUILT (2026-07-09). Offline; no rig, no chain write, no FROZEN-v1.
**Novelty:** compose the session's proofs (PoSP + KAS/deferred + VHR ZK proof + on-chain anchor +
consent) into ONE self-contained bundle whose **cryptographic claims a third party can re-verify
against PUBLIC parameters — without the rig and without the raw data.**
**Related:** `l9_presence/posp_verifier.py` (reused), `l9_presence/kas_deferred.py`, VHR
`audits/vhr_proof2_m17/`, A3 anchor `audits/posp_anchor_*_anchor.json`, `bcc_match.py`,
`audits/rp-close-1-ledger-2026-07-07.md`.

---

## 0. The gap

Every current surface is **self-witnessed by the same rig** (`verifier_independence=False`). But that
caveat conflates two different things:

- **the CAPTURE** — the rig generated the surfaces. *Not* trustless (the witness-independence long arc).
- **the PROOFS** — the ZK proof's validity, the commitment consistency, the session-join integrity, the
  on-chain anchor's presence. **These are checkable by anyone with the public parameters.**

Today the proofs are scattered across artifact files and only the rig "knows" they belong together.
PORT-CERT bundles them + ships an **off-rig verifier** so a party *not in the original trust chain* can
re-check the cryptography. It does **not** close capture trust — it makes the math **portable**.

## 1. The certificate (`qortroller-match-certificate-v0`)

REFERENCE-AND-BIND (PoSP/KAS precedent): NO new commitment primitive, NO domain tag, NO FROZEN-v1. The
bundle *references* the surfaces' existing commitments + carries the ZK public inputs (zero-knowledge
safe — no raw data). Per session (`session_id` = the U1 join key across all surfaces):

```
surfaces:
  posp     { verdict, session_id, device_id, file_sha256, record_path }
  kas      { commitment, verdict, session_id } | null
  deferred { verdict, deferred_authored, session_id } | null
  vhr      { replay_proof_token, public_inputs[6], poac_chain_root, sanitized_trace_root,
             proof_ref, public_ref, vkey_ref } | null
  anchor   { registry, tx, block, digest (= posp file_sha256), method } | null
  consent  { manifest_hash } | null
honesty:  advisory=true, cert_scope=developer_self, population_certified=false,
          verifier_independence=false   # the CAPTURE stays rig-witnessed; only the PROOFS are portable
```

## 2. The off-rig verifier — checks (fail-closed)

`verify_match_certificate(cert, *, posp_file_bytes=None, groth16_verify=None, chain_lookup=None)`.
The pure module NEVER shells snarkjs or reads the chain — those are **injected callables** (the runner
supplies them), so the module is pure + deterministic and the network/subprocess blast radius is one script.

| # | Check | How a third party re-runs it | Fail |
|---|-------|------------------------------|------|
| C1 | schema | `schema == qortroller-match-certificate-v0` | SCHEMA_ERROR |
| C2 | **session join** | every present surface carries the cert's `session_id` (anti-splice: a certificate cannot mix sessions) | FAILED |
| C3 | PoSP | `posp.verdict == SYNCHRONIZED` | FAILED |
| C4 | **anchor-digest match** | `SHA-256(published PoSP file bytes) == posp.file_sha256 == anchor.digest` — proves the EXACT PoSP record is the one anchored on-chain | FAILED |
| C5 | **VHR ZK proof** | injected `groth16_verify(vkey, public_inputs, proof)` → snarkjs `groth16 verify` (the runner shells it) | FAILED on FALSE; UNCHECKED → PARTIAL if not injected |
| C6 | anchor on-chain | injected `chain_lookup(tx)` → confirm the anchor tx/digest is on IoTeX (read-only, 0 IOTX) | UNCHECKED → PARTIAL if not injected |
| C7 | authorship | `kas.verdict==AUTHORED_SESSION` or `deferred==DEFERRED_AUTHORED_SESSION` | advisory (note only) |

**Overall (mirrors `posp_verifier`):** `SCHEMA_ERROR` / `FAILED` (any hard check fails) / `VERIFIED`
(all hard checks pass AND the ZK proof verified AND anchor evidence present) / `PARTIAL` (hard checks
pass but some checks were UNCHECKED — e.g. verifier ran without snarkjs or a chain RPC).

## 3. Honest scope

PORT-CERT makes the **proofs** re-verifiable across a trust boundary (a buyer/adjudicator with the
public vkey + the on-chain anchor confirms ZK validity, commitment consistency, session-join, and that
the exact PoSP file was anchored — none of which they could do before, and none of which needs the rig
or the raw session). It does **NOT** make the **capture** trustless: `verifier_independence=false` is
inherited — the rig still generated the surfaces. The novelty is cross-trust-boundary RE-verifiability,
not witness independence. Advisory, `developer_self`, `population_certified=false`.

## 4. Increment 1 (BUILT) / next

1. **BUILT + DEMONSTRATED ON REAL M17:** `l9_presence/port_cert.py` (pure builder + injected-check
   verifier) + `test_port_cert.py` 14/14 + `scripts/match_certificate.py`. Real M17 cert
   `audits/match_certificate_m17.json` (2068 B — references + ZK public inputs only, no raw data). Off-rig
   verify: **all offline checks green** (schema · session-join · posp-synchronized · **anchor-digest-match:
   published PoSP file hashes to `545f9d44…`, the digest anchored on-chain at block 45447322** · authorship
   AUTHORED_SESSION), ZK + on-chain honestly UNCHECKED (no snarkjs/RPC this shell) → **PARTIAL, not a false
   VERIFIED** (the anti-overclaim rail). Passing `--snarkjs` + `--chain-rpc` reaches VERIFIED.
2. **Next (offline):** ADVERSARY-EXPAND red-teams this verifier — forged/tampered bundles must fail C2/C4/C5.
3. **Later:** a signed certificate (gamer wallet signs the bundle) so the *holder* is provable too.

## 5. Rails

Advisory · `developer_self` · `verifier_independence=false` inherited · no 228B PoAC contact (references
`record_hash`/commitments, never the wire) · no FROZEN-v1 / domain tag · no chain write / 0 IOTX · pure
stdlib (injected network/subprocess) · single-committer.
