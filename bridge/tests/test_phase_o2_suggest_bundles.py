"""Phase O2-SUGGEST-DRAFT — pre-anchor validation tests for O2 SUGGEST bundles.

Locks the O2 SUGGEST bundles into CI so future contributors can't
regress them silently. Pairs with the C7 V&V CLI tooling — same
contracts but tested as data, not as CLI invocation.

These bundles are pre-validated authoring artifacts. They will become
the input to a future dual-anchor cycle when Phase O1 D ships and the
operator-track advances to O2 SUGGEST. Until then, they sit on disk as
verified candidates.
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

BUNDLES_DIR = BRIDGE_DIR / "vapi_bridge" / "cedar_bundles"
SENTRY_O2 = BUNDLES_DIR / "anchor_sentry_o2_suggest_v1.json"
GUARDIAN_O2 = BUNDLES_DIR / "guardian_o2_suggest_v1.json"


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# T-O2-SUG-1: both O2 bundle files exist and are valid Cedar bundles
# ---------------------------------------------------------------------------

def test_t_o2_sug_1_both_bundles_valid():
    from vapi_bridge.cedar_parser import parse_bundle, bundle_merkle_root

    assert SENTRY_O2.exists(), f"Sentry O2 bundle missing at {SENTRY_O2}"
    assert GUARDIAN_O2.exists(), f"Guardian O2 bundle missing at {GUARDIAN_O2}"

    sentry = _load(SENTRY_O2)
    guardian = _load(GUARDIAN_O2)

    sentry_parsed = parse_bundle(sentry)
    guardian_parsed = parse_bundle(guardian)

    # Phase MUST be O2_SUGGEST (not the O1 SHADOW value)
    assert sentry_parsed.phase == "O2_SUGGEST"
    assert guardian_parsed.phase == "O2_SUGGEST"

    # agent_ids must match the canonical Q9-frozen identifiers
    assert sentry_parsed.agent_id == SENTRY_ID
    assert guardian_parsed.agent_id == GUARDIAN_ID

    # Round-trip Merkle root check
    assert sentry_parsed.merkle_root == bundle_merkle_root(sentry)
    assert guardian_parsed.merkle_root == bundle_merkle_root(guardian)


# ---------------------------------------------------------------------------
# T-O2-SUG-2: O2 lifts the shadow_mode constraint on kms-sign + provenance
# ---------------------------------------------------------------------------

def test_t_o2_sug_2_shadow_mode_constraint_lifted():
    """Per Pass 2C activation matrix: at O2, kms-sign signs commit hashes
    (no longer draft-only); provenance-recording fires PR-merged anchors
    (no longer shadow-only). The shadow_mode:true constraint that gated
    these in O1 must NOT appear in O2."""
    from vapi_bridge.cedar_parser import parse_bundle

    sentry = parse_bundle(_load(SENTRY_O2))
    guardian = parse_bundle(_load(GUARDIAN_O2))

    for bundle, label in [(sentry, "sentry"), (guardian, "guardian")]:
        for pol in bundle.policies:
            if pol.action in ("tool:kms-sign", "skill:provenance-recording", "skill:audit-drafting"):
                if pol.effect == "permit" and pol.constraint:
                    assert pol.constraint.get("shadow_mode") is not True, (
                        f"{label} O2 policy {pol.id} ({pol.action}) STILL has shadow_mode:true "
                        f"constraint — should be lifted in O2 SUGGEST per activation matrix"
                    )


# ---------------------------------------------------------------------------
# T-O2-SUG-3: O2 adds previously-forbidden capabilities (pda-anchor, ipfs-pin,
# git-commit, git-pr) as PERMITS — but git-push remains forbidden
# ---------------------------------------------------------------------------

def test_t_o2_sug_3_o2_capability_lift_per_matrix():
    from vapi_bridge.cedar_parser import parse_bundle

    sentry = parse_bundle(_load(SENTRY_O2))
    guardian = parse_bundle(_load(GUARDIAN_O2))

    sentry_actions_permitted = {p.action for p in sentry.policies if p.effect == "permit"}
    sentry_actions_forbidden = {p.action for p in sentry.policies if p.effect == "forbid"}
    guardian_actions_permitted = {p.action for p in guardian.policies if p.effect == "permit"}
    guardian_actions_forbidden = {p.action for p in guardian.policies if p.effect == "forbid"}

    # Sentry: pda-attestation-anchor + git-commit + git-pr + ipfs-pin become permitted
    for action in ("tool:pda-attestation-anchor", "tool:git-commit",
                   "tool:git-pr", "tool:ipfs-pin"):
        assert action in sentry_actions_permitted, (
            f"Sentry O2 must PERMIT {action} (lifted from O1 SHADOW per matrix)"
        )

    # Guardian: same capabilities lift EXCEPT pda-attestation-anchor (Sentry-only)
    for action in ("tool:git-commit", "tool:git-pr", "tool:ipfs-pin"):
        assert action in guardian_actions_permitted, (
            f"Guardian O2 must PERMIT {action} (lifted from O1 SHADOW per matrix)"
        )
    assert "tool:pda-attestation-anchor" in guardian_actions_forbidden, (
        "Guardian O2 must FORBID pda-attestation-anchor (Sentry-only skill per matrix)"
    )

    # BOTH agents: git-push REMAINS forbidden (no direct push at O2; must go via PR)
    for label, forbidden in (("sentry", sentry_actions_forbidden),
                             ("guardian", guardian_actions_forbidden)):
        assert "tool:git-push" in forbidden, (
            f"{label} O2 must FORBID tool:git-push — direct push prohibited at O2; "
            f"PR-merge is the ONLY path per Pass 2C activation matrix"
        )


# ---------------------------------------------------------------------------
# T-O2-SUG-4: cross-agent skill separation preserved — Sentry/Guardian
# remain in their respective lanes (event-correlation vs audit-drafting etc)
# ---------------------------------------------------------------------------

def test_t_o2_sug_4_cross_agent_separation_preserved():
    """Sentry handles event-correlation + provenance-recording.
    Guardian handles audit-drafting + operational-diagnostic.
    These boundaries from O1 SHADOW MUST persist in O2 SUGGEST."""
    from vapi_bridge.cedar_parser import parse_bundle

    sentry = parse_bundle(_load(SENTRY_O2))
    guardian = parse_bundle(_load(GUARDIAN_O2))

    sentry_forbidden = {p.action for p in sentry.policies if p.effect == "forbid"}
    guardian_forbidden = {p.action for p in guardian.policies if p.effect == "forbid"}

    # Sentry must FORBID Guardian's skills
    assert "skill:audit-drafting" in sentry_forbidden, \
        "Sentry O2 must FORBID skill:audit-drafting (Guardian-only)"
    assert "skill:operational-diagnostic" in sentry_forbidden, \
        "Sentry O2 must FORBID skill:operational-diagnostic (Guardian-only)"

    # Guardian must FORBID Sentry's skills
    assert "skill:event-correlation" in guardian_forbidden, \
        "Guardian O2 must FORBID skill:event-correlation (Sentry-only)"
    assert "skill:provenance-recording" in guardian_forbidden, \
        "Guardian O2 must FORBID skill:provenance-recording (Sentry-only)"
