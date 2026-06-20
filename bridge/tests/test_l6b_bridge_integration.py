"""Tests for L6b bridge integration — Phase 63.

Tests pitl_meta fields, humanity formula branches, and store persistence.
Uses the existing DualShockIntegration mock pattern from Phase 58/62 tests.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Stub heavy optional deps before importing bridge modules
for _mod in [
    "web3", "web3.exceptions", "eth_account",
    "pydualsense", "pydualsense.enums",
    "hidapi", "hid",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

sys.path.insert(0, str(Path(__file__).parents[1]))

from vapi_bridge.config import Config


def _make_config(**overrides) -> Config:
    """Build a minimal Config with L6b fields, bypassing env file."""
    import os
    os.environ.setdefault("POAC_VERIFIER_ADDRESS", "0x" + "a" * 40)
    os.environ.setdefault("BRIDGE_PRIVATE_KEY", "0x" + "b" * 64)
    os.environ.setdefault("HTTP_ENABLED", "true")
    # Isolate from operator bridge/.env (T199-8 pattern).
    for key in (
        "L6B_ENABLED",
        "L6B_PROBE_INTERVAL_TICKS",
        "L6B_PROBE_R2_FORCE",
        "L6B_PROBE_MODE",
        "L6B_PROBE_HOLD_MS",
    ):
        os.environ.pop(key, None)
    for k, v in overrides.items():
        os.environ[k.upper()] = str(v)
    cfg = Config()
    for k in overrides:
        os.environ.pop(k.upper(), None)
    return cfg


class TestL6bConfigFields:
    def test_l6b_enabled_defaults_false(self):
        cfg = _make_config()
        assert cfg.l6b_enabled is False

    def test_l6b_probe_interval_default(self):
        cfg = _make_config()
        assert cfg.l6b_probe_interval_ticks == 6750

    def test_l6b_accel_threshold_default(self):
        cfg = _make_config()
        assert cfg.l6b_accel_delta_threshold_lsb == pytest.approx(500.0)

    def test_l6b_human_bounds_defaults(self):
        cfg = _make_config()
        assert cfg.l6b_human_min_ms == pytest.approx(80.0)
        assert cfg.l6b_human_max_ms == pytest.approx(280.0)

    def test_l6b_probe_r2_force_default(self):
        cfg = _make_config()
        assert cfg.l6b_probe_r2_force == 60

    def test_l6b_probe_r2_force_env_override(self):
        cfg = _make_config(L6B_PROBE_R2_FORCE=120)
        assert cfg.l6b_probe_r2_force == 120


class TestHumanityFormulaL6b:
    """Verify humanity formula coefficient branches sum to 1.00."""

    def test_l6b_only_branch_sums_to_one(self):
        weights = [0.25, 0.24, 0.17, 0.14, 0.12, 0.08]
        assert sum(weights) == pytest.approx(1.00, abs=1e-9)

    def test_both_l6_and_l6b_branch_sums_to_one(self):
        weights = [0.20, 0.18, 0.12, 0.14, 0.14, 0.12, 0.10]
        assert sum(weights) == pytest.approx(1.00, abs=1e-9)

    def test_baseline_branch_sums_to_one(self):
        weights = [0.28, 0.27, 0.20, 0.15, 0.10]
        assert sum(weights) == pytest.approx(1.00, abs=1e-9)

    def test_l6_only_branch_sums_to_one(self):
        weights = [0.23, 0.22, 0.15, 0.15, 0.15, 0.10]
        assert sum(weights) == pytest.approx(1.00, abs=1e-9)


class TestL6bStoreIntegration:
    """Verify store methods for L6b probe log."""

    def test_insert_and_retrieve_probe(self, tmp_path):
        """insert_l6b_probe + get_l6b_baseline round-trip."""
        import tempfile, os
        tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=str(tmp_path))
        tf.close()
        from vapi_bridge.store import Store
        store = Store(tf.name)
        store.insert_l6b_probe(
            device_id="aa" * 32,
            probe_ts_ms=1000000,
            latency_ms=140.0,
            classification="HUMAN",
            accel_delta_peak=800.0,
        )
        store.insert_l6b_probe(
            device_id="aa" * 32,
            probe_ts_ms=1067000,
            latency_ms=5.0,
            classification="BOT",
            accel_delta_peak=1200.0,
        )
        baseline = store.get_l6b_baseline("aa" * 32)
        assert baseline["probe_count"] == 2
        assert baseline["bot_events"] == 1
        assert baseline["mean_latency_ms"] == pytest.approx(72.5)
        assert baseline["classification_distribution"]["HUMAN"] == 1
        assert baseline["classification_distribution"]["BOT"] == 1

    def test_get_l6b_baseline_empty(self, tmp_path):
        """get_l6b_baseline returns probe_count=0 when no rows exist."""
        import tempfile
        tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=str(tmp_path))
        tf.close()
        from vapi_bridge.store import Store
        store = Store(tf.name)
        baseline = store.get_l6b_baseline("bb" * 32)
        assert baseline["probe_count"] == 0
        assert baseline["mean_latency_ms"] is None

    def test_insert_l6b_probe_cco_telemetry_columns(self, tmp_path):
        """CCO Phase B: reflex_verdict + profile + policy_ref round-trip."""
        import tempfile
        tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=str(tmp_path))
        tf.close()
        from vapi_bridge.store import Store
        store = Store(tf.name)
        store.insert_l6b_probe(
            device_id="cc" * 32,
            probe_ts_ms=2000000,
            latency_ms=150.0,
            classification="HUMAN",
            accel_delta_peak=900.0,
            reflex_verdict="REFLEX_OBSERVED",
            cco_profile_id="sony_dualshock_edge_v1",
            policy_ref="CCO_T0_POLICY_v1_OPTION_C",
        )
        with store._conn() as conn:
            row = conn.execute(
                "SELECT reflex_verdict, cco_profile_id, policy_ref "
                "FROM l6b_probe_log WHERE device_id=?",
                ("cc" * 32,),
            ).fetchone()
        assert row is not None
        assert row["reflex_verdict"] == "REFLEX_OBSERVED"
        assert row["cco_profile_id"] == "sony_dualshock_edge_v1"
        assert row["policy_ref"] == "CCO_T0_POLICY_v1_OPTION_C"

    def test_insert_l6b_probe_trigger_r2_at_probe_column(self, tmp_path):
        """F-L6B-CAL-003: nullable trigger_r2_at_probe audit column."""
        import tempfile
        tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=str(tmp_path))
        tf.close()
        from vapi_bridge.store import Store
        store = Store(tf.name)
        store.insert_l6b_probe(
            device_id="dd" * 32,
            probe_ts_ms=3000000,
            latency_ms=120.0,
            classification="HUMAN",
            accel_delta_peak=650.0,
            reflex_verdict="REFLEX_OBSERVED",
            trigger_r2_at_probe=8,
        )
        with store._conn() as conn:
            row = conn.execute(
                "SELECT trigger_r2_at_probe FROM l6b_probe_log WHERE device_id=?",
                ("dd" * 32,),
            ).fetchone()
        assert row is not None
        assert row["trigger_r2_at_probe"] == 8

    def test_insert_l6b_probe_diagnostic_round_trip(self, tmp_path):
        import tempfile

        tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=str(tmp_path))
        tf.close()
        from vapi_bridge.store import Store
        from vapi_bridge.cco_l6b_wiring import (
            compute_l6b_probe_diagnostic,
            l6b_probe_diagnostic_to_json,
        )

        store = Store(tf.name)
        probe_id = store.insert_l6b_probe(
            device_id="ee" * 32,
            probe_ts_ms=3000000,
            latency_ms=352.0,
            classification="INCONCLUSIVE",
            accel_delta_peak=1200.0,
        )
        diag = compute_l6b_probe_diagnostic(
            [{"ax": 100.0, "ay": 0.0, "az": 0.0}],
            [{"ax": 700.0, "ay": 0.0, "az": 0.0, "t_mono": 1001.25}],
            1000.0,
            legacy_latency_ms=352.0,
        )
        store.insert_l6b_probe_diagnostic(
            device_id="ee" * 32,
            probe_ts_mono=diag.probe_ts,
            probe_log_id=probe_id,
            legacy_latency_ms=diag.legacy_index_latency_ms,
            true_latency_ms=diag.true_latency_ms,
            precursor_gap_ms=diag.precursor_gap_ms,
            reflex_gap_ms=diag.reflex_gap_ms,
            diagnostic_json=l6b_probe_diagnostic_to_json(diag),
        )
        with store._conn() as conn:
            row = conn.execute(
                "SELECT probe_log_id, true_latency_ms, reflex_gap_ms "
                "FROM l6b_probe_diagnostic WHERE device_id=?",
                ("ee" * 32,),
            ).fetchone()
        assert row is not None
        assert row["probe_log_id"] == probe_id
        assert row["true_latency_ms"] == pytest.approx(1250.0)
