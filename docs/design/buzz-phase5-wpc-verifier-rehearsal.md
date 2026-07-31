# Buzz × QorTroller — Phase 5 WP-C Independent Verifier Rehearsal

**Status:** REHEARSED — gate **G5-VER** closed for the M17 sealed match
**Date:** 2026-07-31
**Scope doc:** `docs/design/buzz-phase5-product-claims-scope.md` §4 WP-C, §3 G5-VER
**Register row:** R-06 in `docs/design/buzz-phase5-claim-register-v0.md`

---

## 0. What was asked

> Package a sealed match (commitment roots + PORT-CERT / WMP-style verify scripts) so a third
> party can run one command and get `OVERALL: VERIFIED` without operator keys.
> Document the exact command and the honesty flags that must appear.

---

## 1. The command

From a clone of the repo, with Node available:

```bash
cd contracts && npm install && cd ..      # provides snarkjs (one-time)
python scripts/portcert_full_verify.py
```

Defaults are the M17 demo certificate and its PoSP record. For another sealed match:

```bash
python scripts/portcert_full_verify.py --cert <cert.json> --posp <posp_record.json>
```

No operator key, no wallet, no rig, no write. The only network call is a read-only
`eth_getTransactionReceipt` against IoTeX testnet (0 IOTX).

Exit semantics are unchanged and remain fail-closed: `0` = VERIFIED, `1` = ran but not at
bar, `2` = incomplete environment (never a silent pass).

## 2. The result

```
  vkey      : contracts/circuits/VAPIReplayProofVerifier_verification_key.json (published
              fallback; cert vkey_ref 'bridge/.../zk_artifacts/VAPIReplayProofVerifier_
              verification_key.json' is not in this tree)
  snarkjs   : contracts/node_modules/.bin/snarkjs
  chain-rpc : https://babel-api.testnet.iotex.io (reachable; read-only receipt lookup, 0 IOTX)

  schema              PASS  qortroller-match-certificate-v0
  session_join        PASS  all surfaces share session_id
  posp_synchronized   PASS  posp.verdict='SYNCHRONIZED'
  anchor_digest_match PASS  sha256(posp file) == cert == anchor
  vhr_zk_proof        PASS  snarkjs groth16 verify OK
  anchor_onchain      PASS  anchor tx present on-chain
  authorship          PASS  kas='AUTHORED_SESSION' deferred=None

OVERALL: VERIFIED  (ZK checked, anchor-onchain checked)
  PORT-CERT FULL VERIFY: VERIFIED  (C5 ZK checked + C6 anchor checked)  exit=0
```

Session: `bc7287fbf5e95a4c815d4c520c21397e8aba374b3c0cefc9204b105d827baf06`.

## 3. What had to be fixed to get there

The rehearsal is the point of the exercise: on a fresh non-Windows clone the path did **not**
work, in two ways that a stranger would have hit immediately.

### 3.1 The verifying key was not published

The certificate's `vkey_ref` points into `bridge/vapi_bridge/replay_proof_pipeline/zk_artifacts/`,
which is regenerated locally and not in the repo — the runner exited 2 before C5 could run.
The same verifying key **is** tracked at `contracts/circuits/VAPIReplayProofVerifier_verification_key.json`.

`match_certificate.py verify` and `portcert_full_verify.py` now take `--vkey`, and the runner
falls back to the published copy when the cert's ref is absent, printing which key it used.
This cannot manufacture a pass: groth16 verification fails against any key but the circuit's own,
so the substitution is either the right key or a failed check.

### 3.2 The sealed artifacts were sealed as CRLF

`sha256(posp file)` was `c04afa46…` on Linux against an anchored `545f9d44…`. The difference is
entirely line endings: the records were sealed on Windows, the blobs are LF-normalized, and any
non-Windows checkout hashes bytes that were never the sealed bytes. `verify_provenance_dag` failed
the same way on three artifacts (and had been failing in CI for the same reason).

`.gitattributes` now forces `eol=crlf` for `audits/posp_record_*.json`,
`audits/tri_plane_manifest_*.json`, and `wmp_corpus_real/wmp_corpus.jsonl` — the same policy, and
the same reasoning, as the existing `vsd-vault/notes/**/*.md` rule. Checked: no digest anywhere in
the tree references the LF form of any of those files, so this restores the sealed bytes rather
than choosing between two conventions.

Regression pins: `bridge/tests/test_portcert_stranger_verify.py`.

## 4. Honesty flags that must accompany the claim

Any use of register row R-06 carries these:

- **Testnet.** The anchor is IoTeX testnet 4690, not mainnet.
- **Developer-self.** M17 is a single-operator session; the gamer is the operator. G5-MULTI is open.
- **Producer-declared index.** The provenance DAG detects tampering with listed artifacts; it does
  not detect selective omission.
- **Verdict scope.** `SYNCHRONIZED` is a session-liveness candidate verdict. It is not a humanity
  certification and does not advance `poep_enabled` or L6B.
- **Which key.** The runner prints the verifying key it used. A run where the printed key is not the
  published one is a different claim.

## 5. What this does not close

G5-MULTI, G5-SEP, G5-L6, G5-L6B, G5-FRR, and G5-OPS remain open. Nothing above claim grade G1
becomes sayable except R-06, for certificates that have actually been through this command.

---

**End of WP-C rehearsal record**
