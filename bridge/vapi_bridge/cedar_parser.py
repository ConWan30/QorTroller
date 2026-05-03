"""Phase O1 C1 — Cedar bundle parser (FROZEN-v1).

This module implements the FROZEN-v1 Cedar bundle primitive for VAPI's Operator
Agent activation arc. Bundles are JSON-encoded subset-Cedar policy collections
that describe what each operator agent is permitted/forbidden to do at a given
phase (O0 dormant / O1 shadow / O2 suggest / O3 acting). Each phase boundary
is enforced via on-chain bundle Merkle root anchoring through AgentScope +
AgentRegistry contracts (see cedar_bundle_anchor.py).

Frozen primitives (any change requires v2 + new domain tag):
- canonical_bytes(): deterministic JSON encoding (INV-CEDAR-001)
- bundle_merkle_root(): SHA-256 with VAPI-CEDAR-BUNDLE-v1 domain tag (INV-CEDAR-002)
- VALID_EFFECTS / VALID_CATEGORIES / VALID_SCHEMES / VALID_PHASES (INV-CEDAR-003)

Bundle schema (JSON):
    {
      "$schema": "vapi-cedar-bundle-v1",
      "agent_id": "0x..."  (Q9-frozen 32-byte hex),
      "phase": "O0_DORMANT" | "O1_SHADOW" | "O2_SUGGEST" | "O3_ACTING",
      "version": int,
      "issued_at_iso": ISO-8601 timestamp UTC,
      "lane_prefixes": list of strings (per CODEOWNERS lane assignment),
      "policies": list of policy objects:
        {
          "id": "P-NNN" or "F-NNN" (free-form unique within bundle),
          "effect": "permit" | "forbid",
          "principal": {"agentId": "0x..."},
          "action": "<category>:<name>" (category in VALID_CATEGORIES),
          "resource": glob pattern with scheme prefix (lane:// | draft:// | chain:// | *),
          "constraint": optional dict with v1 keys: "shadow_mode": bool
        }

Decision algorithm (Cedar v3 semantics): forbid wins over permit; default deny.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# Domain tag for INV-CEDAR-002 — any change requires v2.
_DOMAIN_TAG = b"VAPI-CEDAR-BUNDLE-v1"

# Frozen enums for INV-CEDAR-003 — any change to these sets is a v2 break.
VALID_EFFECTS    = frozenset({"permit", "forbid"})
VALID_CATEGORIES = frozenset({"skill", "tool", "endpoint"})
VALID_SCHEMES    = frozenset({"lane://", "draft://", "chain://", "*"})
VALID_PHASES     = frozenset({"O0_DORMANT", "O1_SHADOW", "O2_SUGGEST", "O3_ACTING"})


class CedarBundleError(ValueError):
    """Raised on bundle schema or canonicalization errors."""


class CedarDecision(str, Enum):
    """Cedar evaluation outcomes returned by evaluate()."""
    PERMIT                          = "permit"
    PERMIT_WITH_SHADOW_CONSTRAINT   = "permit_with_shadow_constraint"
    FORBID_LANE_VIOLATION           = "forbid_lane_violation"
    FORBID_CAPABILITY_INACTIVE      = "forbid_capability_inactive"
    FORBID_AGENT_NOT_PRINCIPAL      = "forbid_agent_not_principal"
    FORBID_EXPLICIT_POLICY          = "forbid_explicit_policy"
    FORBID_DEFAULT_DENY             = "forbid_default_deny"


@dataclass(slots=True, frozen=True)
class CedarPolicy:
    """One row of a Cedar bundle's policies array."""
    id: str
    effect: str           # "permit" or "forbid"
    principal_agent_id: str  # 0x... hex (32-byte agentId)
    action: str           # "<category>:<name>"
    resource: str         # glob with scheme prefix
    constraint: Optional[dict] = None


@dataclass(slots=True, frozen=True)
class ParsedBundle:
    """Validated bundle ready for evaluate()."""
    agent_id: str                    # 0x... hex (32-byte agentId)
    phase: str                       # one of VALID_PHASES
    version: int
    issued_at_iso: str
    lane_prefixes: tuple[str, ...]   # immutable
    policies: tuple[CedarPolicy, ...]  # immutable
    merkle_root: bytes               # 32 bytes (precomputed)


# ----------------------------------------------------------------------
# FROZEN primitives — any byte change requires v2 + new domain tag.
# ----------------------------------------------------------------------

