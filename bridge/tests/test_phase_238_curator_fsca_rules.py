"""Phase 238 Step I-AUTOLOOP-2 — FSCA Curator drift rules tests.

T-238-CUR-FSCA-1..4 — verifies the 2 new CONTRADICTION_RULES query the
curator_listing_review_log correctly, fire only on the right verdicts +
within the 1 h window, and the rule count assertion is 29 (Phase O5 M.3 +2 Mythos; was 15 pre-
this-commit).
"""
from __future__ import annotations

import sys
import time
import types as _types
from pathlib import Path

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
from vapi_bridge.fleet_signal_coherence_agent import (  # noqa: E402
    CONTRADICTION_RULES,
)
from vapi_bridge.curator_review import (  # noqa: E402
    VERDICT_FLAGGED_TIER_MISMATCH,
    VERDICT_FLAGGED_CONSENT_AMBIGUOUS,
    VERDICT_APPROVED,
)


@pytest.fixture
def tmp_store(tmp_path):
    return Store(str(tmp_path / "phase238_fsca_test.db"))


def _exec_rule(store, rule_name: str, cfg=None) -> list[dict]:
    """Execute a CONTRADICTION_RULE query against the test store + return rows."""
    rule = CONTRADICTION_RULES[rule_name]
    params = rule["params"](cfg)
    with store._conn() as conn:
        rows = conn.execute(rule["query"], params).fetchall()
    return [dict(r) for r in rows]


# T-238-CUR-FSCA-1 ───────────────────────────────────────────────────────────
def test_t_238_cur_fsca_1_listing_tier_drift_rule_fires(tmp_store):
    """LISTING_TIER_DRIFT fires when a Curator review row has
    verdict=FLAGGED_TIER_MISMATCH AND tier_changed=1 within 1 h.
    """
    # Seed a flagged review with tier mismatch
    tmp_store.insert_curator_review(
        listing_commitment="ab" * 32,
        verdict=VERDICT_FLAGGED_TIER_MISMATCH,
        severity="WARN",
        anchors_recorded_count=2,
        anchors_breakdown_json='{"sepproof":true,"biometric":true,"corpus":false,"gic":false}',
        consent_marketplace_bit_set=True,
        ipfs_resolvable=True,
        declared_tier=3,                 # Premium
        tier_at_review_time=2,           # Attested (only 2 anchors recorded)
        tier_changed=True,
        shadow_mode=True,
        reason_detail="declared_tier=3 != tier_at_review_time=2",
        trigger_reason="t-fsca-1",
        ts_ns=int(time.time_ns()),
    )

    # Also seed a NON-flagged row that should NOT match
    tmp_store.insert_curator_review(
        listing_commitment="cd" * 32,
        verdict=VERDICT_APPROVED, severity="INFO",
        anchors_recorded_count=4, anchors_breakdown_json="{}",
        consent_marketplace_bit_set=True, ipfs_resolvable=True,
        declared_tier=3, tier_at_review_time=3, tier_changed=False,
        shadow_mode=True, reason_detail="all checks pass",
        trigger_reason="t-fsca-1-noise", ts_ns=int(time.time_ns()),
    )

    rows = _exec_rule(tmp_store, "LISTING_TIER_DRIFT", cfg=None)
    assert len(rows) == 1
    assert rows[0]["listing_commitment"] == "ab" * 32
    assert rows[0]["declared_tier"] == 3
    assert rows[0]["tier_at_review_time"] == 2

    # Severity correctness
    rule = CONTRADICTION_RULES["LISTING_TIER_DRIFT"]
    assert rule["severity"] == "HIGH"
    assert "Curator" in rule["agents_involved"]


