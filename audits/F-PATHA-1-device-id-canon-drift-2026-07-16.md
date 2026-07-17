# F-PATHA-1 — device_id 581a836c predates DEVICE_ID_CANON_v1; Path A re-anchor alone can't make it VALID

**Severity: HIGH (blocks Path A for 581a836c). Found BEFORE any spend, during the re-issue device_id check.**

## What

The one live registered device on VMDR (`0x2e5B5FB1`) is `device_id =
581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8`, registered + active, birthCertHash
`8faf6730…`, registeredAt 1779871025 (~2026-05-27, Path A Arc 1).

The current `verify_device_cert` returns **INVALID** for it — not because of the issuer/hash, but because
check 1 (`verify_cert` → `verify_device_id_matches_pubkey`) requires
`device_id == keccak256(uncompressed SEC1 pubkey)` per **DEVICE_ID_CANON_v1**, and that derivation of this
device's pubkey is `20b37e1cf5b8d46e99fa814a654e38e2d9e5a27237b01b223a1d12fb896655fe`, **not** `581a836c`.

## Evidence (all read-only, no spend)

- On-chain `pubkeyHash` (`235a2c04…`) == `sha256(local compressed pubkey)` → **the local
  `~/.vapi/device_birth_cert.json` IS the registered device** (right key, not a stale/mismatched artifact).
- `verify_device_cert.py --offline` → **INVALID** (`device_id_hex mismatch … keccak256(pubkey)=20b37e1c…
  per DEVICE_ID_CANON_v1`).
- No standard derivation of the registered pubkey reproduces `581a836c`:
  keccak(uncompressed65)=`20b37e1c`, keccak(compressed33)=`e2c70c23`, sha256(uncompressed)=`a30061`,
  sha256(compressed)=`235a2c` (= the pubkeyHash). `581a836c` matches none → it was set by an OLD/explicit
  derivation at 2026-05-27 registration that the current canon no longer produces.

## Impact on Path A

The Path A override (`VAPIDeviceBirthCertUpdateRegistry`, committed `9d15f43a`) re-anchors the
**birthCertHash** (check 2). But `581a836c` fails check 1 (device-id) FIRST, independent of the hash. So
**deploying the override + re-anchoring would spend ~0.2 IOTX and the device would STILL read INVALID.**
The re-anchor is necessary-but-not-sufficient for this device.

## The coupling that makes this an operator decision

The DePIN `node_id = 01a574e7ca7f…` was derived as `SHA-256(QORTROLLER-NODE-v0 || device_id_32b ||
first_session_id)` from **581a836c** (memory `[[project_a2a_autonomous_loop_engine_2026_07_13]]`). Switching
the device to the canon-correct `20b37e1c` would **orphan the node_id** (and its first anchored ledger
entry, tx `0xb985f035…`). So this is not a clean swap — it touches device identity + the born node.

## Options (operator decision — NOT fired autonomously)

| Option | What | Trade |
|---|---|---|
| **A — fresh-register under canon** | `provision_device_mfg.py --execute` under the KMS CA derives `20b37e1c` (canon-correct), registers it fresh (VMDR one-shot ALLOWS a new id), verify VALID. **No override contract needed for this.** | 581a836c stays a legacy pre-canon orphan (active but verify-INVALID); node_id derived from 581a836c is orphaned unless re-derived. |
| **B — version the canon** | Introduce `DEVICE_ID_CANON_v2` / a legacy-accept path so `verify_device_id_matches_pubkey` accepts the historical 581a836c derivation. Then the Path A override re-anchor makes 581a836c VALID + node_id preserved. | Touches a device-identity canon (FROZEN-adjacent); needs the original 2026-05-27 derivation reverse-engineered + a governance seal. |
| **C — investigate first** | git-archaeology: how was 581a836c derived at 2026-05-27 (explicit `--device-id`? old canon?) before choosing A vs B. | Cheapest first step; no spend. |

## Root cause (git-archaeology, done — Option C resolved; REFINED post round-26)

