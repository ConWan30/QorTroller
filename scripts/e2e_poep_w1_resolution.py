"""Phase B ② P4b — live E2E: W-1 resolution operational check (testnet).

Proves a gamer-registered composite key flows back through the PRODUCTION read path
(the real poep_registry_handler.resolve_composite_pubkey two-RPC integrity check),
with the gamer as a SEPARATE wallet from the bridge deployer (sovereignty invariant:
msg.sender is the gamer; the bridge cannot register on its behalf).

Spend: funds a throwaway gamer wallet (~0.3 IOTX) from the bridge wallet, then the
gamer registers one device. Both txs on IoTeX testnet (chain 4690).
"""
import json, os, sys, hashlib, secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env"); load_dotenv(ROOT / "contracts" / ".env")

from web3 import Web3
from eth_account import Account
from vapi_bridge.consent_categories import device_id_to_bytes32
from vapi_bridge.poep_registry_handler import resolve_composite_pubkey

RPC = "https://babel-api.testnet.iotex.io"
REG = Web3.to_checksum_address("0x4Dcfa11d7a4d661065784Acbb1AeCC2f124C7B38")
w3 = Web3(Web3.HTTPProvider(RPC))
print("connected:", w3.is_connected(), "| chainId:", w3.eth.chain_id)

abi = json.loads((ROOT / "contracts/artifacts/contracts/VAPIPoEPRegistry.sol/VAPIPoEPRegistry.json").read_text())["abi"]
reg = w3.eth.contract(address=REG, abi=abi)

bridge_key = os.environ.get("DEPLOYER_PRIVATE_KEY") or os.environ.get("BRIDGE_PRIVATE_KEY")
bridge = Account.from_key(bridge_key)
assert bridge.address.lower() == "0x0cf36db57fc4680bcdfc65d1aff96993c57a4692", bridge.address
GAS_PRICE = w3.eth.gas_price

# --- DETERMINISTIC gamer wallet (reusable across runs + sweepable; NOT the bridge) ---
gamer_key = "0x" + hashlib.sha256(b"vapi-e2e-poep-test-gamer-v1").hexdigest()
gamer = Account.from_key(gamer_key)
print("gamer (deterministic, != bridge):", gamer.address, "| bal",
      w3.from_wei(w3.eth.get_balance(gamer.address), "ether"), "IOTX")

def send(signed):
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(h, timeout=180)

# --- register payload ---
device_id_str = "e2e-poep-test-" + secrets.token_hex(4)
b32 = device_id_to_bytes32(device_id_str)
blob = b"E2E-COMPOSITE-PUBKEY-BLOB-" + secrets.token_bytes(64)  # representative ① encode_pubkey blob
commitment = hashlib.sha256(b"E2E-POEP-COMMIT-" + secrets.token_bytes(16)).digest()
expected_hash = hashlib.sha256(blob).digest()

# --- estimate register gas (call; no funds needed) → fund the SHORTFALL only ---
est = reg.functions.registerDevice(b32, blob, commitment, 0).estimate_gas({"from": gamer.address})
gas_limit = (est * 125) // 100
need = gas_limit * GAS_PRICE + 21000 * GAS_PRICE  # register max + one sweep tx
have = w3.eth.get_balance(gamer.address)
print(f"register est_gas {est} -> gas_limit {gas_limit}; need {w3.from_wei(need,'ether')} have {w3.from_wei(have,'ether')} IOTX")
if have < need:
    short = need - have
    n = w3.eth.get_transaction_count(bridge.address)
    r1 = send(bridge.sign_transaction({"to": gamer.address, "value": short, "gas": 21000,
              "gasPrice": GAS_PRICE, "nonce": n, "chainId": 4690}))
    print("fund tx:", r1.transactionHash.hex(), "status", r1.status, "funded", w3.from_wei(short,'ether'), "IOTX")

# --- gamer registers a device (msg.sender = gamer) ---
gn = w3.eth.get_transaction_count(gamer.address)
tx = reg.functions.registerDevice(b32, blob, commitment, 0).build_transaction(
    {"from": gamer.address, "nonce": gn, "gasPrice": GAS_PRICE, "chainId": 4690, "gas": gas_limit})
r2 = send(gamer.sign_transaction(tx))
print("register tx:", r2.transactionHash.hex(), "status", r2.status, "gasUsed", r2.gasUsed)
assert r2.status == 1, "register failed"

# --- READ BACK via the REAL production integrity function ---
# Mirror chain.get_registered_composite_pubkey:1759-1778 — event-log blob + on-chain
# hash view, fed to the real resolve_composite_pubkey (two-RPC integrity check).
evs = reg.events.DeviceRegistered.get_logs(from_block=0, argument_filters={"deviceId": b32})
assert evs, "no DeviceRegistered event"
ev = evs[-1]
ev_gamer = ev["args"]["gamer"]
event_blob = bytes(ev["args"]["compositePubkeyBlob"])

class _ChainReader:
    def is_registration_valid(self, g, d):
        return bool(reg.functions.isRegistrationValid(g, d).call())
    def get_composite_pubkey_hash(self, g, d):
        h = bytes(reg.functions.getCompositePubkeyHash(g, d).call())
        return h if h and h != b"\x00" * 32 else None
    def get_registration_blob(self, g, d):
        return event_blob

resolved = resolve_composite_pubkey(_ChainReader(), ev_gamer, b32)

print("--- W-1 RESOLUTION CHECK ---")
print("event gamer == registering gamer:", ev_gamer.lower() == gamer.address.lower())
print("on-chain pubkey hash == sha256(blob):",
      bytes(reg.functions.getCompositePubkeyHash(ev_gamer, b32).call()) == expected_hash)
print("resolve_composite_pubkey returned blob:", resolved is not None)
print("resolved blob == registered blob (integrity OK):", resolved == blob)
ok = (resolved == blob and ev_gamer.lower() == gamer.address.lower())
print("\nW1_RESOLUTION_OPERATIONAL:", ok)

# --- sweep leftover gamer balance back to bridge (recover funds) ---
try:
    bal = w3.eth.get_balance(gamer.address)
    fee = 21000 * GAS_PRICE
    if bal > fee:
        gn2 = w3.eth.get_transaction_count(gamer.address)
        rs = send(gamer.sign_transaction({"to": bridge.address, "value": bal - fee, "gas": 21000,
                  "gasPrice": GAS_PRICE, "nonce": gn2, "chainId": 4690}))
        print("sweep-back tx:", rs.transactionHash.hex(), "status", rs.status,
              "returned", w3.from_wei(bal - fee, "ether"), "IOTX")
    else:
        print("sweep-back: skipped (dust)")
except Exception as e:
    print("sweep-back: failed (non-fatal):", e)

sys.exit(0 if ok else 3)