# T-238-CUR-FSCA-2 ───────────────────────────────────────────────────────────
def test_t_238_cur_fsca_2_consent_revoked_rule_fires_critical(tmp_store):
    """CONSENT_REVOKED_LISTING_ACTIVE fires CRITICAL on FLAGGED_CONSENT_AMBIGUOUS."""
    tmp_store.insert_curator_review(
        listing_commitment="ef" * 32,
        verdict=VERDICT_FLAGGED_CONSENT_AMBIGUOUS,
        severity="WARN",
        anchors_recorded_count=4,
        anchors_breakdown_json='{"sepproof":true,"biometric":true,"corpus":true,"gic":true}',
        consent_marketplace_bit_set=False,    # bit cleared post-creation
        ipfs_resolvable=True,
        declared_tier=3, tier_at_review_time=3, tier_changed=False,
        shadow_mode=True,
        reason_detail="MARKETPLACE consent bit (bit 3) cleared in consent_bitmask",
        trigger_reason="t-fsca-2", ts_ns=int(time.time_ns()),
    )

    rows = _exec_rule(tmp_store, "CONSENT_REVOKED_LISTING_ACTIVE", cfg=None)
    assert len(rows) == 1
    assert rows[0]["listing_commitment"] == "ef" * 32

    rule = CONTRADICTION_RULES["CONSENT_REVOKED_LISTING_ACTIVE"]
    assert rule["severity"] == "CRITICAL"
    # GDPR Art.17 enforcement primitive — references BiometricPrivacyComplianceAgent
    assert "BiometricPrivacyComplianceAgent" in rule["agents_involved"]
    assert "ConsentLedger" in rule["agents_involved"]


# T-238-CUR-FSCA-3 ───────────────────────────────────────────────────────────
def test_t_238_cur_fsca_3_rules_age_out_after_1h(tmp_store):
    """Rules use a 1 h window — verdicts older than 1 h should not match."""
    # Seed a flagged review with ts_ns 2 hours ago
    two_hours_ago_ns = int((time.time() - 7200) * 1e9)
    tmp_store.insert_curator_review(
        listing_commitment="aa" * 32,
        verdict=VERDICT_FLAGGED_TIER_MISMATCH, severity="WARN",
        anchors_recorded_count=2, anchors_breakdown_json="{}",
        consent_marketplace_bit_set=True, ipfs_resolvable=True,
        declared_tier=3, tier_at_review_time=2, tier_changed=True,
        shadow_mode=True, reason_detail="stale",
        trigger_reason="t-fsca-3", ts_ns=two_hours_ago_ns,
    )

    rows = _exec_rule(tmp_store, "LISTING_TIER_DRIFT", cfg=None)
    # Should NOT match — older than 1 h cutoff
    assert len(rows) == 0


# T-238-CUR-FSCA-4 ───────────────────────────────────────────────────────────
def test_t_238_cur_fsca_4_rule_count_invariant():
    """CONTRADICTION_RULES count assertion: 28 rules at current head
    (29 → 28 on 2026-05-16 after H-1 Option B dropped VPM_MANIFEST_HASH_DRIFT
    per architectural-mismatch finding — the rule was checking a cross-table
    referential integrity relationship the production MLGA-emission design
    never honored; not all dropped rules are FROZEN-region edits)."""
    assert "LISTING_TIER_DRIFT" in CONTRADICTION_RULES
    assert "CONSENT_REVOKED_LISTING_ACTIVE" in CONTRADICTION_RULES
    # Total rule count — locks the structural invariant
    assert len(CONTRADICTION_RULES) == 28, (
        f"Expected 28 CONTRADICTION_RULES; got {len(CONTRADICTION_RULES)}. "
        "If this test fails, either a new rule was added (update count + "
        "this test's expected) or an existing rule was removed (which "
        "requires architectural justification — see VPM_MANIFEST_HASH_DRIFT "
        "removal commit 2026-05-16 as the precedent)."
    )

    # Required fields on the new rules
    for name in ("LISTING_TIER_DRIFT", "CONSENT_REVOKED_LISTING_ACTIVE"):
        rule = CONTRADICTION_RULES[name]
        assert callable(rule["params"]), f"{name} params must be callable"
        assert "Curator" in rule["agents_involved"], f"{name} must list Curator"
        assert rule["severity"] in {"HIGH", "CRITICAL"}, f"{name} severity"
        assert rule.get("explanation"), f"{name} explanation required"
        assert rule.get("resolution"), f"{name} resolution required"
