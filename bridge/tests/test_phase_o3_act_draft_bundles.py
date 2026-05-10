"""Phase O3-ACT-DRAFT — pre-anchor validation tests for O3 ACTING bundles.

Locks the three O3 ACTING bundles (Sentry + Guardian + Curator) into CI so future
contributors can't regress them silently. Pairs with the C7 V&V CLI tooling — same
contracts but tested as data, not as CLI invocation.

These bundles are pre-validated authoring artifacts. They will become the input to a
future triple-dual-anchor cycle (parallel_o3_act_anchor.py, mirroring Phase O1-FRR
Stream E parallel_o2_anchor.py) when:
  - Sentry shadow_age >= 504h AND draft_payload_count >= 50 AND op_disagreement_30d < 5%
    AND kms_hsm_production_ready
  - Guardian: same + github_app_oauth_tokens_valid
  - Curator: 504h + draft_review_count >= 50 + false_positive_rate_30d == 0
    + marketplace_curator_role_assigned (setCurator() on VAPIDataMarketplaceListings.sol)

Until then they sit on disk as verified candidates with locked Merkle roots.
"""

import json
import sys
import types as _types
from pathlib import Path

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"
GUARDIAN_ID = "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1"
CURATOR_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"

BUNDLES_DIR = BRIDGE_DIR / "vapi_bridge" / "cedar_bundles"
SENTRY_O2 = BUNDLES_DIR / "anchor_sentry_o2_suggest_v1.json"
GUARDIAN_O2 = BUNDLES_DIR / "guardian_o2_suggest_v1.json"
CURATOR_O2 = BUNDLES_DIR / "curator_o2_suggest_v1.json"

SENTRY_O3 = BUNDLES_DIR / "anchor_sentry_o3_acting_v1.json"
GUARDIAN_O3 = BUNDLES_DIR / "guardian_o3_acting_v1.json"
CURATOR_O3 = BUNDLES_DIR / "curator_o3_acting_v1.json"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _permits_for_action(parsed, action: str) -> list:
    return [p for p in parsed.policies if p.effect == "permit" and p.action == action]


def _forbids_for_action(parsed, action: str) -> list:
    return [p for p in parsed.policies if p.effect == "forbid" and p.action == action]


# ---------------------------------------------------------------------------
# T-O3-ACT-DRAFT-1: all three O3 ACTING bundle files exist and parse cleanly,
#                    Merkle round-trip matches, agent_ids and phase frozen
# ---------------------------------------------------------------------------

def test_t_o3_act_draft_1_three_bundles_valid():
    from vapi_bridge.cedar_parser import parse_bundle, bundle_merkle_root

    for path, expected_id in (
        (SENTRY_O3, SENTRY_ID),
        (GUARDIAN_O3, GUARDIAN_ID),
        (CURATOR_O3, CURATOR_ID),
    ):
        assert path.exists(), f"O3 ACTING bundle missing at {path}"
        raw = _load(path)
        parsed = parse_bundle(raw)
        # Phase MUST be O3_ACTING (canonical Cedar VALID_PHASES string)
        assert parsed.phase == "O3_ACTING", \
            f"{path.name}: expected phase=O3_ACTING, got {parsed.phase!r}"
        # agent_id MUST match the on-chain Q9-frozen identifier
        assert parsed.agent_id == expected_id, \
            f"{path.name}: agent_id mismatch {parsed.agent_id} vs {expected_id}"
        # Merkle root deterministic round-trip
        assert parsed.merkle_root == bundle_merkle_root(raw)
        # Merkle root non-zero (otherwise canonicalization broke)
        assert parsed.merkle_root != b"\x00" * 32


# ---------------------------------------------------------------------------
# T-O3-ACT-DRAFT-2: O3 ACTING capability lift matrix — specific resource paths
#                    transition draft://* -> lane://* relative to O2 SUGGEST
# ---------------------------------------------------------------------------

