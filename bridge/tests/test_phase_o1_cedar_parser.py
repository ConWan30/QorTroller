"""Phase O1 C1 — cedar_parser.py tests.

T-O1-CP-1   canonical_bytes determinism — insertion-order independence
T-O1-CP-2   bundle_merkle_root domain tag binding — 1-byte change differs
T-O1-CP-3   parse_bundle accepts schema-valid v1 bundle
T-O1-CP-4   parse_bundle rejects unknown $schema
T-O1-CP-5   evaluate forbid wins over permit (Cedar v3 semantics)
T-O1-CP-6   evaluate lane-prefix violation rejected
T-O1-CP-7   evaluate shadow constraint requires context.shadow_mode=True
T-O1-CP-8   parse_bundle invalid input — missing/bad fields raise CedarBundleError
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from vapi_bridge.cedar_parser import (
    CedarBundleError,
    CedarDecision,
    bundle_merkle_root,
    canonical_bytes,
    evaluate,
    parse_bundle,
)


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"


def _minimal_bundle():
    return {
        "$schema": "vapi-cedar-bundle-v1",
        "agent_id": SENTRY_ID,
        "phase": "O1_SHADOW",
        "version": 1,
        "issued_at_iso": "2026-05-03T22:00:00Z",
        "lane_prefixes": ["wiki/"],
        "policies": [
            {
                "id": "P-001",
                "effect": "permit",
                "principal": {"agentId": SENTRY_ID},
                "action": "skill:read",
                "resource": "lane://wiki/**",
            },
        ],
    }


# ----------------------------------------------------------------------
# T-O1-CP-1 — canonical_bytes determinism
# ----------------------------------------------------------------------
def test_t_o1_cp_1_canonical_bytes_determinism():
    """Same dict in different key-insertion order produces same canonical bytes."""
    a = {"version": 1, "agent_id": SENTRY_ID, "phase": "O1_SHADOW", "lane_prefixes": ["wiki/"]}
    b = {"lane_prefixes": ["wiki/"], "phase": "O1_SHADOW", "agent_id": SENTRY_ID, "version": 1}
    assert canonical_bytes(a) == canonical_bytes(b)


# ----------------------------------------------------------------------
# T-O1-CP-2 — bundle_merkle_root domain tag binding
# ----------------------------------------------------------------------
def test_t_o1_cp_2_merkle_root_changes_on_byte_diff():
    """1-byte change in any field changes the Merkle root."""
    b1 = _minimal_bundle()
    b2 = _minimal_bundle()
    b2["version"] = 2
    r1 = bundle_merkle_root(b1)
    r2 = bundle_merkle_root(b2)
    assert r1 != r2
    assert len(r1) == 32 and len(r2) == 32


# ----------------------------------------------------------------------
# T-O1-CP-3 — parse_bundle accepts schema-valid v1
# ----------------------------------------------------------------------
def test_t_o1_cp_3_parse_bundle_accepts_valid():
    parsed = parse_bundle(_minimal_bundle())
    assert parsed.agent_id == SENTRY_ID
    assert parsed.phase == "O1_SHADOW"
    assert parsed.version == 1
    assert parsed.lane_prefixes == ("wiki/",)
    assert len(parsed.policies) == 1
    assert parsed.policies[0].effect == "permit"
    assert isinstance(parsed.merkle_root, bytes)
    assert len(parsed.merkle_root) == 32


# ----------------------------------------------------------------------
# T-O1-CP-4 — parse_bundle rejects unknown $schema
# ----------------------------------------------------------------------
def test_t_o1_cp_4_parse_bundle_rejects_unknown_schema():
    bundle = _minimal_bundle()
    bundle["$schema"] = "vapi-cedar-bundle-v999"
    with pytest.raises(CedarBundleError, match="schema"):
        parse_bundle(bundle)


# ----------------------------------------------------------------------
# T-O1-CP-5 — evaluate: forbid wins over permit
# ----------------------------------------------------------------------
def test_t_o1_cp_5_forbid_wins_over_permit():
    bundle = _minimal_bundle()
    bundle["policies"].append({
        "id": "F-001",
        "effect": "forbid",
        "principal": {"agentId": SENTRY_ID},
        "action": "skill:read",
        "resource": "lane://wiki/**",
    })
    parsed = parse_bundle(bundle)
    decision = evaluate(parsed, agent_id=SENTRY_ID, action="skill:read", resource="lane://wiki/page1.md")
    assert decision == CedarDecision.FORBID_EXPLICIT_POLICY


# ----------------------------------------------------------------------
# T-O1-CP-6 — evaluate: lane-prefix violation
# ----------------------------------------------------------------------
def test_t_o1_cp_6_lane_violation():
    parsed = parse_bundle(_minimal_bundle())  # only "wiki/" lane
    decision = evaluate(parsed, agent_id=SENTRY_ID, action="skill:read", resource="lane://audits/foo.md")
    assert decision == CedarDecision.FORBID_LANE_VIOLATION


# ----------------------------------------------------------------------
# T-O1-CP-7 — evaluate: shadow constraint binding
# ----------------------------------------------------------------------
def test_t_o1_cp_7_shadow_constraint():
    bundle = _minimal_bundle()
    bundle["policies"].append({
        "id": "P-002",
        "effect": "permit",
        "principal": {"agentId": SENTRY_ID},
        "action": "tool:kms-sign",
        "resource": "draft://shadow_log/*",
        "constraint": {"shadow_mode": True},
    })
    parsed = parse_bundle(bundle)
    # WITH context.shadow_mode=True → permit_with_shadow_constraint
    d_permit = evaluate(
        parsed, agent_id=SENTRY_ID, action="tool:kms-sign",
        resource="draft://shadow_log/draft1", context={"shadow_mode": True},
    )
    assert d_permit == CedarDecision.PERMIT_WITH_SHADOW_CONSTRAINT
    # WITHOUT shadow_mode=True → constraint not satisfied → default deny
    d_deny = evaluate(
        parsed, agent_id=SENTRY_ID, action="tool:kms-sign",
        resource="draft://shadow_log/draft1", context={"shadow_mode": False},
    )
    assert d_deny == CedarDecision.FORBID_DEFAULT_DENY
    # No context at all → default deny
    d_no_ctx = evaluate(
        parsed, agent_id=SENTRY_ID, action="tool:kms-sign",
        resource="draft://shadow_log/draft1", context=None,
    )
    assert d_no_ctx == CedarDecision.FORBID_DEFAULT_DENY


# ----------------------------------------------------------------------
# T-O1-CP-8 — parse_bundle invalid input rejected (multiple cases)
# ----------------------------------------------------------------------
def test_t_o1_cp_8_invalid_input_rejected():
    base = _minimal_bundle()
    # Non-dict
    with pytest.raises(CedarBundleError):
        parse_bundle("not a dict")
    # Missing required field
    bad = base.copy()
    del bad["agent_id"]
    with pytest.raises(CedarBundleError, match="agent_id"):
        parse_bundle(bad)
    # Invalid effect
    bad = _minimal_bundle()
    bad["policies"][0]["effect"] = "invalid_effect"
    with pytest.raises(CedarBundleError, match="effect"):
        parse_bundle(bad)
    # Invalid action category
    bad = _minimal_bundle()
    bad["policies"][0]["action"] = "garbage:read"
    with pytest.raises(CedarBundleError, match="category"):
        parse_bundle(bad)
    # Cross-agent agentId in policy
    bad = _minimal_bundle()
    bad["policies"][0]["principal"]["agentId"] = "0x" + "f" * 64
    with pytest.raises(CedarBundleError, match="agent_id"):
        parse_bundle(bad)
    # Invalid phase
    bad = _minimal_bundle()
    bad["phase"] = "O99_INVALID"
    with pytest.raises(CedarBundleError, match="phase"):
        parse_bundle(bad)
