"""Compute the three governance-package hashes for the Curator scope-expansion
VAPIBiometricGovernance proposal.

Produces:
  - newScopeHash       : keccak256 of canonical-JSON serialization of the
                         scope manifest
                         (off-chain commitment to the scope manifest content)
  - justificationHash  : sha256 of the raw UTF-8 bytes of the justification
                         markdown
                         (off-chain commitment to the justification document)
  - proposalHash       : sha256 of the canonical preimage:
                           b"VAPI-CURATOR-SCOPE-PROPOSAL-v1" (30B)
                           || agentId (32B)
                           || newScopeHash (32B)
                           || justificationHash (32B)
                         = 126 bytes -> 32-byte commitment.
                         THIS is the bytes32 submitted on-chain via
                         VAPIBiometricGovernance.proposeWithVHP() per the
                         actual deployed Phase 222 ABI (V-check 2026-05-28).

The deployed Phase 222 VAPIBiometricGovernance contract takes a single
opaque bytes32 commitment (+ a VHP-gated proposer identity), not the
multi-argument shape some earlier package drafts assumed. proposalHash
encodes the full structured proposal off-chain; any third party with these
files + the formula above can re-derive proposalHash byte-identically.

The b"VAPI-CURATOR-SCOPE-PROPOSAL-v1" domain tag is OFF-CHAIN-ONLY — it is
NOT registered as a FROZEN-v1 PATTERN-017 commitment family. The
governance proposal is a one-shot operational commitment, not a recurring
cryptographic primitive. If future Curator scope-expansion proposals reuse
this domain tag, that's fine — the {agentId, scopeHash, justHash} triple
keeps each commitment unique.

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

# Bridge wallet's Phase 99 VHP token ID — required by VAPIBiometricGovernance
# .proposeWithVHP(proposalHash, vhpTokenId). Per CLAUDE.md: "Phase 99 VHP
# demo mint COMPLETE: tokenId=2 isValid=True for bridge wallet binding
# canonical Sony_DualShock_Edge_CFI-ZCP1 device".
VHP_TOKEN_ID = 2

# Canonical proposalHash preimage domain tag. 30 bytes, off-chain-only.
# Bound at the head of the proposalHash preimage so future Curator scope
# expansions cannot collide with this commitment (every proposal carries
# the same tag + a unique {agentId, scopeHash, justHash} triple).
_PROPOSAL_DOMAIN_TAG = b"VAPI-CURATOR-SCOPE-PROPOSAL-v1"
assert len(_PROPOSAL_DOMAIN_TAG) == 30, "domain tag width drift"


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

    # ── 3. Compute the on-chain proposalHash per the canonical formula ────
    # preimage = domain_tag(30) || agentId(32) || newScopeHash(32) || justHash(32)
    # = 126-byte preimage -> 32-byte commitment via SHA-256
    agent_id_bytes = bytes.fromhex(CURATOR_AGENT_ID[2:])  # strip "0x"
    assert len(agent_id_bytes) == 32, "agentId width drift"
    assert len(scope_hash) == 32, "scope hash width drift"
    assert len(justification_hash) == 32, "justification hash width drift"
    proposal_preimage = _PROPOSAL_DOMAIN_TAG + agent_id_bytes + scope_hash + justification_hash
    assert len(proposal_preimage) == 30 + 32 + 32 + 32 == 126, "preimage width drift"
    proposal_hash = _sha256(proposal_preimage)

    # ── 4. Print human-readable summary ───────────────────────────────────
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
    print(f"  vhpTokenId           : {VHP_TOKEN_ID}  (bridge wallet Phase 99 VHP)")
    print()
    print(f"  proposal preimage    : {len(proposal_preimage)} bytes")
    print(f"  proposal domain tag  : {_PROPOSAL_DOMAIN_TAG.decode('ascii')}  ({len(_PROPOSAL_DOMAIN_TAG)} B)")
    print(f"  proposalHash         : 0x{proposal_hash.hex()}")
    print(f"                         (= SHA-256(domain_tag || agentId || newScopeHash || justificationHash))")
    print()
    print("On-chain submission (verified against deployed Phase 222 ABI):")
    print()
    print("VAPIBiometricGovernance.proposeWithVHP(")
    print(f"    proposalHash = bytes32(0x{proposal_hash.hex()}),")
    print(f"    vhpTokenId   = {VHP_TOKEN_ID}  // bridge wallet's Phase 99 VHP, isValid=True")
    print(")")
    print()
    print("-" * 72)
    print("[!] FINALIZATION DISCIPLINE")
    print("  The hashes above commit the protocol to the EXACT current bytes of")
    print("  both files. Editing either file AFTER submission invalidates the")
    print("  hashes and any third-party audit will detect the mismatch when")
    print("  re-deriving from the post-edit files.")
    print()
    print("  Finalize -> hash -> submit. NEVER submit -> edit.")
    print("-" * 72)

    # ── 5. Machine-readable JSON line for capture by deploy automation ───
    print("DEPLOY_RESULT_JSON " + json.dumps({
        "scriptName":         "compute_governance_hashes",
        "agentId":            CURATOR_AGENT_ID,
        "vhpTokenId":         VHP_TOKEN_ID,
        "newScopeHash":       "0x" + scope_hash.hex(),
        "justificationHash":  "0x" + justification_hash.hex(),
        "proposalHash":       "0x" + proposal_hash.hex(),
        "proposalDomainTag":  _PROPOSAL_DOMAIN_TAG.decode("ascii"),
        "proposalPreimageBytes": len(proposal_preimage),
        "manifestBytes":      len(manifest_canonical),
        "justificationBytes": len(justification_bytes),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
