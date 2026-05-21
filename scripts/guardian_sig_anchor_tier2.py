"""Tier-2 — anchor a Guardian KMS-HSM signature commitment ON-CHAIN (IoTeX
testnet) for third-party-verifiable provenance. One-shot, bounded, triple-gated.

Builds on Tier-1 (Guardian autonomously signs via AWS KMS HSM, 0 IOTX). Tier-2
records a 32-byte commitment to that signature on IoTeX so a third party can
confirm — months later, with no AWS access — that Guardian signed subject X,
and that the attestation existed on-chain at block N.

Cost: ONE GateAttestationAnchor.recordGateAttestation tx, ~0.16–0.29 testnet
IOTX (hard-capped at 0.50). Testnet tokens (faucet, no real value).

DOUBLE-GATE + CONFIRM (process-scoped; bridge/.env never changed):
  Gate 1: env CHAIN_SUBMISSION_PAUSED=false   (kill-switch, process-scope only)
  Gate 2: env GUARDIAN_SIG_ANCHOR_AUTHORIZED=true  (intent)
  Gate 3: --confirm CLI flag
After the shell exits the env vars vanish; bridge/.env stays paused.

The anchored commitment:
  attestation_hash = SHA-256( b"VAPI-GUARDIAN-SIG-ANCHOR-v1"
                              || guardian_pubkey_der || digest || signature_der )
binding (who signed, what was signed, the signature) into one 32-byte value.

USAGE (one shell):
  CHAIN_SUBMISSION_PAUSED=false GUARDIAN_SIG_ANCHOR_AUTHORIZED=true \
    python scripts/guardian_sig_anchor_tier2.py --confirm

EXIT: 0 ok · 1 gate · 2 balance · 3 chain · 5 cost-over-budget
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import hashlib
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_BRIDGE = str(PROJECT_ROOT / "bridge")
if _BRIDGE not in sys.path:
    sys.path.insert(0, _BRIDGE)

COST_BUDGET_IOTX = 0.50      # hard cap; abort if a single anchor would exceed
BALANCE_FLOOR_IOTX = 0.05    # refuse if wallet below this
GAS_LIMIT = 80_000           # AdjudicationRegistry.recordAdjudication gas
DOMAIN = b"VAPI-GUARDIAN-SIG-ANCHOR-v1"
DEVICE_TAG = "VAPI_GUARDIAN_SIG_ANCHOR_v1"  # on-chain deviceIdHash attribution


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT).decode().strip()
    except Exception:
        return "no-git-head"


def _check_gates() -> tuple[bool, str]:
    if os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").strip().lower() != "false":
        return False, "Gate 1 FAILED: set CHAIN_SUBMISSION_PAUSED=false in the SHELL (process-scope, not bridge/.env)."
    if os.environ.get("GUARDIAN_SIG_ANCHOR_AUTHORIZED", "").strip().lower() != "true":
        return False, "Gate 2 FAILED: set GUARDIAN_SIG_ANCHOR_AUTHORIZED=true (intent)."
    return True, "all 3 gates aligned"


async def _run() -> int:
    print("=" * 72); print("Tier-2 — anchor a Guardian KMS-HSM signature on IoTeX testnet"); print("=" * 72)
    ok, reason = _check_gates()
    if not ok:
        print(f"  ABORT: {reason}"); return 1
    print(f"  Gates: {reason}")

    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.chain import ChainClient
    from vapi_bridge.kms_client import KMSClient
    from cryptography.hazmat.primitives.serialization import load_der_public_key
    from cryptography.hazmat.primitives.asymmetric import ec, utils
    from cryptography.hazmat.primitives import hashes

    cfg = Config()
    if getattr(cfg, "chain_submission_paused", True) is not False:
        print("  ABORT: Config.chain_submission_paused did not pick up env override."); return 1
    print("  cfg.chain_submission_paused = False (kill-switch lifted, process-scope)")

    # ── Produce a real Guardian KMS-HSM signature (0 IOTX, off-chain) ──
    kms = KMSClient()
    subject = f"draft://commit_hashes/{_git_head()}"
    digest = hashlib.sha256(subject.encode("utf-8")).digest()
    signature = await kms.sign("guardian", digest)
    kms_ok = bool(await kms.verify("guardian", digest, signature))
    pub_der = await kms.get_public_key("guardian")
    meta = await kms.describe_key("guardian")
    # independent local verify (no AWS trust)
    pub = load_der_public_key(pub_der)
    try:
        pub.verify(signature, digest, ec.ECDSA(utils.Prehashed(hashes.SHA256()))); local_ok = True
    except Exception:
        local_ok = False
    print(f"  Guardian signature: kms_verified={kms_ok} local_verified={local_ok} curve={pub.curve.name} keyspec={meta.get('KeySpec')}")
    if not (kms_ok and local_ok):
        print("  ABORT: signature did not verify — refusing to anchor."); return 3

    attestation_hash = hashlib.sha256(DOMAIN + pub_der + digest + signature).hexdigest()
    print(f"  attestation_hash (to anchor): {attestation_hash}")

    # ── Wallet + cost pre-checks ──
    chain = ChainClient(cfg)
    if chain._account is None:
        print("  ABORT: bridge wallet not loaded"); return 2
    addr = chain._account.address
    bal_before = (await chain._w3.eth.get_balance(addr)) / 1e18
    gas_price = await chain._w3.eth.gas_price
    est_cost = GAS_LIMIT * gas_price / 1e18
    print(f"  Wallet: {addr}")
    print(f"  Balance before: {bal_before:.6f} IOTX | gas_price {gas_price/1e9:.0f} Gwei | est cost ~{est_cost:.4f} IOTX")
    if bal_before < BALANCE_FLOOR_IOTX:
        print(f"  ABORT: balance {bal_before:.6f} < floor {BALANCE_FLOOR_IOTX}"); return 2
    if est_cost > COST_BUDGET_IOTX:
        print(f"  ABORT (pre-send cap): est cost {est_cost:.4f} > budget {COST_BUDGET_IOTX}"); return 5

    # ── Fire ONE anchor tx — direct recordAdjudication build with DYNAMIC gas.
    # chain.py wrappers use static low gas (80k/100k) that hits IoTeX out-of-gas
    # (status 101); anchor_corpus_snapshot proves the fix is estimate_gas*1.25
    # (~160k for the two-SSTORE storage op). Build directly to keep correct
    # GUARDIAN_SIG deviceIdHash attribution AND a pre-send revert guard.
    ts_ns = __import__("time").time_ns()
    import hashlib as _hl
    addr_reg = getattr(cfg, "adjudication_registry_address", "")
    if not addr_reg:
        print("  ABORT: adjudication_registry_address not configured"); return 3
    _ABI = [{"name": "recordAdjudication", "type": "function", "stateMutability": "nonpayable",
             "inputs": [{"name": "deviceIdHash", "type": "bytes32"},
                        {"name": "poadHash", "type": "bytes32"},
                        {"name": "dualVeto", "type": "bool"}], "outputs": []}]
    reg = chain._w3.eth.contract(address=chain._w3.to_checksum_address(addr_reg), abi=_ABI)
    device_id_hash = _hl.sha256(DEVICE_TAG.encode()).digest()
    poad_bytes = bytes.fromhex(attestation_hash)
    nonce = await chain._w3.eth.get_transaction_count(addr)
    tx = await reg.functions.recordAdjudication(device_id_hash, poad_bytes, False).build_transaction(
        {"from": addr, "nonce": nonce})
    # PRE-SEND revert guard: estimate_gas reverts iff the call itself would revert.
    try:
        gas_est = await chain._w3.eth.estimate_gas(tx)
    except Exception as exc:
        print(f"  ABORT (pre-send): estimate_gas reverted — the call would revert, NOT sending: {exc}"); return 3
    tx["gas"] = int(gas_est * 1.25)
    est_cost2 = tx["gas"] * gas_price / 1e18
    print(f"  estimate_gas={gas_est} -> gas={tx['gas']} | est cost ~{est_cost2:.4f} IOTX")
    if est_cost2 > COST_BUDGET_IOTX:
        print(f"  ABORT (pre-send cap): est cost {est_cost2:.4f} > budget {COST_BUDGET_IOTX}"); return 5
    print("\n  Firing recordAdjudication (1 tx, AdjudicationRegistry, GUARDIAN_SIG attribution)...")
    try:
        signed = chain._account.sign_transaction(tx)
        txh = await chain._w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash = txh.hex()
    except Exception as exc:
        print(f"  CHAIN ERROR: {exc}"); return 3
    print(f"  tx_hash: {tx_hash}")
    # WAIT for the tx to mine BEFORE any post-checks (else TransactionNotFound).
    receipt = await chain._w3.eth.wait_for_transaction_receipt(txh, timeout=120)
    block = receipt.get("blockNumber")
    status = receipt.get("status")
    try:
        recorded = await chain.is_adjudication_recorded(attestation_hash)
    except Exception as exc:
        print(f"  WARN: isRecorded verify failed: {exc}"); recorded = None
    print(f"  on-chain isRecorded({attestation_hash[:16]}...): {recorded}")

    # ── Cost accounting + cap enforcement ──
    bal_after = (await chain._w3.eth.get_balance(addr)) / 1e18
    cost = bal_before - bal_after
    print(f"  Balance after: {bal_after:.6f} IOTX | cost {cost:.6f} IOTX | block {block} | status {status}")
    if cost > COST_BUDGET_IOTX:
        print(f"  COST OVERAGE: {cost:.6f} > {COST_BUDGET_IOTX} — investigate."); over = True
    else:
        over = False

    # ── Persist + document ──
    try:
        store = Store(cfg.db_path)
        store.insert_operator_agent_signature(
            agent_id="guardian", draft_id=0, subject=f"TIER2-ANCHOR:{subject}",
            digest_hex=digest.hex(), signature_hex=signature.hex(),
            kms_key_spec=str(meta.get("KeySpec", "")), kms_verified=kms_ok, ts_ns=ts_ns,
        )
    except Exception as exc:
        print(f"  WARN: signature-log persist failed (non-fatal): {exc}")

    proven = (status == 1) and (recorded is True) and not over
    ts_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = f"""# QorTroller — Tier-2 Proof: Guardian Signature Anchored on IoTeX

