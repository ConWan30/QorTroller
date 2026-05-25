"""Phase 3 (Path B) Step 1 — provision the host-held composite device keypair +
register its pubkey on the live VAPIPoEPRegistry.

LOCAL part (no spend): load-or-generate the ML-DSA-44 composite keypair in
~/.vapi, roundtrip-verify (serialize->deserialize->sign->verify), compute the
encode_pubkey blob + poep_commitment, ESTIMATE registerDevice gas.

ON-CHAIN part (spend): broadcasts registerDevice ONLY when POEP_REGISTER_CONFIRM=1.
Estimate-first + 2.0 IOTX hard-cap, matching the deploy discipline.
"""
import json, os, sys, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "bridge"))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env"); load_dotenv(ROOT / "contracts" / ".env")
from web3 import Web3
from eth_account import Account
from l9_presence import composite_sig as c
from vapi_bridge import composite_device_identity as cdi
from vapi_bridge.ipact_challenge import CHALLENGE_TAG
from vapi_bridge.consent_categories import device_id_to_bytes32

HARD_CAP_IOTX = 2.0
REG = Web3.to_checksum_address("0x4Dcfa11d7a4d661065784Acbb1AeCC2f124C7B38")
# The real DualShock device (637874 PoAC records); register the composite key under it.
DEVICE_ID = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"

# --- LOCAL: generate/load + roundtrip self-test ---
kp = cdi.load_or_generate()
blob = cdi.get_composite_pubkey_blob()
# roundtrip: a freshly deserialized signer must produce a verifying composite-sig
import os as _os
_nonce = _os.urandom(32)
_sig = cdi.make_reattest_signer()(_nonce)
_ok = c.verify(c.decode_pubkey(blob), CHALLENGE_TAG, _nonce, _sig)
print("composite keypair :", cdi.DEFAULT_COMPOSITE_KEY_PATH)
print("tier              : ML-DSA-44 + ECDSA-P256")
print("pubkey blob len   :", len(blob), "bytes")
print("roundtrip sign+verify (load->sign->verify):", _ok, "| sig len", len(_sig))
assert _ok, "composite keypair roundtrip FAILED"

b32 = device_id_to_bytes32(DEVICE_ID)
commitment = hashlib.sha256(b"QORTROLLER-POEP-DEVICE-BIND-v0" + b32 + blob).digest()
print("device_id         :", DEVICE_ID)
print("poep_commitment   :", commitment.hex())

# --- chain handle + estimate ---
w3 = Web3(Web3.HTTPProvider("https://babel-api.testnet.iotex.io"))
abi = json.loads((ROOT / "contracts/artifacts/contracts/VAPIPoEPRegistry.sol/VAPIPoEPRegistry.json").read_text())["abi"]
reg = w3.eth.contract(address=REG, abi=abi)
gamer = Account.from_key(os.environ.get("DEPLOYER_PRIVATE_KEY") or os.environ.get("BRIDGE_PRIVATE_KEY"))
print("gamer (registrant):", gamer.address, "| bal", w3.from_wei(w3.eth.get_balance(gamer.address), "ether"), "IOTX")

# guard: already registered?
try:
    existing = bytes(reg.functions.getCompositePubkeyHash(gamer.address, b32).call())
    if existing and existing != b"\x00" * 32:
        print("NOTE: a composite pubkey is ALREADY registered for (gamer, device); registerDevice would overwrite.")
except Exception:
    pass  # fail-open: the already-registered pre-check is advisory only; a read failure
          # (method absent / RPC hiccup) must not block provisioning. Real errors surface
          # at the estimate_gas / send step below.

GP = w3.eth.gas_price
est = reg.functions.registerDevice(b32, blob, commitment, 0).estimate_gas({"from": gamer.address})
gas_limit = (est * 125) // 100
cost = w3.from_wei(est * GP, "ether"); buf = w3.from_wei(gas_limit * GP, "ether")
print("--- GAS ESTIMATE ---")
print("estimate_gas      :", est, "| buffered x1.25:", gas_limit, "| gasPrice", GP)
print("est cost          :", cost, "IOTX | buffered", buf, "IOTX | hard-cap", HARD_CAP_IOTX)
if float(buf) > HARD_CAP_IOTX:
    print("[HARD-CAP EXCEEDED] ABORT."); sys.exit(2)
print("hard-cap check    : PASS")

if os.environ.get("POEP_REGISTER_CONFIRM") != "1":
    print("\n[ESTIMATE-ONLY] POEP_REGISTER_CONFIRM!=1 — NOT broadcasting registerDevice.")
    sys.exit(0)

# --- ON-CHAIN: broadcast registerDevice ---
n = w3.eth.get_transaction_count(gamer.address)
tx = reg.functions.registerDevice(b32, blob, commitment, 0).build_transaction(
    {"from": gamer.address, "nonce": n, "gasPrice": GP, "chainId": 4690, "gas": gas_limit})
r = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(gamer.sign_transaction(tx).raw_transaction), timeout=180)
print("register tx       :", r.transactionHash.hex(), "status", r.status, "gasUsed", r.gasUsed, "block", r.blockNumber)
assert r.status == 1, "registerDevice failed"

# verify on-chain hash == sha256(blob)
onchain = bytes(reg.functions.getCompositePubkeyHash(gamer.address, b32).call())
print("on-chain hash == sha256(blob):", onchain == hashlib.sha256(blob).digest())

# record registration metadata into the key file
import datetime
cdi.update_registration_metadata(
    registered_tx="0x" + r.transactionHash.hex(),
    registry_address=REG,
    registered_device_id=DEVICE_ID,
    registered_gamer=gamer.address,
    registration_tier="mldsa44",
    registered_at_iso=datetime.datetime.now(datetime.timezone.utc).isoformat(),
)
print("REGISTER_RESULT_JSON " + json.dumps({
    "device_id": DEVICE_ID, "registry": REG, "txHash": "0x" + r.transactionHash.hex(),
    "block": r.blockNumber, "gasUsed": r.gasUsed, "status": r.status,
    "pubkey_blob_len": len(blob),
}))
