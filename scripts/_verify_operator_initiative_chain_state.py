"""Path 2 verification — read AgentScope on-chain state for the 3 operator
agents and compare against documented Cedar bundle Merkles from CLAUDE.md
NOTEs. Wallet-free; read-only eth_call against IoTeX testnet.

Purpose: resolve the local-DB-empty vs CLAUDE.md-narratives-rich state
discrepancy discovered 2026-05-18 during Path 2 verification.

Exit codes:
  0 = all 3 agents' on-chain scope_root matches documented Cedar bundle Merkle
  1 = at least one mismatch — surface for operator review
  2 = chain unreachable / contract call failed
"""
import json
import sys
import urllib.request
from urllib.error import URLError

IOTEX_TESTNET_RPC = "https://babel-api.testnet.iotex.io"
AGENT_SCOPE_ADDR = "0xc694692a69bbf1cDAda87d5bc43D345C4579FF13"

# AgentScope.getScopeRoot(bytes32) function selector
# keccak256("getScopeRoot(bytes32)")[:4]
GET_SCOPE_ROOT_SELECTOR = "0x60db13d1"  # placeholder — will compute properly

# Compute selector from function signature
import hashlib
def _keccak256(data: bytes) -> bytes:
    """SHA-3 Keccak-256 (Ethereum) — needs pysha3 or eth_utils. Falls back
    to hashlib's sha3_256 which is NIST SHA-3, NOT Keccak. For accurate
    Ethereum selectors we need eth_utils or pycryptodome with Keccak."""
    try:
        from eth_utils import keccak
        return keccak(data)
    except ImportError:
        try:
            from Crypto.Hash import keccak as kk
            k = kk.new(digest_bits=256)
            k.update(data)
            return k.digest()
        except ImportError:
            raise RuntimeError(
                "Need eth_utils or pycryptodome for Keccak-256. "
                "Install: pip install eth-utils"
            )

def _function_selector(signature: str) -> str:
    """Compute 4-byte Ethereum function selector from signature."""
    return "0x" + _keccak256(signature.encode()).hex()[:8]


GET_SCOPE_ROOT_SELECTOR = _function_selector("getScopeRoot(bytes32)")

AGENTS = {
    "anchor_sentry": {
        "q9": "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c",
        "expected_merkle": "0xebe899279b230ff5d71db22dc4b80282c810ff5bd1a9d249db6e6d309af52e41",
        "note_source": "CLAUDE.md L33 brand-lock NOTE + L38 PATH-B v1 NOTE",
    },
    "guardian": {
        "q9": "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1",
        "expected_merkle": "0x46807e13dd1c81cefa784ab8b30f8cdcaefd60697de921aae46ac24dac000a50",
        "note_source": "CLAUDE.md L33 brand-lock NOTE",
    },
    "curator": {
        "q9": "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8",
        "expected_merkle": "0x44f89d0a05e7594741f7a06a1c4ca817d58396ad41b22b0eb5d0b5ce4be88ae6",
        "note_source": "CLAUDE.md (Curator activation Sessions 1+2+3 2026-05-09)",
    },
}


