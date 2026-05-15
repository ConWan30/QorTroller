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
    (
        "getDeviceWallet(bytes32)",
        "VAPIioIDRegistry",
        "validate_poac_record.ts",
        "Phase O4-VPM-INT-A.PARTIAL device_id_hash → gamer address "
        "resolution. Selector 0x0ff0779b used by _resolve_device_to_gamer "
        "before consent-routing checks.",
    ),
]

# Placeholders currently present in the applet sources at this commit.
# Each tuple: (hex_placeholder, file_glob, real_signature_to_replace_with)
#
# Phase O4-VPM-INT-A.PARTIAL (2026-05-14): 0xCAFE0237 and 0xDEADBEEF were
# removed from validate_poac_record.ts when the ABI_ENCODER + CONSENT_RETURN_DATA
# + DEVICE_ID_TO_GAMER deltas closed. The real selectors (0x7c4847ed,
# 0xbabcf9f5, 0x0ff0779b) are now used directly as FROZEN constants. The
# audit detects placeholders by literal substring; with the placeholders
# removed from source, the audit no longer flags them.
KNOWN_PLACEHOLDERS = [
    ("0xCAFE0237", "validate_poac_record.ts", "isConsentValid(address,uint8)"),
    ("0xDEADBEEF", "validate_poac_record.ts",
     "submitPITLProof(bytes32,bytes,uint256,uint256,uint256,uint256,uint256)"),
]

# Crypto-integration deltas the applet-pipeline phase must address.
# Phase O4-VPM-INT-A.PARTIAL (2026-05-14): ABI_ENCODER + CONSENT_RETURN_DATA +
# DEVICE_ID_TO_GAMER moved to CLOSED_DELTAS below.
# Phase O4-W3B-POSEIDON-AS (2026-05-14): POSEIDON_HASH moved to CLOSED_DELTAS.
# The W.1 V-check established that POSEIDON_HASH was never an in-applet
# computation delta: featureCommitment + nullifierHash derive from
# circuit-PRIVATE inputs (scaledFeatures[7], deviceIdHash) that do not travel
# in the 228-byte PoAC wire format. The applet RELAYS these bridge-computed
# ZK public inputs; it is not their computation site. The verified +
# PV-CI-pinned AS Poseidon(BN254) capability (poseidon_bn254.ts) resolves the
# capability layer; in-applet wiring is architecture-N/A. See CLOSED_DELTAS.
# P256_VERIFY remains the sole genuinely-open delta (dep-blocked by
# @assemblyscript/wasm-crypto 404).
# Each tuple: (delta_id, applet, current_state, production_requirement)
CRYPTO_INTEGRATION_DELTAS = [
    (
        "P256_VERIFY",
        "validate_poac_record.ts",
        "_verify_p256_stub() returns true unconditionally (explicit deferral; "
        "Hard Rule prohibits shipping unverified crypto)",
        "Integrate @assemblyscript/wasm-crypto + ecdsa.verify(body, sig, pubkey) "
        "where pubkey resolves via VAPIioIDRegistry device-to-wallet mapping. "
        "Currently blocked by @assemblyscript/wasm-crypto 404 on npm registry.",
    ),
]