**Claim proven:** a Guardian AWS-KMS-HSM signature commitment is recorded
**on-chain on IoTeX testnet** — third-party verifiable, no AWS access required.

**Result: {"PROVEN" if proven else "SEE FIELDS"}**  ·  {ts_iso}

| Field | Value |
|---|---|
| network | IoTeX testnet (chain ID 4690) |
| contract | AdjudicationRegistry `{getattr(cfg,'adjudication_registry_address','')}` |
| deviceIdHash attribution | SHA-256(`{DEVICE_TAG}`) |
| tx_hash | `{tx_hash}` |
| block | {block} · status {status} |
| attestation_hash (on-chain, isRecorded={recorded}) | `{attestation_hash}` |
| signed subject | `{subject}` |
| sha256 digest | `{digest.hex()}` |
| guardian signature (DER) | `{signature.hex()}` |
| guardian KMS key spec | `{meta.get('KeySpec','')}` (curve `{pub.curve.name}`) |
| KMS verify / local verify | {kms_ok} / {local_ok} |
| cost | **{cost:.6f} IOTX** (testnet; hard cap {COST_BUDGET_IOTX}) |
| wallet | `{addr}` |

## How a third party verifies (no AWS)
1. Recompute `attestation_hash = SHA-256(b"VAPI-GUARDIAN-SIG-ANCHOR-v1" || guardian_pubkey_der || digest || signature_der)` from the values above.
2. Confirm `AdjudicationRegistry.isRecorded(attestation_hash) == true` at the tx/block above (IoTeX testnet explorer / eth_call).
3. Verify the signature itself against Guardian's KMS public key (ECDSA, curve `{pub.curve.name}`, prehashed SHA-256).

## Scope / honesty
Testnet (no real economic value); single bounded tx (~{cost:.3f} IOTX, hard-capped {COST_BUDGET_IOTX}); the kill-switch was lifted process-scoped only (bridge/.env stays paused; restart re-engages it). Anchored via one-shot operator-confirmed script — autonomous on-chain anchoring by the executor is a separate future tier.
"""
    out = PROJECT_ROOT / "docs" / "qortroller-guardian-sig-onchain-anchor-proof.md"
    out.write_text(doc, encoding="utf-8")

    print("\n  " + "=" * 70)
    print(f"  TIER-2 {'PROVEN' if proven else 'INCOMPLETE'} — Guardian signature anchored on IoTeX")
    print("  " + "=" * 70)
    print(f"    tx={tx_hash} block={block} status={status} cost={cost:.6f} IOTX")
    print(f"    attestation_hash={attestation_hash}")
    print(f"    artifact: {out}")
    return 0 if proven else 5


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--confirm", action="store_true", help="required to fire the tx")
    a = ap.parse_args()
    if not a.confirm:
        print("  DRY RUN: --confirm absent. No on-chain operation."); return 0
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(_main())
