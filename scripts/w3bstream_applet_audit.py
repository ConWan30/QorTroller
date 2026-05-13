"""W3bstream applet integration audit — wallet-free, read-only.

Closes the documentation gap between the W3bstream applet stubs in
scripts/w3bstream/*.ts and the actual Solidity ABI selectors of the
contracts they bind to.

Today the applets carry PLACEHOLDER hex selectors (0xCAFE0237,
0xDEADBEEF) explicitly marked as "replace at applet-pipeline phase".
The agent cannot do the full applet-pipeline rewrite (AssemblyScript
@assemblyscript/wasm-crypto integration for ECDSA-P256 verify, Poseidon
hash implementation, Groth16 proof byte assembly, real ABI encoder for
the 7-arg submitPITLProof signature — collectively a 1-2 day effort
requiring W3bstream node integration testing). But the SELECTORS the
applets will use ARE computable today from the deployed contract ABIs
via keccak256.

This audit:

  1. Lists every PLACEHOLDER selector currently in the applet sources
  2. Computes the REAL selector for each via keccak256(signature)[:4]
  3. Surfaces the integration deltas the future applet-pipeline phase
     must address (P256 verify, Poseidon, Groth16, real ABI encoders)
  4. Reports a single per-applet readiness verdict:
        STUB         — current state; not production-deployable
        SELECTORS_OK — selectors match real ABI, crypto stubs remain
        PRODUCTION   — all crypto integrated, registration-ready

Run:

    python scripts/w3bstream_applet_audit.py
    python scripts/w3bstream_applet_audit.py --json

WALLET-FREE CONTRACT:
  - No transaction submission paths invoked
  - No bridge HTTP calls
  - No env-var changes
  - No file mutation outside the audit report output
  - CHAIN_SUBMISSION_PAUSED state untouched

Exit codes:
  0  All applets at SELECTORS_OK or PRODUCTION (post-applet-pipeline)
  1  One or more applets at STUB (current state at this commit)
  2  Configuration / file-access error
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPLET_DIR = PROJECT_ROOT / "scripts" / "w3bstream"


def _keccak256(data: bytes) -> bytes:
    """Keccak-256 (Ethereum's hash function, NOT NIST SHA-3-256)."""
    try:
        # eth_utils provides the canonical Ethereum keccak.
        from eth_utils import keccak  # type: ignore
        return keccak(data)
    except ImportError:
        # Fallback: pycryptodome
        try:
            from Crypto.Hash import keccak as _keccak_mod  # type: ignore
            h = _keccak_mod.new(digest_bits=256)
            h.update(data)
            return h.digest()
        except ImportError:
            raise RuntimeError(
                "Neither eth_utils nor pycryptodome installed; cannot "
                "compute Ethereum keccak256. Install one via:\n"
                "  pip install eth_utils\n"
                "or:\n"
                "  pip install pycryptodome"
            )


def selector_for(signature: str) -> str:
    """Compute the 4-byte ABI function selector for a Solidity signature.

    Example: selector_for('isConsentValid(address,uint8)') -> '0xbabcf9f5'
    """
    sel_bytes = _keccak256(signature.encode("utf-8"))[:4]
    return "0x" + sel_bytes.hex()


# FROZEN authoritative ABI signatures the applets bind to. Each tuple:
#   (signature, target_contract, applet_consumer, purpose)
# Updating any of these requires updating both this constant AND the
# corresponding applet source.
AUTHORITATIVE_SIGNATURES = [
    (
        "isConsentValid(address,uint8)",
        "VAPIConsentRegistry",
        "validate_poac_record.ts",
        "Phase 237-EXTEND consent routing check (replaces 0xCAFE0237 placeholder)",
    ),
    (
        "submitPITLProof(bytes32,bytes,uint256,uint256,uint256,uint256,uint256)",
        "PITLSessionRegistry",
        "validate_poac_record.ts",
        "Phase 62 ZK proof submission (replaces 0xDEADBEEF placeholder; "
        "FULL signature has 7 args, not 3 — applet stub is significantly "
        "under-spec'd vs production)",
    ),
    (
        "getConsentRecord(address,uint8)",
        "VAPIConsentRegistry",
        "(future read pattern)",
        "Phase 237 consent record fetch — not yet bound in any applet",
    ),
    (
        "isCertified(bytes32)",
        "VAPIHardwareCertRegistry",
        "(future read pattern)",
        "Phase 99A hardware cert composition check — not yet bound",
    ),
]

# Placeholders currently present in the applet sources at this commit.
# Each tuple: (hex_placeholder, file_glob, real_signature_to_replace_with)
KNOWN_PLACEHOLDERS = [
    ("0xCAFE0237", "validate_poac_record.ts", "isConsentValid(address,uint8)"),
    ("0xDEADBEEF", "validate_poac_record.ts",
     "submitPITLProof(bytes32,bytes,uint256,uint256,uint256,uint256,uint256)"),
]

# Crypto-integration deltas the applet-pipeline phase must address.
# Each tuple: (delta_id, applet, current_state, production_requirement)
CRYPTO_INTEGRATION_DELTAS = [
    (
        "P256_VERIFY",
        "validate_poac_record.ts",
        "_verify_p256_stub() returns true unconditionally",
        "Integrate @assemblyscript/wasm-crypto + ecdsa.verify(body, sig, pubkey) "
        "where pubkey resolves via VAPIioIDRegistry device-to-wallet mapping",
    ),
    (
        "ABI_ENCODER",
        "validate_poac_record.ts",
        "_encode_submit_proof() emits 4-byte selector + 3 padded fields = stub shape",
        "Replace with full ABI encoder emitting 7-arg submitPITLProof: "
        "bytes32 deviceId + dynamic-length bytes proof + 5 uint256 fields. "
        "Variable-length 'bytes proof' requires offset+length prefix per "
        "Solidity ABI v2 spec.",
    ),
    (
        "POSEIDON_HASH",
        "validate_poac_record.ts",
        "nullifierHash uint256 derivation not implemented",
        "Implement Poseidon(deviceIdHash, epoch) in AssemblyScript or "
        "find an AS-compiled circom-Poseidon implementation. nullifierHash "
        "is the anti-replay guard at PITLSessionRegistry.submitPITLProof.",
    ),
    (
        "CONSENT_RETURN_DATA",
        "validate_poac_record.ts",
        "_check_consent_view assumes chain_call return==0 means consent-valid",
        "Read the actual return-data buffer (32 bytes; bool is rightmost byte) "
        "and treat non-zero rightmost byte as consent-valid. The chain_call "
        "return code is RPC-level (was the call reachable), not consent state.",
    ),
    (
        "DEVICE_ID_TO_GAMER",
        "validate_poac_record.ts",
        "device_id bytes treated as gamer address in stub",
        "Real flow: device_id_hash -> VAPIioIDRegistry.getDeviceWallet(hash) "
        "-> gamer address. Requires extra chain_call before consent check.",
    ),
]


def audit_one_applet(applet_path: Path) -> dict:
    """Scan one applet file. Reports its current state + deltas."""
    if not applet_path.exists():
        return {
            "applet": applet_path.name,
            "exists": False,
            "verdict": "MISSING",
        }

    try:
        source = applet_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {
            "applet": applet_path.name,
            "exists": True,
            "verdict": "READ_ERROR",
            "error": str(exc),
        }

    placeholders_found: list[dict] = []
    for placeholder, target_file, real_sig in KNOWN_PLACEHOLDERS:
        if applet_path.name != target_file:
            continue
        if placeholder.lower() in source.lower():
            placeholders_found.append({
                "placeholder": placeholder,
                "real_signature": real_sig,
                "real_selector": selector_for(real_sig),
            })

    deltas_for_applet = [
        d for d in CRYPTO_INTEGRATION_DELTAS
        if d[1] == applet_path.name
    ]

    if placeholders_found or deltas_for_applet:
        verdict = "STUB"
    else:
        verdict = "SELECTORS_OK"  # No placeholders + no crypto deltas means
                                  # at minimum selectors are fixed; further
                                  # production readiness is operator's call.

    return {
        "applet": applet_path.name,
        "exists": True,
        "size_bytes": len(source.encode("utf-8")),
        "lines": source.count("\n") + 1,
        "placeholders_found": placeholders_found,
        "crypto_deltas_open": [
            {
                "delta_id": d[0],
                "current_state": d[2],
                "production_requirement": d[3],
            }
            for d in deltas_for_applet
        ],
        "verdict": verdict,
    }


def run_audit(applet_dir: Path) -> tuple[dict, int]:
    if not applet_dir.exists():
        return ({
            "error": f"applet_dir does not exist: {applet_dir}",
            "exit_code": 2,
        }, 2)

    applets = sorted(applet_dir.glob("*.ts"))
    if not applets:
        return ({
            "error": f"no *.ts applets under {applet_dir}",
            "exit_code": 2,
        }, 2)

    per_applet = [audit_one_applet(p) for p in applets]

    any_stub = any(a.get("verdict") == "STUB" for a in per_applet)
    exit_code = 1 if any_stub else 0

    return ({
        "audit": "w3bstream_applet_integration",
        "applet_dir": str(applet_dir),
        "applets": per_applet,
        "authoritative_signatures": [
            {
                "signature": sig,
                "selector": selector_for(sig),
                "target_contract": tgt,
                "applet_consumer": consumer,
                "purpose": purpose,
            }
            for sig, tgt, consumer, purpose in AUTHORITATIVE_SIGNATURES
        ],
        "exit_code": exit_code,
    }, exit_code)


def render_human(report: dict) -> str:
    if "error" in report:
        return f"ERROR: {report['error']}\nExit code: {report['exit_code']}\n"

    lines = []
    lines.append("=" * 70)
    lines.append("W3bstream Applet Integration Audit")
    lines.append("=" * 70)
    lines.append(f"Applet dir: {report['applet_dir']}")
    lines.append("")

    lines.append("Authoritative ABI selectors (computed via keccak256):")
    for entry in report["authoritative_signatures"]:
        lines.append(
            f"  {entry['selector']}  {entry['signature']}"
        )
        lines.append(
            f"               -> {entry['target_contract']}  ({entry['purpose'][:70]})"
        )
    lines.append("")

    for a in report["applets"]:
        lines.append(f"--- {a['applet']} ---")
        lines.append(f"  verdict: {a['verdict']}")
        if a.get("placeholders_found"):
            lines.append("  Placeholders to replace:")
            for ph in a["placeholders_found"]:
                lines.append(
                    f"    {ph['placeholder']:<10s} -> {ph['real_selector']}  "
                    f"({ph['real_signature']})"
                )
        if a.get("crypto_deltas_open"):
            lines.append("  Crypto integration deltas:")
            for d in a["crypto_deltas_open"]:
                lines.append(f"    [{d['delta_id']}]")
                lines.append(f"      now: {d['current_state']}")
                lines.append(f"      req: {d['production_requirement'][:120]}")
        lines.append("")

    lines.append("=" * 70)
    lines.append(f"Exit code: {report['exit_code']}")
    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="W3bstream applet integration audit",
    )
    parser.add_argument(
        "--applet-dir", type=Path, default=APPLET_DIR,
        help=f"Applet directory (default: {APPLET_DIR})",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    report, exit_code = run_audit(args.applet_dir)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(render_human(report))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
