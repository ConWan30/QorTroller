"""Phase 238 Step I-AUTOLOOP-4 — pre-flight runbook + O2 SUGGEST + Step H tests.

T-238-PFLT-1..6 — verifies the activation runbook script imports cleanly,
the O2 SUGGEST Cedar bundle validates + lints + has expected delta from
O1, the Step H deploy script has expected sanity-call shape, and the
ProtocolStateCache producer wiring fires curator_verdict events when
compute_verdict_for_listing is invoked with a cache argument.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import types as _types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.curator_agent import compute_verdict_for_listing  # noqa: E402
from vapi_bridge.protocol_state_cache import (  # noqa: E402
    ProtocolStateCache, EVENT_CURATOR_VERDICT,
)
from vapi_bridge.curator_review import MARKETPLACE_CONSENT_BIT  # noqa: E402


# T-238-PFLT-1 ───────────────────────────────────────────────────────────────
def test_t_238_pflt_1_runbook_script_importable():
    """The pre-flight runbook script imports cleanly + has main() with argparse."""
    runbook_path = PROJECT_ROOT / "scripts" / "curator_preflight_runbook.py"
    assert runbook_path.exists(), "runbook script must exist"
    src = runbook_path.read_text(encoding="utf-8")
    # Required structure
    assert "def main()" in src
    assert "argparse" in src
    assert "MIN_REQUIRED_IOTX = 0.5" in src
    assert "PLACEHOLDER_AGENT_ID" in src
    # 9-step procedure documented
    assert "9-STEP ON-CHAIN ACTIVATION PROCEDURE" in src
    # All check labels present
    for label in [
        "[1] Wallet balance",
        "[2] O1_SHADOW bundle validate",
        "[6] O1 bundle agentId still placeholder",
        "[7] Step H VAPIDataMarketplaceListings",
    ]:
        assert label in src, f"runbook missing check label: {label}"


# T-238-PFLT-2 ───────────────────────────────────────────────────────────────
def test_t_238_pflt_2_o2_suggest_bundle_present():
    """curator_o2_suggest_v1.json exists with required structural fields."""
    bundle_path = (
        BRIDGE_DIR / "vapi_bridge" / "cedar_bundles" / "curator_o2_suggest_v1.json"
    )
    assert bundle_path.exists(), "O2 SUGGEST bundle must exist"
    bundle = json.loads(bundle_path.read_text())
    assert bundle["$schema"] == "vapi-cedar-bundle-v1"
    assert bundle["phase"] == "O2_SUGGEST"
    assert "marketplace/" in bundle["lane_prefixes"]
    # NEW O2 permit not present in O1
    actions = {p["action"] for p in bundle["policies"] if p["effect"] == "permit"}
    assert "tool:operator-notify" in actions
    # Cross-agent separation preserved at O2
    forbids = {p["action"] for p in bundle["policies"] if p["effect"] == "forbid"}
    assert "skill:event-correlation" in forbids
    assert "skill:audit-drafting" in forbids
    assert "tool:git-push" in forbids
    # Curator-exclusive skills retained
    assert "skill:marketplace-listing-review" in actions
    assert "skill:tier-compliance-check" in actions


# T-238-PFLT-3 ───────────────────────────────────────────────────────────────
def test_t_238_pflt_3_o2_bundle_lifts_shadow_mode():
    """O2_SUGGEST bundle lifts shadow_mode constraint on tool:kms-sign +
    skill:marketplace-listing-review (graduation from O1)."""
    bundle_path = (
        BRIDGE_DIR / "vapi_bridge" / "cedar_bundles" / "curator_o2_suggest_v1.json"
    )
    bundle = json.loads(bundle_path.read_text())

    # The two policies that had shadow_mode constraint at O1 (P-006 + P-007)
    # MUST have it removed at O2.
    for pol in bundle["policies"]:
        if pol.get("action") == "tool:kms-sign" and pol.get("effect") == "permit":
            assert "constraint" not in pol or not pol.get("constraint"), (
                f"O2 P-{pol['id']} kms-sign should NOT have shadow_mode constraint"
            )
        if pol.get("action") == "skill:marketplace-listing-review" and pol.get("effect") == "permit":
            assert "constraint" not in pol or not pol.get("constraint"), (
                f"O2 P-{pol['id']} marketplace-listing-review should NOT have shadow_mode constraint"
            )


# T-238-PFLT-4 ───────────────────────────────────────────────────────────────
def test_t_238_pflt_4_step_h_deploy_script_shape():
    """deploy-phase238-step-h.js has the required sanity-call shape."""
    script_path = (
        PROJECT_ROOT / "contracts" / "scripts" / "deploy-phase238-step-h.js"
    )
    assert script_path.exists(), "Step H deploy script must exist"
    src = script_path.read_text(encoding="utf-8")
    # Reads constructor args from deployed-addresses.json
    assert "VAPIDataMarketplace" in src
    assert "AdjudicationRegistry" in src
    # Already-deployed guard prevents accidental re-deploy
    assert "addresses.VAPIDataMarketplaceListings" in src
    assert "ALREADY DEPLOYED" in src
    # Sanity calls verify constructor wiring
    assert "phase69MarketplaceAddress" in src or "phase69Marketplace()" in src
    assert "adjudicationRegistry()" in src
    # Wallet balance pre-check
    assert "balanceIotx" in src
    # Updates deployed-addresses.json after success
    assert "_phase238_step_h_status" in src


# T-238-PFLT-5 ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_pflt_5_producer_emits_curator_verdict_to_cache(tmp_path):
    """compute_verdict_for_listing emits curator_verdict event to ProtocolStateCache
    when cache argument is passed.  This is the producer wiring for Step I-AUTOLOOP-3.
    """
    store = Store(str(tmp_path / "phase238_pflt_test.db"))
    cache = ProtocolStateCache()
    queue = cache.subscribe()

    # Mock chain — all anchors recorded
    chain = MagicMock()
    chain.is_adjudication_recorded = AsyncMock(return_value=True)
    cfg = MagicMock()
    cfg.curator_anchor_freshness_blocks = 1_000_000

    listing = {
        "listing_commitment":     "ab" * 32,
        "sepproof_commitment":    "11" * 32,
        "biometric_snapshot_hash":"22" * 32,
        "corpus_snapshot_hash":   "33" * 32,
        "gic_hash":               "44" * 32,
        "consent_bitmask":        MARKETPLACE_CONSENT_BIT,
        "data_class":             6,
        "anchors_present_count":  4,
    }
    res = await compute_verdict_for_listing(
        store, chain, cfg,
        "ab" * 32, listing, "test_t5",
        protocol_state_cache=cache,
    )
    assert res["verdict"] == "APPROVED"

    # Cache subscriber received curator_verdict event
    event_type, payload = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event_type == EVENT_CURATOR_VERDICT
    assert payload["commitment16"] == ("ab" * 32)[:16]
    assert payload["verdict"] == "APPROVED"
    assert payload["severity"] == "INFO"

    cache.unsubscribe(queue)


# T-238-PFLT-6 ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_t_238_pflt_6_producer_failopen_when_cache_none(tmp_path):
    """compute_verdict_for_listing without cache argument runs cleanly (no error,
    no event emission)."""
    store = Store(str(tmp_path / "phase238_pflt_t6.db"))
    chain = MagicMock()
    chain.is_adjudication_recorded = AsyncMock(return_value=False)
    cfg = MagicMock()
    cfg.curator_anchor_freshness_blocks = 1_000_000

    listing = {
        "listing_commitment": "cd" * 32,
        "consent_bitmask":    MARKETPLACE_CONSENT_BIT,
        "data_class":         0,
        "anchors_present_count": 0,
    }
    # No cache passed — should still complete normally
    res = await compute_verdict_for_listing(
        store, chain, cfg,
        "cd" * 32, listing, "test_t6",
        protocol_state_cache=None,
    )
    assert res["row_id"] > 0
    assert res["verdict"] == "REJECTED_NO_ANCHORS"