def _eth_call(rpc_url: str, to_addr: str, data_hex: str) -> str:
    """Make eth_call against the JSON-RPC endpoint. Returns hex result string."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": to_addr, "data": data_hex}, "latest"],
        "id": 1,
    }
    req = urllib.request.Request(
        rpc_url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "QorTroller-OperatorInitiative-Verifier/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read())
    if "error" in body:
        raise RuntimeError(f"RPC error: {body['error']}")
    return body["result"]


def verify_agent(name: str, q9_hex: str, expected_merkle: str) -> dict:
    """Read AgentScope.getScopeRoot(q9) and compare against expected."""
    # Strip 0x prefix from q9, pad to 32 bytes (already 32 bytes)
    q9_padded = q9_hex.lower().replace("0x", "").rjust(64, "0")
    call_data = GET_SCOPE_ROOT_SELECTOR + q9_padded
    try:
        result_hex = _eth_call(IOTEX_TESTNET_RPC, AGENT_SCOPE_ADDR, call_data)
    except URLError as e:
        return {
            "agent": name, "q9": q9_hex, "status": "RPC_UNREACHABLE",
            "error": str(e), "expected": expected_merkle, "actual": None,
        }
    except Exception as e:
        return {
            "agent": name, "q9": q9_hex, "status": "RPC_ERROR",
            "error": str(e), "expected": expected_merkle, "actual": None,
        }
    # Normalize comparison
    expected_norm = expected_merkle.lower().replace("0x", "")
    actual_norm = (result_hex or "0x").lower().replace("0x", "")
    zero_root = "0" * 64
    if actual_norm == zero_root:
        return {
            "agent": name, "q9": q9_hex, "status": "ZERO_ROOT_UNANCHORED",
            "expected": expected_merkle, "actual": "0x" + zero_root,
            "interpretation": "AgentScope returned zero — agent never anchored OR anchored to different scope",
        }
    if actual_norm == expected_norm:
        return {
            "agent": name, "q9": q9_hex, "status": "MATCH",
            "expected": expected_merkle, "actual": "0x" + actual_norm,
        }
    return {
        "agent": name, "q9": q9_hex, "status": "MISMATCH",
        "expected": expected_merkle, "actual": "0x" + actual_norm,
        "interpretation": (
            "AgentScope returned a non-zero scope_root, but it does not match "
            "the Cedar bundle Merkle documented in CLAUDE.md. Either the on-chain "
            "state has been updated post-activation OR the documented Merkle is "
            "incorrect OR a different bundle was anchored. Investigate."
        ),
    }


def main() -> int:
    print("=" * 78)
    print("Operator Initiative — On-Chain State Verification (Path 2)")
    print("=" * 78)
    print(f"RPC:          {IOTEX_TESTNET_RPC}")
    print(f"AgentScope:   {AGENT_SCOPE_ADDR}")
    print(f"Selector:     {GET_SCOPE_ROOT_SELECTOR} (getScopeRoot(bytes32))")
    print()

    results = []
    for name, info in AGENTS.items():
        print(f"--- {name} ---")
        print(f"  Q9 agent_id:        {info['q9']}")
        print(f"  Expected Merkle:    {info['expected_merkle']}")
        print(f"  Source:             {info['note_source']}")
        r = verify_agent(name, info["q9"], info["expected_merkle"])
        results.append(r)
        print(f"  On-chain scope:     {r.get('actual', 'N/A')}")
        print(f"  Status:             {r['status']}")
        if r.get("interpretation"):
            print(f"  Interpretation:     {r['interpretation']}")
        if r.get("error"):
            print(f"  Error:              {r['error']}")
        print()

    print("=" * 78)
    print("Summary")
    print("=" * 78)
    match_count = sum(1 for r in results if r["status"] == "MATCH")
    print(f"  MATCH: {match_count}/{len(results)}")
    for r in results:
        glyph = "✓" if r["status"] == "MATCH" else "✗" if r["status"] == "MISMATCH" else "?"
        print(f"  {glyph} {r['agent']:14s} {r['status']}")

    if match_count == len(results):
        print("\n>>> CHAIN STATE MATCHES DOCUMENTED NARRATIVES <<<")
        print("    On-chain truth confirms Sentry+Guardian+Curator Cedar bundle anchors.")
        print("    Local DB gap is mechanical (bridge hasn't run) — reconstruction is safe.")
        return 0
    elif any(r["status"] in ("RPC_UNREACHABLE", "RPC_ERROR") for r in results):
        print("\n>>> CHAIN UNREACHABLE OR RPC ERROR <<<")
        print("    Cannot verify on-chain state. Retry when network available.")
        return 2
    else:
        print("\n>>> STATE MISMATCH OR UNANCHORED <<<")
        print("    Surface for operator investigation before further action.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