# Crypto-integration deltas CLOSED in prior commits. Retained for historical
# record so re-audits can confirm the deltas didn't silently re-open.
# Each tuple: (delta_id, applet, closed_in_phase, closure_summary)
CLOSED_DELTAS = [
    (
        "ABI_ENCODER",
        "validate_poac_record.ts",
        "Phase O4-VPM-INT-A.PARTIAL (2026-05-14)",
        "Full ABI v2 encoder for 7-arg submitPITLProof with real selector "
        "0x7c4847ed. Head: deviceId + offset(224) + featureCommitment[ZERO] + "
        "humanityProbInt[ZERO] + inferenceCode + nullifierHash[ZERO] + "
        "epoch[ZERO]. Tail: length(0) + empty data. Total calldata = 260B. "
        "ABI shape is FINAL; zero-placeholder fills change when Poseidon "
        "and P256 deps land.",
    ),
    (
        "CONSENT_RETURN_DATA",
        "validate_poac_record.ts",
        "Phase O4-VPM-INT-A.PARTIAL (2026-05-14)",
        "_check_consent_view now reads 32-byte chain_call return-data buffer "
        "via chain_call_returndata host import, then extracts bool from "
        "rightmost byte via _read_bool_from_returndata(retPtr). RPC-level "
        "errors (chain_call != 0) are correctly distinguished from "
        "consent-state false (rightmost byte == 0).",
    ),
    (
        "DEVICE_ID_TO_GAMER",
        "validate_poac_record.ts",
        "Phase O4-VPM-INT-A.PARTIAL (2026-05-14)",
        "_resolve_device_to_gamer calls VAPIioIDRegistry.getDeviceWallet"
        "(bytes32 deviceIdHash) with real selector 0x0ff0779b. Reads 32-byte "
        "return-data, extracts left-padded address from rightmost 20 bytes, "
        "guards against zero-address (device not registered). Resolved "
        "gamer address (32B-padded) flows into _check_consent_view. "
        "Return code 6 surfaces resolution failures distinctly.",
    ),
    (
        "POSEIDON_HASH",
        "validate_poac_record.ts",
        "Phase O4-W3B-POSEIDON-AS (2026-05-14)",
        "Resolved at the CAPABILITY layer; reclassified architecture-N/A for "
        "in-applet wiring. A protocol-internal AS Poseidon(BN254) module "
        "(scripts/w3bstream/poseidon_bn254.ts) shipped and was verified "
        "byte-identical to circomlibjs 0.1.7 across 525 final-output vectors "
        "+ 150 per-round vectors + 48100 intermediate round-state elements "
        "(V.1 commit 0b6adc13 + V.2 commit a80f3fb4), then pinned by PV-CI "
        "invariants INV-POSEIDON-AS-001/002/003 (PV-CI 83->86, PV.1 commit "
        "de64af4c). The W.1 V-check then established that POSEIDON_HASH was "
        "never an in-applet computation delta: featureCommitment = "
        "Poseidon(8)(scaledFeatures[0..6], inferenceCodeFromBody) and "
        "nullifierHash = Poseidon(deviceIdHash, epoch) both derive from "
        "circuit-PRIVATE inputs (scaledFeatures[7], deviceIdHash) per "
        "contracts/circuits/PitlSessionProof.circom -- inputs that do NOT "
        "travel in the 228-byte PoAC wire format (bridge/vapi_bridge/codec.py: "
        "the 164-byte body is 4 hashes + 13 telemetry scalars; no feature "
        "vector, no raw deviceId). The applet RELAYS these bridge-computed ZK "
        "public inputs; it is structurally not their computation site. The "
        "zero placeholders in _encode_submit_proof are the honest "
        "not-yet-relayed state. The AS Poseidon capability stands available "
        "for any future WASM context that must COMPUTE rather than relay a "
        "BN254 Poseidon (e.g. independent in-applet commitment re-derivation "
        "if the bridge->W3bstream message is later extended to carry feature "
        "data). AMBER path: circomlibjs 0.1.7 single reference; V.3 "
        "cross-reference triangulation deferred.",
    ),
]

# Phase O4-VPM-INT-A.5 (Stream A RED path) — Upstream package availability
# blockers for the applet-pipeline rewrite. Each tuple:
#   (package_name, npm_check_status, blocking_for, alternative_path)
# These are FACT: probed via `npm view <package>` on 2026-05-14.
# When a future operator probe finds these packages available, the audit's
# DEPENDENCY_BLOCKERS check upgrades the verdict reasoning automatically.
# Phase O4-W3B-POSEIDON-AS (2026-05-14): the "AssemblyScript Poseidon
# implementation" blocker was RESOLVED -- a verified, PV-CI-pinned AS
# Poseidon(BN254) module shipped (scripts/w3bstream/poseidon_bn254.ts; see
# CLOSED_DELTAS POSEIDON_HASH for the full closure record). It is removed
# from this roster. The W.1 V-check additionally established POSEIDON_HASH
# was never an in-applet wiring delta (relay-not-compute). The sole live
# blocker is @assemblyscript/wasm-crypto (P256_VERIFY).
DEPENDENCY_BLOCKERS = [
    (
        "@assemblyscript/wasm-crypto",
        "404 Not Found on npm registry (re-probed 2026-05-14)",
        ["P256_VERIFY"],
        "Vendor a hand-written ECDSA-P256 AS implementation (~200 LOC) "
        "OR wait for an upstream AS crypto package; do NOT ship pseudo-"
        "production crypto without runtime verification per VAPI's "
        "'verifiable claims with visible limits' posture. Phase O4-VPM-INT-"
        "A.PARTIAL Hard Rule explicitly blocks hand-rolled ECDSA-P256.",
    ),
]


