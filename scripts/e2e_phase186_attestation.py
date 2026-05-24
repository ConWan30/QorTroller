"""Phase 186 — live E2E against the DEPLOYED SeparationRatioRegistry (testnet).

Proves the attestation extension works on the live deployed bytecode:
commitRatio (seed) -> registerAttestation -> attestedRenewCommit (consumes the
attestation, single-use) -> getAttestation shows used=true + new commit recorded.
Owner-only methods; signer = bridge wallet (the contract owner).
"""
import json, os, sys, hashlib, secrets
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv
load_dotenv(ROOT / ".env"); load_dotenv(ROOT / "contracts" / ".env")
from web3 import Web3
from eth_account import Account

RPC = "https://babel-api.testnet.iotex.io"
REG = Web3.to_checksum_address("0xc88eDc0a07F25bC5c499d1b132Ce2Dd8d45BEC1f")
w3 = Web3(Web3.HTTPProvider(RPC))
abi = json.loads((ROOT / "contracts/artifacts/contracts/SeparationRatioRegistry.sol/SeparationRatioRegistry.json").read_text())["abi"]
reg = w3.eth.contract(address=REG, abi=abi)
owner = Account.from_key(os.environ.get("DEPLOYER_PRIVATE_KEY") or os.environ.get("BRIDGE_PRIVATE_KEY"))
assert owner.address.lower() == "0x0cf36db57fc4680bcdfc65d1aff96993c57a4692"
GP = w3.eth.gas_price
print("registry:", REG, "| owner:", owner.address)

def send(fn, gas=300000):
    n = w3.eth.get_transaction_count(owner.address)
    tx = fn.build_transaction({"from": owner.address, "nonce": n, "gasPrice": GP, "chainId": 4690, "gas": gas})
    r = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(owner.sign_transaction(tx).raw_transaction), timeout=180)
    return r

# unique fixtures
commit0 = b"\x00"; commit0 = Web3.keccak(b"e2e-commit-0-" + secrets.token_bytes(8))
commit1 = Web3.keccak(b"e2e-commit-1-" + secrets.token_bytes(8))
attHash = Web3.keccak(b"e2e-attest-" + secrets.token_bytes(8))

# 1) seed an initial commitment (prev for the renewal)
r0 = send(reg.functions.commitRatio(commit0, 1261, 11, 3))
print("commitRatio   tx:", r0.transactionHash.hex(), "status", r0.status)
# 2) register an HMAC attestation (the Phase 186 method)
r1 = send(reg.functions.registerAttestation(attHash, 7))
print("registerAttest tx:", r1.transactionHash.hex(), "status", r1.status)
rec = reg.functions.getAttestation(attHash).call()
print("getAttestation -> ttlDays", rec[0], "registeredAt>0", rec[1] > 0, "used", rec[2])
# 3) attested renewal consuming the attestation (W2 closure feature)
r2 = send(reg.functions.attestedRenewCommit(commit0, commit1, 30, attHash))
print("attestedRenew  tx:", r2.transactionHash.hex(), "status", r2.status)
rec2 = reg.functions.getAttestation(attHash).call()
new_recorded = reg.functions.isCommitted(commit1).call()
total = reg.functions.totalCommits().call()

ok = (r0.status==1 and r1.status==1 and r2.status==1 and rec[2] is False and rec2[2] is True and new_recorded and total >= 2)
print("--- PHASE 186 LIVE E2E ---")
print("attestation used after renew (single-use consumed):", rec2[2])
print("new commit recorded:", new_recorded, "| totalCommits:", total)
print("\nPHASE186_EXTENSION_OPERATIONAL:", ok)
sys.exit(0 if ok else 3)