def canonical_bytes(bundle: dict) -> bytes:
    """INV-CEDAR-001 FROZEN — deterministic JSON encoding for hashing.

    Uses sort_keys=True for cross-Python-version key ordering determinism,
    separators=(",", ":") to strip insignificant whitespace, and
    ensure_ascii=True for OS-agnostic non-ASCII escaping.
    """
    return json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def bundle_merkle_root(bundle: dict) -> bytes:
    """INV-CEDAR-002 FROZEN — SHA-256 with VAPI-CEDAR-BUNDLE-v1 domain tag.

    Domain tag prevents cross-protocol root collision. Returns 32-byte digest
    suitable for AgentScope.setAgentScopeRoot + AgentRegistry.updateAgentScope.
    """
    cb = canonical_bytes(bundle)
    return hashlib.sha256(_DOMAIN_TAG + cb).digest()


# ----------------------------------------------------------------------
# Schema validation + ParsedBundle construction.
# ----------------------------------------------------------------------

def _validate_action(action: str) -> None:
    """Check action follows '<category>:<name>' with category in VALID_CATEGORIES."""
    if not isinstance(action, str) or ":" not in action:
        raise CedarBundleError(f"action must be '<category>:<name>': {action!r}")
    category, _, name = action.partition(":")
    if category not in VALID_CATEGORIES:
        raise CedarBundleError(
            f"action category {category!r} not in VALID_CATEGORIES {sorted(VALID_CATEGORIES)}"
        )
    if not name:
        raise CedarBundleError(f"action name part empty: {action!r}")


def _validate_resource_scheme(resource: str) -> None:
    """Check resource starts with one of VALID_SCHEMES."""
    if not isinstance(resource, str):
        raise CedarBundleError(f"resource must be string: {resource!r}")
    if resource == "*":
        return
    for scheme in VALID_SCHEMES:
        if scheme == "*":
            continue
        if resource.startswith(scheme):
            return
    raise CedarBundleError(
        f"resource scheme not in VALID_SCHEMES {sorted(VALID_SCHEMES)}: {resource!r}"
    )


def _parse_policy(p: dict, idx: int) -> CedarPolicy:
    """Validate one policy dict and return CedarPolicy."""
    if not isinstance(p, dict):
        raise CedarBundleError(f"policies[{idx}] must be dict, got {type(p).__name__}")
    pid = p.get("id")
    if not isinstance(pid, str) or not pid:
        raise CedarBundleError(f"policies[{idx}].id must be non-empty string")
    effect = p.get("effect")
    if effect not in VALID_EFFECTS:
        raise CedarBundleError(
            f"policies[{idx}].effect={effect!r} not in {sorted(VALID_EFFECTS)}"
        )
    principal = p.get("principal")
    if not isinstance(principal, dict):
        raise CedarBundleError(f"policies[{idx}].principal must be dict")
    pa = principal.get("agentId")
    if not isinstance(pa, str) or not pa.startswith("0x") or len(pa) != 66:
        raise CedarBundleError(
            f"policies[{idx}].principal.agentId must be 0x-prefixed 32-byte hex (66 chars)"
        )
    _validate_action(p.get("action", ""))
    _validate_resource_scheme(p.get("resource", ""))
    constraint = p.get("constraint")
    if constraint is not None and not isinstance(constraint, dict):
        raise CedarBundleError(f"policies[{idx}].constraint must be dict or absent")
    return CedarPolicy(
        id=pid,
        effect=effect,
        principal_agent_id=pa,
        action=p["action"],
        resource=p["resource"],
        constraint=constraint,
    )


def parse_bundle(payload: dict) -> ParsedBundle:
    """Validate bundle dict against FROZEN-v1 schema; return ParsedBundle.

    Raises CedarBundleError on any schema violation.
    """
    if not isinstance(payload, dict):
        raise CedarBundleError(f"bundle must be dict, got {type(payload).__name__}")
    schema = payload.get("$schema")
    if schema != "vapi-cedar-bundle-v1":
        raise CedarBundleError(
            f"$schema must be 'vapi-cedar-bundle-v1', got {schema!r}"
        )
    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id.startswith("0x") or len(agent_id) != 66:
        raise CedarBundleError("agent_id must be 0x-prefixed 32-byte hex (66 chars)")
    phase = payload.get("phase")
    if phase not in VALID_PHASES:
        raise CedarBundleError(
            f"phase={phase!r} not in {sorted(VALID_PHASES)}"
        )
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        raise CedarBundleError(f"version must be positive int, got {version!r}")
    issued_at_iso = payload.get("issued_at_iso")
    if not isinstance(issued_at_iso, str) or not issued_at_iso:
        raise CedarBundleError("issued_at_iso must be non-empty ISO-8601 string")
    lane_prefixes = payload.get("lane_prefixes")
    if not isinstance(lane_prefixes, list) or not all(isinstance(s, str) for s in lane_prefixes):
        raise CedarBundleError("lane_prefixes must be list of strings")
    policies = payload.get("policies")
    if not isinstance(policies, list):
        raise CedarBundleError("policies must be list")
    parsed_policies = tuple(_parse_policy(p, i) for i, p in enumerate(policies))
    # Cross-policy integrity: principal.agentId must match top-level agent_id
    for i, pol in enumerate(parsed_policies):
        if pol.principal_agent_id != agent_id:
            raise CedarBundleError(
                f"policies[{i}].principal.agentId={pol.principal_agent_id!r} "
                f"does not match bundle.agent_id={agent_id!r}"
            )
    return ParsedBundle(
        agent_id=agent_id,
        phase=phase,
        version=version,
        issued_at_iso=issued_at_iso,
        lane_prefixes=tuple(lane_prefixes),
        policies=parsed_policies,
        merkle_root=bundle_merkle_root(payload),
    )