def test_t_o3_act_draft_2_capability_lift_matrix():
    """Per the Phase O2-SUGGEST -> O3-ACTING activation matrix:

    SENTRY:
      pda-attestation-anchor:    draft://attestations/* -> lane://provenance/**
      ipfs-pin:                  draft://attestations/* -> lane://provenance/**
      provenance-recording:      draft://attestations/* (O2 had draft already)
                                                          -> lane://provenance/**

    GUARDIAN:
      audit-drafting:            draft://audit_entries/* -> lane://audits/**
      operational-diagnostic:    draft://audit_entries/* -> lane://ops/**
      audit-entry-draft:         draft://audit_entries/* -> lane://audits/**
      ipfs-pin:                  draft://audit_entries/* -> lane://audits/**

    CURATOR:
      marketplace-listing-review: draft://listing_reviews/* -> lane://marketplace/**
      NEW PERMIT:                 marketplace-listing-suspend on chain://iotex-testnet
                                  (the headline O3 ACT authority for Curator;
                                   setCurator() role on VAPIDataMarketplaceListings.sol)
    """
    from vapi_bridge.cedar_parser import parse_bundle

    sentry = parse_bundle(_load(SENTRY_O3))
    guardian = parse_bundle(_load(GUARDIAN_O3))
    curator = parse_bundle(_load(CURATOR_O3))

    # Sentry: pda-attestation-anchor and ipfs-pin both write to lane://provenance/**
    pda = _permits_for_action(sentry, "tool:pda-attestation-anchor")
    assert any(p.resource == "lane://provenance/**" for p in pda), \
        "Sentry O3 must lift pda-attestation-anchor to lane://provenance/**"
    sentry_ipfs = _permits_for_action(sentry, "tool:ipfs-pin")
    assert any(p.resource == "lane://provenance/**" for p in sentry_ipfs), \
        "Sentry O3 must lift ipfs-pin to lane://provenance/**"
    sentry_prov = _permits_for_action(sentry, "skill:provenance-recording")
    assert any(p.resource == "lane://provenance/**" for p in sentry_prov), \
        "Sentry O3 must lift provenance-recording to lane://provenance/**"

    # Guardian: audit-drafting writes to lane://audits/**, operational-diagnostic to lane://ops/**
    g_audit = _permits_for_action(guardian, "skill:audit-drafting")
    assert any(p.resource == "lane://audits/**" for p in g_audit), \
        "Guardian O3 must lift audit-drafting to lane://audits/**"
    g_ops = _permits_for_action(guardian, "skill:operational-diagnostic")
    assert any(p.resource == "lane://ops/**" for p in g_ops), \
        "Guardian O3 must lift operational-diagnostic to lane://ops/**"
    g_ipfs = _permits_for_action(guardian, "tool:ipfs-pin")
    assert any(p.resource == "lane://audits/**" for p in g_ipfs), \
        "Guardian O3 must lift ipfs-pin to lane://audits/**"

    # Curator: marketplace-listing-review writes verdicts to live marketplace lane
    c_review = _permits_for_action(curator, "skill:marketplace-listing-review")
    assert any(p.resource == "lane://marketplace/**" for p in c_review), \
        "Curator O3 must lift marketplace-listing-review to lane://marketplace/**"
    # Curator NEW O3 permit: marketplace-listing-suspend on chain://iotex-testnet
    c_suspend = _permits_for_action(curator, "tool:marketplace-listing-suspend")
    assert len(c_suspend) >= 1, "Curator O3 must permit tool:marketplace-listing-suspend"
    assert any(p.resource == "chain://iotex-testnet" for p in c_suspend), \
        "Curator O3 marketplace-listing-suspend must target chain://iotex-testnet"


# ---------------------------------------------------------------------------
# T-O3-ACT-DRAFT-3: cross-fleet skill-separation invariant preserved at O3.
#                    Each agent FORBIDS every action exclusive to the other agents.
# ---------------------------------------------------------------------------

