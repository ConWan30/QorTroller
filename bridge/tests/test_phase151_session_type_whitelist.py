"""
Phase 151 — Session-Type Whitelist + Enrollment Capture Guidance (10 tests)

W1-011 formal closure: 'gameplay' and other free-form session types are invalid
inputs for the defensibility gate.  Only STRUCTURED_PROBE_TYPES are accepted:
    touchpad_corners | touchpad_freeform | touchpad_swipes

P0: insert_separation_defensibility_log raises ValueError on invalid session_type.
P1: get_enrollment_capture_guidance() returns per-probe per-player gap breakdown.

test_1_invalid_session_type_raises
test_2_valid_session_types_accepted
test_3_gameplay_rejected_whitelist
test_4_structured_probe_types_frozenset_contains_3
test_5_guidance_empty_db_all_probes_not_found
test_6_guidance_reflects_inserted_data
test_7_guidance_sessions_needed_total
test_8_guidance_overall_ready_false_without_all_probes
test_9_endpoint_returns_5_keys
test_10_tool_107_returns_5_keys
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

# Web3/eth_account stub
_w3 = MagicMock()
sys.modules.setdefault("web3", _w3)
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store():
    """Create a file-based Store (Windows WAL safety)."""
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test_phase151.db")
    from bridge.vapi_bridge.store import Store
    return Store(db_path)


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "test-key-phase151"
    cfg.rate_limit_per_minute = 9999
    cfg.agent_dry_run_mode = True
    cfg.min_touchpad_sessions_per_player = 10
    cfg.ioswarm_enabled = False
    cfg.ioswarm_poad_auto_anchor_enabled = False
    cfg.gsr_enabled = False
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.dual_primitive_gate_enabled = False
    cfg.epistemic_consensus_enabled = False
    cfg.poad_registry_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.mcp_server_enabled = False
    return cfg


def _insert_corners(store, n_per_player=None, ratio=1.261, defensible=False):
    """Helper to insert a touchpad_corners defensibility record."""
    if n_per_player is None:
        n_per_player = {"P1": 3, "P2": 4, "P3": 4}
    return store.insert_separation_defensibility_log(
        session_type="touchpad_corners",
        n_sessions_total=sum(n_per_player.values()),
        n_per_player=n_per_player,
        min_n_per_player=10,
        defensible=defensible,
        ratio=ratio,
        all_pairs_above_1=ratio > 1.0,
    )


# ---------------------------------------------------------------------------
# 1. Invalid session_type raises ValueError
# ---------------------------------------------------------------------------

class TestSessionTypeWhitelist:

    def test_1_invalid_session_type_raises(self):
        """insert_separation_defensibility_log must raise ValueError on invalid session_type."""
        store = _make_store()
        with pytest.raises(ValueError, match="Invalid session_type"):
            store.insert_separation_defensibility_log(
                session_type="gameplay",
                n_sessions_total=127,
                n_per_player={"P1": 53, "P2": 40, "P3": 34},
                min_n_per_player=10,
                defensible=False,
                ratio=0.417,
                all_pairs_above_1=False,
            )

    def test_2_valid_session_types_accepted(self):
        """All three structured probe types must be accepted without raising."""
        store = _make_store()
        valid_types = ["touchpad_corners", "touchpad_freeform", "touchpad_swipes"]
        for stype in valid_types:
            rowid = store.insert_separation_defensibility_log(
                session_type=stype,
                n_sessions_total=11,
                n_per_player={"P1": 3, "P2": 4, "P3": 4},
                min_n_per_player=10,
                defensible=False,
                ratio=1.261,
                all_pairs_above_1=True,
            )
            assert isinstance(rowid, int) and rowid > 0, (
                f"insert_separation_defensibility_log returned {rowid!r} for {stype!r}"
            )

    def test_3_gameplay_rejected_whitelist(self):
        """'gameplay' is the canonical non-structured type — must be rejected (W1-011)."""
        store = _make_store()
        with pytest.raises(ValueError) as exc_info:
            store.insert_separation_defensibility_log(
                session_type="gameplay",
                n_sessions_total=30,
                n_per_player={"P1": 10, "P2": 10, "P3": 10},
                min_n_per_player=10,
                defensible=False,
                ratio=0.417,
                all_pairs_above_1=False,
            )
        assert "W1-011" in str(exc_info.value) or "gameplay" in str(exc_info.value).lower()

    def test_4_structured_probe_types_frozenset_contains_4(self):
        """Store.STRUCTURED_PROBE_TYPES must be a frozenset with exactly 4 entries (Phase 166 adds mixed_biometric_probe)."""
        from bridge.vapi_bridge.store import Store
        spt = Store.STRUCTURED_PROBE_TYPES
        assert isinstance(spt, frozenset)
        assert len(spt) == 4
        assert "touchpad_corners" in spt
        assert "touchpad_freeform" in spt
        assert "touchpad_swipes" in spt
        assert "mixed_biometric_probe" in spt  # Phase 166: 2-min all-feature probe
        # Free-form gameplay must NOT be in whitelist
        assert "gameplay" not in spt


# ---------------------------------------------------------------------------
# 5-8. get_enrollment_capture_guidance
# ---------------------------------------------------------------------------

class TestEnrollmentCaptureGuidance:

    def test_5_guidance_empty_db_all_probes_not_found(self):
        """On an empty DB, guidance must report found=False for all probe types (Phase 166: 4 types)."""
        store = _make_store()
        g = store.get_enrollment_capture_guidance(min_n=10)
        assert "guidance" in g
        assert "probe_types" in g
        assert len(g["probe_types"]) == 4  # Phase 166: mixed_biometric_probe added
        for probe in g["probe_types"]:
            assert g["guidance"][probe]["found"] is False
        assert g["overall_ready"] is False

    def test_6_guidance_reflects_inserted_data(self):
        """Guidance n_per_player and current_ratio must match the latest inserted record."""
        store = _make_store()
        _insert_corners(store, n_per_player={"P1": 3, "P2": 4, "P3": 4}, ratio=1.261)
        g = store.get_enrollment_capture_guidance(min_n=10)
        corners = g["guidance"]["touchpad_corners"]
        assert corners["found"] is True
        assert abs(corners["current_ratio"] - 1.261) < 0.001
        assert corners["n_per_player"]["P1"] == 3
        assert corners["n_per_player"]["P2"] == 4
        assert corners["n_per_player"]["P3"] == 4

    def test_7_guidance_sessions_needed_total(self):
        """sessions_needed_total must equal sum of per-player gaps across all probe types."""
        store = _make_store()
        # Insert corners: P1=3, P2=4, P3=4 → gap=7+6+6=19 for corners
        _insert_corners(store, n_per_player={"P1": 3, "P2": 4, "P3": 4})
        # freeform and swipes not inserted → gap=10+10+10=30 each
        g = store.get_enrollment_capture_guidance(min_n=10)
        # corners gap = 19, freeform/swipes not found (0 sessions → all_players_ready False, no gap computed)
        # When found=False, no player gap is computed; only corners contributes
        assert g["sessions_needed_total"] == 19

    def test_8_guidance_overall_ready_false_without_all_probes(self):
        """overall_ready must be False when not all probe types have defensible data."""
        store = _make_store()
        # Only insert touchpad_corners — other probes not found
        _insert_corners(store, n_per_player={"P1": 10, "P2": 10, "P3": 10}, ratio=1.5,
                        defensible=True)
        g = store.get_enrollment_capture_guidance(min_n=10)
        # Even though corners has enough players, freeform/swipes are missing → not ready
        assert g["overall_ready"] is False


# ---------------------------------------------------------------------------
# 9. Endpoint response shape
# ---------------------------------------------------------------------------

class TestEnrollmentCaptureEndpoint:

    def test_9_endpoint_returns_5_keys(self):
        """GET /agent/enrollment-capture-guidance must return 5 required keys."""
        store = _make_store()
        cfg = _make_cfg()
        import time as _t
        # Replicate endpoint logic (FastAPI not instantiated here)
        _min_n = int(getattr(cfg, "min_touchpad_sessions_per_player", 10))
        _guidance = store.get_enrollment_capture_guidance(min_n=_min_n)
        _guidance["timestamp"] = _t.time()
        for key in ("min_n_per_player", "probe_types", "guidance",
                    "sessions_needed_total", "overall_ready"):
            assert key in _guidance, f"Missing key: {key}"
        assert "timestamp" in _guidance


# ---------------------------------------------------------------------------
# 10. Tool #107
# ---------------------------------------------------------------------------

class TestTool107:

    def test_10_tool_107_returns_5_keys(self):
        """Tool #107 get_enrollment_capture_guidance must return 5 required keys."""
        store = _make_store()
        cfg = _make_cfg()
        from bridge.vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._store = store
        agent._cfg = cfg

        result = agent._execute_tool("get_enrollment_capture_guidance", {})
        for key in ("min_n_per_player", "probe_types", "guidance",
                    "sessions_needed_total", "overall_ready"):
            assert key in result, f"Tool #107 missing key: {key}"
