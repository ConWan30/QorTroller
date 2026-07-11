"""WMP ZK Property Proof (ZKP-1) — the ceremony-gated rung above selective
disclosure: prove a VDC claim's value satisfies a PREDICATE (e.g. value ≥
threshold) WITHOUT revealing the value.

This is the "withhold + prove" rung. A real zero-knowledge proof needs a circuit
+ trusted-setup ceremony (the Arc 5 Groth16 precedent). Until that lands, this
module builds the request/record STRUCTURE and returns an HONEST DEFERRAL through
a DeferredProver — it NEVER emits a fake proof (the Arc 5 DeferredProver honesty
rail). The moment a circuit + ceremony are wired, a real Prover drops in behind
the same interface and records flip from DEFERRED to PROVEN.

Ceiling: v0 defines the property-proof envelope + honest deferral. It produces NO
zero-knowledge proof and asserts NO property until a circuit + ceremony exist.
The public REQUEST carries the STATEMENT (which claim, which field, predicate,
public threshold) but NEVER the secret field value.
"""
from __future__ import annotations

from typing import Optional, Protocol

from sdk.wmp_derived import SCHEMA as _CLAIM_SCHEMA

SCHEMA = "vapi-wmp-zk-property-v1"

# Frozen predicate enum — part of the proof statement.
PREDICATES = ("GTE", "LTE", "EQ")

OUTCOME_PROVEN = "PROVEN"
OUTCOME_DEFERRED = "DEFERRED"     # honest no-op: no ceremony yet (NOT pass, NOT fail)
OUTCOME_REJECTED = "REJECTED"


def _resolve_field(value: dict, field_path: str):
    """Read a dotted path out of a claim's value (e.g. 'fraction' or
    'per_channel.button_mask.entropy_millibits'). Raises if absent."""
    cur = value
    for part in field_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(f"field {field_path!r} not found at {part!r}")
        cur = cur[part]
    return cur


def build_property_request(claim: dict, field_path: str, predicate: str, threshold) -> dict:
    """The public STATEMENT to prove in zero-knowledge — 'the claim bound to
    parent_bundle_hash, derivation D, has value.<field> <predicate> <threshold>' —
    WITHOUT revealing the field value. The value is confirmed to EXIST (well-formed
    statement) but is not placed in the request."""
    if claim.get("schema") != _CLAIM_SCHEMA:
        raise ValueError(f"not a VDC claim: {claim.get('schema')!r}")
    if predicate not in PREDICATES:
        raise ValueError(f"unknown predicate {predicate!r}; frozen: {PREDICATES}")
    _resolve_field(claim.get("value") or {}, field_path)   # statement must be well-formed
    return {
        "schema": SCHEMA,
        "claim_hash": claim.get("claim_hash"),
        "parent_bundle_hash": claim.get("parent_bundle_hash"),
        "derivation_id": claim.get("derivation_id"),
        "field_path": field_path,
        "predicate": predicate,
        "threshold": threshold,        # PUBLIC part of the statement; value stays secret
    }


class Prover(Protocol):
    """A ZK prover: given the public request + the secret claim, emit proof bytes,
    or None if it cannot (honest deferral)."""

    def prove(self, request: dict, claim: dict) -> Optional[str]:
        ...


class DeferredProver:
    """The honesty rail: no circuit + ceremony yet → no proof → returns None.
    Never fabricates. Drop-in replaceable by a real Groth16 prover post-ceremony."""

    reason = "ZK circuit + trusted-setup ceremony not yet wired (Arc 5 precedent)"

    def prove(self, request: dict, claim: dict) -> Optional[str]:
        return None


def build_property_proof(claim: dict, field_path: str, predicate: str, threshold,
                         prover: Optional[Prover] = None) -> dict:
    """Build the property-proof record. With DeferredProver (default) it ships
    DEFERRED honestly (proof_hex=None); with a real prover it carries proof bytes."""
    prover = prover if prover is not None else DeferredProver()
    request = build_property_request(claim, field_path, predicate, threshold)
    proof_hex = prover.prove(request, claim)
    return {
        "schema": SCHEMA,
        "request": request,
        "proof_hex": proof_hex,                    # None until a ceremony-backed prover exists
        "deferred": proof_hex is None,
        "prover": type(prover).__name__,
        "deferred_reason": getattr(prover, "reason", "") if proof_hex is None else "",
    }


def verify_property_proof(record: dict, zk_verify=None) -> dict:
    """Fail-closed. A DEFERRED record (no proof) is reported as DEFERRED — NOT pass,
    NOT fail; a consumer must never treat a deferral as a proven property. A present
    proof is verified by the injected `zk_verify(request, proof_hex) -> bool` (the
    snarkjs / on-chain verifier, post-ceremony); with no verifier a present proof is
    itself DEFERRED (cannot confirm without the ceremony verifier)."""
    checks: list = []

    def _chk(name, ok, note=""):
        checks.append({"name": name, "ok": bool(ok), "note": note})
        return bool(ok)

    struct_ok = _chk("schema", record.get("schema") == SCHEMA, f"schema={record.get('schema')!r}")
    req = record.get("request") or {}
    struct_ok &= _chk("request_schema", req.get("schema") == SCHEMA)
    struct_ok &= _chk("predicate", req.get("predicate") in PREDICATES, f"predicate={req.get('predicate')!r}")
    if not struct_ok:
        return {"outcome": OUTCOME_REJECTED, "checks": checks}

    if record.get("proof_hex") is None:
        return {"outcome": OUTCOME_DEFERRED, "checks": checks,
                "note": record.get("deferred_reason") or "no ZK proof present — ceremony not yet run"}
    if zk_verify is None:
        return {"outcome": OUTCOME_DEFERRED, "checks": checks,
                "note": "proof present but no ZK verifier injected — ceremony verifier required to confirm"}
    try:
        ok = bool(zk_verify(req, record["proof_hex"]))
    except Exception as exc:  # noqa: BLE001 — a failing verifier is a FAIL, never a silent pass
        return {"outcome": OUTCOME_REJECTED, "checks": checks, "note": f"zk_verify raised: {exc}"}
    _chk("zk_proof", ok, "injected ZK verifier verdict")
    return {"outcome": OUTCOME_PROVEN if ok else OUTCOME_REJECTED, "checks": checks}