def test_t_o3_act_draft_3_cross_agent_skill_separation_preserved():
    """The CFSS invariant that justifies a >=3-agent fleet must HOLD at O3.

    Sentry-exclusive:    tool:pda-attestation-anchor, skill:event-correlation, skill:provenance-recording
    Guardian-exclusive:  skill:audit-drafting, skill:operational-diagnostic
    Curator-exclusive:   skill:marketplace-listing-review, tool:marketplace-listing-suspend

    Each agent's O3 bundle must contain `forbid` policies for every action
    exclusive to the other two agents. tool:git-push is forbidden across ALL
    three (PR-merge-only invariant).
    """
    from vapi_bridge.cedar_parser import parse_bundle

    sentry = parse_bundle(_load(SENTRY_O3))
    guardian = parse_bundle(_load(GUARDIAN_O3))
    curator = parse_bundle(_load(CURATOR_O3))

    # Sentry forbids Guardian-exclusive + Curator-exclusive actions
    for forbidden_action in (
        "skill:audit-drafting",
        "skill:operational-diagnostic",
        "skill:marketplace-listing-review",
        "tool:marketplace-listing-suspend",
    ):
        assert _forbids_for_action(sentry, forbidden_action), \
            f"Sentry O3 missing forbid for {forbidden_action} (CFSS violation)"

    # Guardian forbids Sentry-exclusive + Curator-exclusive actions
    for forbidden_action in (
        "tool:pda-attestation-anchor",
        "skill:event-correlation",
        "skill:provenance-recording",
        "skill:marketplace-listing-review",
        "tool:marketplace-listing-suspend",
    ):
        assert _forbids_for_action(guardian, forbidden_action), \
            f"Guardian O3 missing forbid for {forbidden_action} (CFSS violation)"

    # Curator forbids Sentry-exclusive + Guardian-exclusive actions
    for forbidden_action in (
        "tool:pda-attestation-anchor",
        "skill:event-correlation",
        "skill:provenance-recording",
        "skill:audit-drafting",
        "skill:operational-diagnostic",
    ):
        assert _forbids_for_action(curator, forbidden_action), \
            f"Curator O3 missing forbid for {forbidden_action} (CFSS violation)"

    # tool:git-push FOREVER forbidden across all three (PR-merge-only invariant;
    # never lifts at any phase)
    for parsed, label in ((sentry, "Sentry"), (guardian, "Guardian"), (curator, "Curator")):
        assert _forbids_for_action(parsed, "tool:git-push"), \
            f"{label} O3 missing forbid for tool:git-push (PR-merge-only invariant)"

    # endpoint:write FOREVER forbidden across all three (specific tool: actions
    # are the only write paths, never raw HTTP)
    for parsed, label in ((sentry, "Sentry"), (guardian, "Guardian"), (curator, "Curator")):
        assert _forbids_for_action(parsed, "endpoint:write"), \
            f"{label} O3 missing forbid for endpoint:write"

    # Curator-specific: kms-sign on validation_record/* FOREVER forbidden
    # (tournament gate validation_records require Sentry+Guardian co-sign,
    #  never Curator). Preserved across O0/O1/O2/O3.
    c_kms_forbids = _forbids_for_action(curator, "tool:kms-sign")
    assert any(p.resource == "draft://validation_record/*" for p in c_kms_forbids), \
        "Curator O3 missing forbid for tool:kms-sign on draft://validation_record/*"


# ---------------------------------------------------------------------------
# T-O3-ACT-DRAFT-4: O3 Merkle roots locked, distinct from O2 siblings, frozen
#                    pre-anchor (any policy edit re-anchors to a new root by design)
# ---------------------------------------------------------------------------

def test_t_o3_act_draft_4_merkle_roots_locked_and_distinct():
    """The three O3 ACTING bundle Merkle roots are pre-anchor frozen at draft time.
    Future policy edits (e.g. lifting a forbid) MUST re-anchor to a new Merkle root
    by design — that is the governance gate. This test pins the current values
    so a silent edit fails CI.

    These exact 32-byte hex strings will be the inputs to parallel_o3_act_anchor.py
    when the operator authorizes the triple dual-anchor cycle.
    """
    from vapi_bridge.cedar_parser import parse_bundle, bundle_merkle_root

    expected_merkles = {
        "anchor_sentry_o3_acting_v1.json":
            "0xc0bcdee8576e83f6b80e8c5ac89093cf08f153033037176cd03fc34fcedfd878",
        "guardian_o3_acting_v1.json":
            "0x6f0fc77cc1dacaf3f79aeb0f27dd8c7b3d88e95b236f0806ad3588a06bb82225",
        "curator_o3_acting_v1.json":
            "0xd9d760c8b7b1088f2edd165fbfa6441abcb3bc3f921e8ba75a3339c0825fec24",
    }

    for fname, expected_hex in expected_merkles.items():
        path = BUNDLES_DIR / fname
        raw = _load(path)
        parsed = parse_bundle(raw)
        actual_hex = "0x" + parsed.merkle_root.hex()
        assert actual_hex == expected_hex, (
            f"{fname}: Merkle root drift\n"
            f"  expected={expected_hex}\n"
            f"  actual=  {actual_hex}\n"
            "If this is intentional (policy edit), update the expected value here AND "
            "in CLAUDE.md notes referencing the locked O3 ACTING Merkle roots."
        )

    # Pairs check: each O3 root distinct from its O2 sibling
    o2_o3_pairs = (
        (SENTRY_O2, SENTRY_O3),
        (GUARDIAN_O2, GUARDIAN_O3),
        (CURATOR_O2, CURATOR_O3),
    )
    for o2_path, o3_path in o2_o3_pairs:
        o2 = parse_bundle(_load(o2_path))
        o3 = parse_bundle(_load(o3_path))
        assert o2.merkle_root != o3.merkle_root, (
            f"{o2_path.name} and {o3_path.name} have IDENTICAL Merkle roots; "
            "O3 ACTING bundle has not actually changed the policy set"
        )