def check_dependency_blockers() -> dict:
    """Return the static DEPENDENCY_BLOCKERS roster as a structured dict.

    This is intentionally STATIC — the audit script doesn't probe npm at
    runtime (would couple audit success to network availability + add a
    latency tier). The roster is updated by operator at re-audit time
    when upstream packages become available.

    Updating this roster is wallet-free; ship the change as a follow-up
    commit with documented re-probe outcome.
    """
    return {
        "as_of_date": "2026-05-14",
        "blockers": [
            {
                "package": pkg,
                "npm_status": status,
                "blocks_deltas": list(blocks),
                "alternative_path": alternative,
            }
            for pkg, status, blocks, alternative in DEPENDENCY_BLOCKERS
        ],
        "any_blocked": len(DEPENDENCY_BLOCKERS) > 0,
        "rationale": (
            "Per VAPI's 'verifiable claims with visible limits' posture: "
            "the applet-pipeline phase MUST NOT ship pseudo-production "
            "crypto without runtime verification. While AS crypto deps "
            "remain unavailable, the applets stay STUB + the deferral is "
            "explicitly documented. Operator re-probes at each future "
            "audit cycle; verdict transitions automatically when blockers "
            "clear."
        ),
    }


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
        # Distinguish dep-blocked STUB from generic STUB: if any of this
        # applet's open deltas matches a DEPENDENCY_BLOCKERS entry, the
        # verdict surfaces STUB_DEPS_BLOCKED so the operator audit knows
        # the gap is upstream-blocked, not just untouched.
        delta_ids = {d[0] for d in deltas_for_applet}
        all_blocked_delta_ids = {
            blocked_id
            for _, _, blocks_list, _ in DEPENDENCY_BLOCKERS
            for blocked_id in blocks_list
            if not blocked_id.endswith("(partial)")
        }
        if delta_ids and delta_ids.issubset(
            all_blocked_delta_ids | {"ABI_ENCODER", "CONSENT_RETURN_DATA",
                                     "DEVICE_ID_TO_GAMER"}
        ):
            # Some deltas remain; check if ANY is dep-blocked
            has_dep_blocked = any(
                d_id in all_blocked_delta_ids for d_id in delta_ids
            )
            verdict = "STUB_DEPS_BLOCKED" if has_dep_blocked else "STUB"
        else:
            verdict = "STUB"
    else:
        verdict = "SELECTORS_OK"  # No placeholders + no crypto deltas means
                                  # at minimum selectors are fixed; further
                                  # production readiness is operator's call.

    closed_for_applet = [
        d for d in CLOSED_DELTAS
        if d[1] == applet_path.name
    ]

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
        "crypto_deltas_closed": [
            {
                "delta_id": d[0],
                "closed_in_phase": d[2],
                "closure_summary": d[3],
            }
            for d in closed_for_applet
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

    # Either STUB or STUB_DEPS_BLOCKED count toward non-zero exit. The
    # distinction is informational — both indicate the applet pipeline
    # is not production-ready — but STUB_DEPS_BLOCKED tells the operator
    # the gap is upstream-blocked.
    any_stub = any(
        a.get("verdict") in ("STUB", "STUB_DEPS_BLOCKED")
        for a in per_applet
    )
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
        "dependency_blockers": check_dependency_blockers(),
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
            lines.append("  Crypto integration deltas (OPEN):")
            for d in a["crypto_deltas_open"]:
                lines.append(f"    [{d['delta_id']}]")
                lines.append(f"      now: {d['current_state']}")
                lines.append(f"      req: {d['production_requirement'][:120]}")
        if a.get("crypto_deltas_closed"):
            lines.append("  Crypto integration deltas (CLOSED):")
            for d in a["crypto_deltas_closed"]:
                lines.append(f"    [{d['delta_id']}] closed in {d['closed_in_phase']}")
                lines.append(f"      summary: {d['closure_summary'][:120]}")
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
