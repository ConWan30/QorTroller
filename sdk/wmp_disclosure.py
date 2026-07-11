"""WMP Selective Disclosure (SD-1) — commit to a SET of VDC claims, reveal a
chosen SUBSET, hide the rest, all bound to one certified bundle.

The gamer controls WHICH derived claims a consumer sees. The disclosure commits
IMMUTABLY to the full set (count + claim-type inventory + per-claim hashes), so
the gamer cannot cherry-pick post-hoc or hide the EXISTENCE of claims; then
reveals only the chosen claims' full values. Purest "Core Controllers": the
gamer decides what leaves their hands.

This is the desk-buildable (no-ceremony) half of "ZK selective disclosure". Its
honest ceiling:

  * Proves — the revealed claims are members of an IMMUTABLE committed set of N
    claims, all bound to one certified bundle; the claim-type inventory + count
    are committed (tamper-evident).
  * Does NOT — re-derive the revealed VALUES without the bundle (that is
    VDC-with-bundle); reveal or assert anything about HIDDEN claims' values; hide
    the hidden claims' HASHES (a Merkle-tree upgrade would); provide
    zero-knowledge — "prove value ≥ threshold WITHOUT revealing it" is the
    ceremony-gated property-proof rung, named and deferred.

Pure stdlib + sdk.wmp_derived. No ceremony, no chain, no spend.
"""
from __future__ import annotations

import hashlib

from sdk.wmp_derived import _claim_hash, SCHEMA as _CLAIM_SCHEMA

SCHEMA = "vapi-wmp-disclosure-v1"
_DOMAIN = "VAPI-WMP-DISCLOSURE-v1"


def _commitment_root(parent_bundle_hash: str, leaf_hashes: list, inventory: list) -> str:
    """Immutable commitment over bundle + count + sorted leaves + sorted inventory.
    Binding the inventory means a discloser cannot misstate which claim TYPES exist
    without breaking the root."""
    payload = "|".join([
        _DOMAIN,
        str(parent_bundle_hash),
        str(len(leaf_hashes)),
        ",".join(sorted(leaf_hashes)),
        ",".join(sorted(inventory)),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_disclosure(claims: list, reveal_ids=None) -> dict:
    """Commit to `claims` (all VDC claims bound to the same bundle) and reveal the
    subset whose derivation_id is in `reveal_ids` (default: reveal all)."""
    if not claims:
        raise ValueError("no claims to disclose")
    pbh = claims[0].get("parent_bundle_hash")
    for c in claims:
        if c.get("schema") != _CLAIM_SCHEMA:
            raise ValueError(f"not a VDC claim: schema={c.get('schema')!r}")
        if c.get("parent_bundle_hash") != pbh:
            raise ValueError("all claims must bind to the same parent bundle")
    leaves = sorted(_claim_hash(c) for c in claims)
    inventory = sorted(c["derivation_id"] for c in claims)
    root = _commitment_root(pbh, leaves, inventory)
    want = set(inventory) if reveal_ids is None else set(reveal_ids)
    revealed = [c for c in claims if c.get("derivation_id") in want]
    return {
        "schema": SCHEMA,
        "parent_bundle_hash": pbh,
        "set_size": len(claims),
        "derivation_inventory": inventory,   # which claim TYPES exist (not their values)
        "commitment_root": root,
        "leaf_hashes": leaves,               # the envelope: hashes, never values
        "revealed": revealed,                # full claims for the chosen subset only
    }


def verify_disclosure(disclosure: dict) -> dict:
    """Fail-closed: the commitment recomputes (immutability), and every revealed
    claim hashes to its claim_hash, binds to the disclosure's bundle, and is a
    member of the committed set."""
    checks: list = []

    def _chk(name, ok, note=""):
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return bool(ok)

    ok = _chk("schema", disclosure.get("schema") == SCHEMA, f"schema={disclosure.get('schema')!r}")
    leaves = list(disclosure.get("leaf_hashes") or [])
    inventory = list(disclosure.get("derivation_inventory") or [])
    pbh = disclosure.get("parent_bundle_hash")
    ok &= _chk("set_size", disclosure.get("set_size") == len(leaves), "set_size == leaf count")
    ok &= _chk("inventory_size", len(inventory) == len(leaves), "inventory count == leaf count")
    ok &= _chk("commitment_root",
               disclosure.get("commitment_root") == _commitment_root(pbh, leaves, inventory),
               "root recomputes over bundle + count + leaves + inventory (immutability)")
    leafset = set(leaves)
    integrity = binding = membership = in_inventory = True
    for c in (disclosure.get("revealed") or []):
        if c.get("schema") != _CLAIM_SCHEMA:
            integrity = False
            continue
        h = _claim_hash(c)
        if h != c.get("claim_hash"):
            integrity = False
        if c.get("parent_bundle_hash") != pbh:
            binding = False
        if h not in leafset:
            membership = False
        if c.get("derivation_id") not in inventory:
            in_inventory = False
    ok &= _chk("revealed_integrity", integrity, "each revealed claim hashes to its claim_hash")
    ok &= _chk("revealed_binding", binding, "each revealed claim binds to the disclosure's bundle")
    ok &= _chk("revealed_membership", membership, "each revealed claim is a committed-set member")
    ok &= _chk("revealed_in_inventory", in_inventory, "each revealed derivation_id is in the inventory")
    return {"ok": bool(ok), "checks": checks, "commitment_root": disclosure.get("commitment_root")}