# ----------------------------------------------------------------------
# Decision algorithm (Cedar v3 semantics): forbid wins; default deny.
# ----------------------------------------------------------------------

def _resource_matches(policy_resource: str, request_resource: str) -> bool:
    """Glob-style match of request_resource against policy_resource pattern.

    Patterns:
      "*"                — match anything
      "lane://prefix/**" — match anything starting with "lane://prefix/"
      "lane://prefix/*"  — match one path segment after "lane://prefix/"
      "draft://name/*"   — match draft path
      exact string       — exact match
    """
    if policy_resource == "*":
        return True
    if policy_resource.endswith("/**"):
        return request_resource.startswith(policy_resource[:-2])
    if policy_resource.endswith("/*"):
        prefix = policy_resource[:-1]
        if not request_resource.startswith(prefix):
            return False
        rest = request_resource[len(prefix):]
        return "/" not in rest
    return policy_resource == request_resource


def _lane_violation(bundle: ParsedBundle, request_resource: str) -> bool:
    """Check if request_resource lies outside the bundle's lane_prefixes."""
    if not request_resource.startswith("lane://"):
        return False
    after_scheme = request_resource[len("lane://"):]
    return not any(after_scheme.startswith(prefix) for prefix in bundle.lane_prefixes)


def evaluate(
    bundle: ParsedBundle,
    *,
    agent_id: str,
    action: str,
    resource: str,
    context: Optional[dict] = None,
) -> CedarDecision:
    """Cedar decision algorithm. Forbid wins over permit; default deny.

    Args:
        bundle:    Parsed bundle (output of parse_bundle).
        agent_id:  Requesting agent (must equal bundle.agent_id; cross-agent denied).
        action:    Requested action ("category:name").
        resource:  Requested resource (glob-matched against policy resources).
        context:   Optional dict of runtime context. Recognized v1 keys:
                     - "shadow_mode": bool — required True when policy has
                       constraint={"shadow_mode": true}; otherwise the policy
                       returns FORBID_DEFAULT_DENY (constraint not satisfied).

    Returns:
        CedarDecision enum value.
    """
    # Cross-agent denial: bundle is for one agent only.
    if agent_id != bundle.agent_id:
        return CedarDecision.FORBID_AGENT_NOT_PRINCIPAL

    # Lane violation check (only applies to lane:// resources).
    if _lane_violation(bundle, resource):
        return CedarDecision.FORBID_LANE_VIOLATION

    ctx = context or {}
    permit_match: Optional[CedarPolicy] = None
    forbid_match: Optional[CedarPolicy] = None

    for pol in bundle.policies:
        # Action and resource must match.
        if pol.action != action:
            continue
        if not _resource_matches(pol.resource, resource):
            continue
        # If constraint present, require all keys satisfied by context.
        if pol.constraint:
            if not all(ctx.get(k) == v for k, v in pol.constraint.items()):
                # constraint not satisfied — policy doesn't apply
                continue
        if pol.effect == "forbid":
            forbid_match = pol
            break  # forbid wins immediately
        elif pol.effect == "permit":
            permit_match = pol
            # don't break — keep scanning for explicit forbid

    if forbid_match is not None:
        return CedarDecision.FORBID_EXPLICIT_POLICY
    if permit_match is not None:
        if permit_match.constraint and permit_match.constraint.get("shadow_mode") is True:
            return CedarDecision.PERMIT_WITH_SHADOW_CONSTRAINT
        return CedarDecision.PERMIT

    # Default deny per Cedar v3 semantics.
    return CedarDecision.FORBID_DEFAULT_DENY
