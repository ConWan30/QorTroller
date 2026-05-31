"""
Phase 223 — PV-CI Protocol Invariant Gate Tests
T223-1..T223-8

Tests:
  T223-1: insert_invariant_gate_log stores entry and returns row id
  T223-2: get_invariant_gate_status returns 7 expected keys after insert
  T223-3: get_invariant_gate_status returns None gate_pass before any run
  T223-4: Config has pv_ci_enabled field defaulting to True
  T223-5: vapi_invariant_gate.py check_invariants() returns 15 results
  T223-6: vapi_invariant_gate.py run_gate() returns 0 (pass) against current codebase
  T223-7: GET /agent/invariant-gate-status returns 200 with 7 keys
  T223-8: POST /agent/run-invariant-gate returns 200 with gate_pass
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))

# ── web3 / eth_account stubs ──────────────────────────────────────────────────
import types

for _mod in ("web3", "web3.exceptions", "eth_account", "eth_account.messages",
             "web3.middleware", "web3.gas_strategies", "web3.gas_strategies.time_based"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_fake_web3 = sys.modules["web3"]
if not hasattr(_fake_web3, "Web3"):
    class _W3Stub:
        HTTPProvider = lambda *a, **kw: None
        class middleware_onion:
            inject = lambda *a, **kw: None
    _fake_web3.Web3 = _W3Stub

_fake_exc = sys.modules["web3.exceptions"]
if not hasattr(_fake_exc, "ContractLogicError"):
    _fake_exc.ContractLogicError = type("ContractLogicError", (Exception,), {})


def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test223.db"))


# ── T223-1: insert_invariant_gate_log ────────────────────────────────────────
def test_T223_1_insert_invariant_gate_log():
    """insert_invariant_gate_log stores entry and returns row id."""
    store = _make_store()
    row_id = store.insert_invariant_gate_log(
        gate_pass=True,
        total_checked=15,
        failures_json="[]",
        run_source="test",
    )
    assert isinstance(row_id, int)
    assert row_id >= 1


# ── T223-2: get_invariant_gate_status returns 7 keys ────────────────────────
def test_T223_2_get_invariant_gate_status_keys():
    """get_invariant_gate_status returns 7 expected keys after insert."""
    store = _make_store()
    store.insert_invariant_gate_log(
        gate_pass=True, total_checked=15, failures_json="[]", run_source="ci"
    )
    result = store.get_invariant_gate_status()
    expected = {
        "pv_ci_enabled", "gate_pass", "total_checked",
        "failure_count", "last_failures", "last_run_ts", "timestamp",
    }
    assert expected.issubset(set(result.keys()))
    assert result["gate_pass"] is True
    assert result["total_checked"] == 15
    assert result["failure_count"] == 0


# ── T223-3: get_invariant_gate_status no-run sentinel ────────────────────────
def test_T223_3_get_invariant_gate_status_empty():
    """get_invariant_gate_status returns None gate_pass before any run."""
    store = _make_store()
    result = store.get_invariant_gate_status()
    assert result["gate_pass"] is None
    assert result["total_checked"] == 0
    assert result["last_run_ts"] is None


# ── T223-4: Config has pv_ci_enabled field ──────────────────────────────────
def test_T223_4_config_pv_ci_enabled_default():
    """Config.pv_ci_enabled defaults to True."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.pv_ci_enabled is True


# ── T223-5: vapi_invariant_gate check_invariants returns all results ─────────
def test_T223_5_check_invariants_count():
    """vapi_invariant_gate.check_invariants() returns 86 result dicts (current INVARIANTS set)."""
    import vapi_invariant_gate as vig
    results = vig.check_invariants()
    assert len(results) == 172
    for r in results:
        assert "id" in r
        assert "digest" in r
        assert "match_count" in r
        assert "pattern_matched" in r


# ── T223-6: run_gate returns 0 (all pass) ────────────────────────────────────
def test_T223_6_run_gate_passes():
    """vapi_invariant_gate.run_gate() returns 0 against current codebase."""
    import vapi_invariant_gate as vig
    exit_code = vig.run_gate()
    assert exit_code == 0, "Invariant gate failed — a frozen protocol region may have drifted"


# ── T223-7: GET /agent/invariant-gate-status returns 7 keys ─────────────────
@pytest.mark.needs_env
def test_T223_7_endpoint_invariant_gate_status():
    """GET /agent/invariant-gate-status returns 200 with 7 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    import os
    os.environ.pop("OPERATOR_API_KEY", None)
    store223 = _make_store()
    cfg223 = Config()
    app223 = create_operator_app(cfg223, store223)
    client = TestClient(app223)

    resp = client.get("/agent/invariant-gate-status")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "pv_ci_enabled", "gate_pass", "total_checked",
        "failure_count", "last_failures", "last_run_ts", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T223-8: POST /agent/run-invariant-gate returns gate_pass ─────────────────
@pytest.mark.needs_env
def test_T223_8_endpoint_run_invariant_gate():
    """POST /agent/run-invariant-gate returns 200 with gate_pass key."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    import os
    os.environ.pop("OPERATOR_API_KEY", None)
    store223 = _make_store()
    cfg223 = Config()
    app223 = create_operator_app(cfg223, store223)
    client = TestClient(app223)

    resp = client.post("/agent/run-invariant-gate")
    assert resp.status_code == 200
    body = resp.json()
    assert "gate_pass" in body
    assert "total_checked" in body
    assert body["total_checked"] > 0
