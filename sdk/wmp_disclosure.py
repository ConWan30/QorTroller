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


# ── SD-2: Merkle-tree upgrade — hide hidden leaves, log-N inclusion proofs ──
#
# SD-1 revealed every leaf hash (the flat envelope). SD-2 commits via a binary
# Merkle tree, so the disclosure carries only the root + a per-revealed-claim
# inclusion proof (≈ log₂N sibling hashes) — proof size scales with log N, not N,
# and MOST hidden claims' leaf hashes stay hidden.
# Honest caveat: a revealed claim's leaf-level Merkle SIBLING hash is exposed by
# its proof (inherent to Merkle inclusion) — so revealing k of N leaks ≤ k sibling
# leaf-hashes, never all N. VALUES are ALWAYS hidden. Same ceiling as SD-1: proves
# membership + binding in an IMMUTABLE committed structure (the commitment must
# have been published/anchored ahead of the reveal), never hidden values or ZK.

SCHEMA_V2 = "vapi-wmp-disclosure-v2"


def _h(*hexes: str) -> str:
    m = hashlib.sha256()
    for x in hexes:
        m.update(bytes.fromhex(x))
    return m.hexdigest()


def _merkle_leaf(claim_hash: str) -> str:
    """Domain-tagged leaf commitment for a claim (distinct from an interior node)."""
    return hashlib.sha256(("VAPI-WMP-DISCLOSURE-v2|leaf|" + claim_hash).encode("utf-8")).hexdigest()


def _merkle_layers(leaves: list) -> list:
    """Bottom-up layers over SORTED leaves; duplicate-last on odd counts."""
    layers = [list(leaves)]
    cur = list(leaves)
    while len(cur) > 1:
        nxt = []
        for i in range(0, len(cur), 2):
            a = cur[i]
            b = cur[i + 1] if i + 1 < len(cur) else cur[i]
            nxt.append(_h(a, b))
        layers.append(nxt)
        cur = nxt
    return layers


def _inclusion_proof(layers: list, index: int) -> list:
    proof = []
    idx = index
    for layer in layers[:-1]:
        sib = idx ^ 1
        sib_hash = layer[sib] if sib < len(layer) else layer[idx]
        proof.append({"hash": sib_hash, "sibling_left": (idx % 2 == 1)})
        idx //= 2
    return proof


def _verify_inclusion(leaf: str, proof: list, root: str) -> bool:
    h = leaf
    for step in proof:
        h = _h(step["hash"], h) if step.get("sibling_left") else _h(h, step["hash"])
    return h == root


def _v2_commitment(parent_bundle_hash, set_size, inventory, merkle_root) -> str:
    payload = "|".join([SCHEMA_V2, str(parent_bundle_hash), str(set_size),
                        ",".join(sorted(inventory)), str(merkle_root)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_merkle_disclosure(claims: list, reveal_ids=None) -> dict:
    """SD-2: commit via a Merkle tree; each revealed claim carries a log-N
    inclusion proof and hidden leaves are not disclosed."""
    if not claims:
        raise ValueError("no claims to disclose")
    pbh = claims[0].get("parent_bundle_hash")
    for c in claims:
        if c.get("schema") != _CLAIM_SCHEMA:
            raise ValueError(f"not a VDC claim: schema={c.get('schema')!r}")
        if c.get("parent_bundle_hash") != pbh:
            raise ValueError("all claims must bind to the same parent bundle")
    leaf_of = {c["derivation_id"]: _merkle_leaf(_claim_hash(c)) for c in claims}
    sorted_leaves = sorted(leaf_of.values())
    layers = _merkle_layers(sorted_leaves)
    merkle_root = layers[-1][0]
    inventory = sorted(c["derivation_id"] for c in claims)
    want = set(inventory) if reveal_ids is None else set(reveal_ids)
    revealed = []
    for c in claims:
        if c.get("derivation_id") not in want:
            continue
        idx = sorted_leaves.index(leaf_of[c["derivation_id"]])
        revealed.append({"claim": c, "inclusion_proof": _inclusion_proof(layers, idx)})
    return {
        "schema": SCHEMA_V2,
        "parent_bundle_hash": pbh,
        "set_size": len(claims),
        "derivation_inventory": inventory,
        "merkle_root": merkle_root,
        "commitment_root": _v2_commitment(pbh, len(claims), inventory, merkle_root),
        "revealed": revealed,          # each = {claim, inclusion_proof}; NO full leaf list
    }


def verify_merkle_disclosure(disclosure: dict) -> dict:
    """Fail-closed SD-2 verify: header commitment recomputes, and every revealed
    claim hashes to its claim_hash, binds to the bundle, and its Merkle inclusion
    proof reaches the committed root."""
    checks: list = []

    def _chk(name, ok, note=""):
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return bool(ok)

    ok = _chk("schema", disclosure.get("schema") == SCHEMA_V2, f"schema={disclosure.get('schema')!r}")
    pbh = disclosure.get("parent_bundle_hash")
    inventory = list(disclosure.get("derivation_inventory") or [])
    mroot = disclosure.get("merkle_root")
    ok &= _chk("inventory_size", len(inventory) == disclosure.get("set_size"),
               "inventory count == set_size")
    ok &= _chk("commitment_root",
               disclosure.get("commitment_root") == _v2_commitment(pbh, disclosure.get("set_size"), inventory, mroot),
               "header commitment recomputes over bundle + size + inventory + merkle_root")
    integrity = binding = membership = in_inventory = True
    for item in (disclosure.get("revealed") or []):
        c = item.get("claim") or {}
        proof = item.get("inclusion_proof") or []
        if c.get("schema") != _CLAIM_SCHEMA:
            integrity = False
            continue
        h = _claim_hash(c)
        if h != c.get("claim_hash"):
            integrity = False
        if c.get("parent_bundle_hash") != pbh:
            binding = False
        if c.get("derivation_id") not in inventory:
            in_inventory = False
        if not _verify_inclusion(_merkle_leaf(h), proof, mroot):
            membership = False
    ok &= _chk("revealed_integrity", integrity, "each revealed claim hashes to its claim_hash")
    ok &= _chk("revealed_binding", binding, "each revealed claim binds to the disclosure's bundle")
    ok &= _chk("revealed_membership", membership, "each revealed claim's Merkle proof reaches the root")
    ok &= _chk("revealed_in_inventory", in_inventory, "each revealed derivation_id is in the inventory")
    return {"ok": bool(ok), "checks": checks, "commitment_root": disclosure.get("commitment_root")}