**DEVICE_ID_CANON_v1 was introduced `f778e1fd` on 2026-06-18** ("Phase 1A DEVICE_ID_CANON bridge/
manufacturing enforcement"). **581a836c was registered ~2026-05-27** (Path A Arc 1) — **three weeks
BEFORE the canon existed.** So the device was registered correctly under the pre-canon ceremony; the
canon was tightened afterward and now rejects the legacy bind. The device is NOT wrong — the rule changed
under it.

**Refinement (round-26 + fixture check): it is a TWO-KEY bind, not an unknown formula.** `581a836c` IS
canon-derived — `keccak256(042adcdb…)`, the committed golden-fixture pubkey (the controller-identity
key; CI-proven in `test_device_id_canon.py`). But the registered cert binds a **different** key: the
composite host key `02997c…`, whose `sha256(compressed)` is the on-chain `pubkeyHash` (`235a2c04…`).
The 2026-05-27 ceremony passed the identity-derived id explicitly while the cert carried the composite
key; pre-canon nothing required cert-pubkey ≡ id-preimage, and for this device it is not true. So no
derivation of the CERT pubkey ever reproduces `581a836c` (grok round-26 confirmed) — "version the
canon" (Option B) would collapse to a hard-coded exception list. The on-chain pubkeyHash is the only
non-list grandfather.

## Resolution — NOVEL′ mint/verify split + chain-first binding (BUILT 2026-07-16, A2A round-26)

grok round-26 (A2A consult, `docs/a2a/hsm/round-26-grok-consult-canon.txt`) superseded both options:
Option B is a dead end (no recoverable formula — see refined root cause; it collapses to an exception
list) and Option A orphans the born node. The shipped path: **canon for MINTING, chain-binding for
VERIFYING** — the on-chain `pubkeyHash` (the manufacturer's actual attestation) is the authoritative
verify gate for registered devices; local canon re-derivation stays the fail-closed mint gate. NOT a
governance seal (DEVICE_ID_CANON is not PV-CI-pinned; no FROZEN surface touched).

Shipped surfaces:
- `device_birth_cert.py`: `assert_mint_device_id_canon` (mint-only) + `compute_pubkey_hash_hex` +
  `verify_registered_device_binding` (chain-first precedence, fail-closed on malformed evidence) +
  `verify_cert(…, on_chain_pubkey_hash_hex=None)` (default = pre-split byte-identical).
- `scripts/verify_device_cert.py`: online = authoritative chain binding (fetches VMDR `pubkeyHash`
  before check 1); offline = honest INVALID-OFFLINE with a re-run-online hint; unregistered =
  mint-shape best-effort. **Live proof: `581a836c` now reads `VERDICT: VALID` online** (read-only,
  0 IOTX) and INVALID-OFFLINE offline — exactly the round-26 precedence table.
- `scripts/provision_device_mfg.py --reissue <id>`: re-signs the EXISTING VMDR id under the current CA
  (grok footgun #1) — fail-closed chain gate (registered + active + on-chain pubkeyHash == local key),
  never broadcasts `registerDevice`, distinct default cert-out, prints the override re-anchor command.
  Live smoke: gate PASS for 581a836c; REFUSED the unregistered `20b37e1c`.
- ioID unblocked (grok bonus footgun): `controller_ioid_registration._require_device_binding` +
  `chain.register_controller_ioid` accept `on_chain_pubkey_hash_hex` (default None = unchanged canon).
- Doc drift fixed: `DEVICE_ID_CANON_v1.md` §8 (mint/verify split) + golden-vector drift correction.
- Tests: `bridge/tests/test_device_binding_split.py` T-BIND-1..12 incl. the live-device grandfather pin.

**F-PATHA-1 status: RESOLVED at the verify layer.** The Path A override deploy + ~0.2 IOTX re-anchor
(operator-fired) is now SUFFICIENT for 581a836c under the HSM root: `--reissue` under
`MFG_CA_BACKEND=kms` → deploy override → re-anchor NEW_HASH → verify VALID. node_id (`01a574e7…`)
preserved; no re-birth.

Found by the verify-before-spend check on the re-issue step. Read-only git + chain reads only; 0 IOTX; no
write; no contract deployed.
