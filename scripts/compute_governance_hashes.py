"""Compute the two governance-package hashes for the Curator scope-expansion
VAPIBiometricGovernance proposal.

Produces:
  - newScopeHash       : keccak256 of canonical-JSON serialization of the
                         scope manifest
  - justificationHash  : sha256 of the raw UTF-8 bytes of the justification
                         markdown

Both hashes are submitted as bytes32 arguments to
`VAPIBiometricGovernance.submitProposal()`. They are the on-chain commitments
that a future auditor uses to verify the file contents were NOT tampered with
between submission and audit.

The scope manifest file MAY be stored in indented (human-readable) JSON; this
script canonicalizes it at hash time (`json.dumps(..., sort_keys=True,
separators=(',', ':'))`) so the on-chain hash is deterministic and stable
across whitespace-only edits to the file.

The justification markdown is hashed AS-IS from disk — markdown has no
canonical form. Any edit (even a single trailing newline) changes the hash.
Operators MUST treat finalization as load-bearing: finalize the document
THEN run this script THEN submit. Never submit-then-edit.

Usage:
    python scripts/compute_governance_hashes.py

Exit codes:
    0  hashes computed successfully (printed to stdout + DEPLOY_RESULT_JSON line)
    1  source file missing
    2  manifest JSON parse error
    3  dependency missing (eth_utils for keccak256)

Honesty: this script touches NO chain state. It is pure file-read + pure
hash. Safe to run at any time. The on-chain submission is a separate
operator-fired action (see docs/governance/CURATOR_GOVERNANCE_SUBMISSION_PACKAGE.md
§Submission Checklist).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Paths anchored to the repo root (script lives in scripts/; manifest +
# justification live in docs/governance/).
REPO_ROOT          = Path(__file__).resolve().parent.parent
MANIFEST_PATH      = REPO_ROOT / "docs" / "governance" / "curator-scope-manifest.json"
JUSTIFICATION_PATH = REPO_ROOT / "docs" / "governance" / "curator-governance-justification.md"

# Curator on-chain agentId (Phase 238 Step I-FINAL 2026-05-09, verified
# in contracts/deployed-addresses.json AgentRegistry note).
CURATOR_AGENT_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"


def _keccak256(data: bytes) -> bytes:
    try:
        from eth_utils import keccak
    except ImportError:
        print("ERROR: eth_utils not installed — pip install eth_utils", file=sys.stderr)
        sys.exit(3)
    return keccak(data)


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _canonical_json_bytes(obj) -> bytes:
    """sort_keys=True + tightest separators + UTF-8 — the canonical form
    every on-chain JSON hash in this protocol uses (cedar_parser /
    agent_review_emitter / cdrr_dag_tracker precedent)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def main() -> int:
    # ── 1. Load the manifest as JSON, re-canonicalize for hashing ─────────
    if not MANIFEST_PATH.exists():
        print(f"ERROR: scope manifest not found: {MANIFEST_PATH}", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: scope manifest JSON parse failed: {exc}", file=sys.stderr)
        return 2
    manifest_canonical = _canonical_json_bytes(manifest)
    scope_hash = _keccak256(manifest_canonical)

    # ── 2. Load the justification markdown as raw bytes, sha256 in-place ──
    if not JUSTIFICATION_PATH.exists():
        print(f"ERROR: justification not found: {JUSTIFICATION_PATH}", file=sys.stderr)
        return 1
    justification_bytes = JUSTIFICATION_PATH.read_bytes()
    justification_hash  = _sha256(justification_bytes)

    # ── 3. Print human-readable summary ───────────────────────────────────
    print("-" * 72)
    print("Curator Scope Expansion — VAPIBiometricGovernance Proposal Hashes")
    print("-" * 72)
    print(f"  manifest file        : {MANIFEST_PATH.relative_to(REPO_ROOT)}")
    print(f"  manifest canon bytes : {len(manifest_canonical)} bytes")
    print(f"  newScopeHash         : 0x{scope_hash.hex()}")
    print()
    print(f"  justification file   : {JUSTIFICATION_PATH.relative_to(REPO_ROOT)}")
    print(f"  justification bytes  : {len(justification_bytes)} bytes")
    print(f"  justificationHash    : 0x{justification_hash.hex()}")
    print()
    print(f"  agentId              : {CURATOR_AGENT_ID}")
    print()
    print("On-chain submission template:")
    print()
    print("VAPIBiometricGovernance.submitProposal(")
    print(f"    agentId           = bytes32({CURATOR_AGENT_ID}),")
    print(f"    newScopeHash      = bytes32(0x{scope_hash.hex()}),")
    print(f"    justificationHash = bytes32(0x{justification_hash.hex()}),")
    print(f"    duration          = GOVERNANCE_WINDOW  // 7 days per manifest")
    print(")")
    print()
    print("-" * 72)
    print("[!] FINALIZATION DISCIPLINE")
    print("  The hashes above commit the protocol to the EXACT current bytes of")
    print("  both files. Editing either file AFTER submission invalidates the")
    print("  hash and any third-party audit will detect the mismatch.")
    print()
    print("  Finalize -> hash -> submit. NEVER submit -> edit.")
    print("-" * 72)

    # ── 4. Machine-readable JSON line for capture by deploy automation ───
    print("DEPLOY_RESULT_JSON " + json.dumps({
        "scriptName":         "compute_governance_hashes",
        "agentId":            CURATOR_AGENT_ID,
        "newScopeHash":       "0x" + scope_hash.hex(),
        "justificationHash":  "0x" + justification_hash.hex(),
        "manifestBytes":      len(manifest_canonical),
        "justificationBytes": len(justification_bytes),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
