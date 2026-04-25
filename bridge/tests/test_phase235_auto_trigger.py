"""Phase 235-AUTO-TRIGGER — SessionBoundaryDetectorAgent unit tests.

Six tests T235-AT-1..6 cover the detector's decision logic in isolation
(no live bridge, no real DB).  Uses unittest.mock.MagicMock for the
Store; the detector reads via documented Store API only, so a Mock is
sufficient.
"""
import os
import sys
import types
import time
import pytest

# Stub heavy optional deps the bridge's chain imports load transitively
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from unittest.mock import MagicMock as _MagicMock
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
_web3_mod = sys.modules["web3"]
for _attr in ["AsyncWeb3", "AsyncHTTPProvider", "Web3"]:
    if not hasattr(_web3_mod, _attr):
        setattr(_web3_mod, _attr, _MagicMock())
_web3_exc = sys.modules["web3.exceptions"]
for _attr in ["ContractLogicError", "TransactionNotFound"]:
    if not hasattr(_web3_exc, _attr):
        setattr(_web3_exc, _attr, Exception)
_eth_acc = sys.modules["eth_account"]
if not hasattr(_eth_acc, "Account"):
    setattr(_eth_acc, "Account", _MagicMock())

from vapi_bridge.session_boundary_detector_agent import (
    SessionBoundaryDetectorAgent,
    ACTIVITY_FRACTION_MIN,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _Cfg:
    def __init__(self, **overrides):
        self.auto_trigger_enabled         = True
        self.auto_trigger_min_interval_s  = 300
        self.auto_trigger_quiescence_window = 60
        self.auto_trigger_activity_window   = 120
        self.grind_session_id             = "grind_phase235_v1"
        self.grind_target                 = 100
        for k, v in overrides.items():
            setattr(self, k, v)


def _records(n_quiescence: int, n_activity: int,
             quiescence_active=False, activity_fraction=0.5):
    """Build a fake recent-records list ordered most-recent-first.

    Tail (head of list) = quiescence window; rest = activity window.
    """
    tail = [
        {"trigger_active": int(bool(quiescence_active)), "device_id": "DEV"}
        for _ in range(n_quiescence)
    ]
    n_active = int(round(n_activity * activity_fraction))
    head = (
        [{"trigger_active": 1, "device_id": "DEV"}] * n_active
        + [{"trigger_active": 0, "device_id": "DEV"}] * (n_activity - n_active)
    )
    return tail + head


def _store_mock(*, pcc_state="NOMINAL", pcc_host="EXCLUSIVE_USB",
                chain_length=0, recent=None):
    s = _MagicMock()
    s.get_capture_health_status.return_value = {
        "capture_state": pcc_state,
        "host_state":    pcc_host,
    }
    s.get_grind_chain_status.return_value = {
        "chain_length": chain_length,
        "chain_intact": True,
    }
    s.get_recent_records.return_value = recent or []
    s.write_agent_event.return_value = 99  # fake event_id
    return s


# ---------------------------------------------------------------------------
# T235-AT-1: skipped when auto_trigger_enabled=False
# ---------------------------------------------------------------------------

def test_t235_at_1_disabled_skips_silently():
    cfg = _Cfg(auto_trigger_enabled=False)
    s   = _store_mock(recent=_records(60, 120, activity_fraction=0.5))
    agent = SessionBoundaryDetectorAgent(cfg, s)

    verdict, reason = agent.evaluate(now_monotonic=1000.0)

    assert verdict == "SKIP"
    assert "auto_trigger_enabled=False" in reason
    s.write_agent_event.assert_not_called()


# ---------------------------------------------------------------------------
# T235-AT-2: skipped when PCC is not NOMINAL+EXCLUSIVE_USB/UNKNOWN
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state,host,expected_substr", [
    ("DEGRADED",     "EXCLUSIVE_USB", "capture_state=DEGRADED"),
    ("DISCONNECTED", "UNKNOWN",       "capture_state=DISCONNECTED"),
    ("NOMINAL",      "CONTESTED",     "host_state=CONTESTED"),
    ("NOMINAL",      "EXCLUSIVE_BT",  "host_state=EXCLUSIVE_BT"),
])
def test_t235_at_2_pcc_failure_skips(state, host, expected_substr):
    cfg = _Cfg()
    s   = _store_mock(pcc_state=state, pcc_host=host,
                      recent=_records(60, 120, activity_fraction=0.5))
    agent = SessionBoundaryDetectorAgent(cfg, s)

    verdict, reason = agent.evaluate(now_monotonic=1000.0)

    assert verdict == "SKIP"
    assert expected_substr in reason
    s.write_agent_event.assert_not_called()


# ---------------------------------------------------------------------------
# T235-AT-3: skipped when no gameplay activity in head window
# ---------------------------------------------------------------------------

def test_t235_at_3_no_activity_skips():
    cfg = _Cfg()
    # 60 quiescence + 120 activity, but only 5% of head is trigger_active
    # — well below ACTIVITY_FRACTION_MIN (0.20).
    s = _store_mock(recent=_records(60, 120, activity_fraction=0.05))
    agent = SessionBoundaryDetectorAgent(cfg, s)

    verdict, reason = agent.evaluate(now_monotonic=1000.0)

    assert verdict == "SKIP"
    assert "insufficient activity" in reason
    s.write_agent_event.assert_not_called()


# ---------------------------------------------------------------------------
# T235-AT-4: fires when all conditions met, write_agent_event called once
# ---------------------------------------------------------------------------

def test_t235_at_4_fires_when_conditions_met():
    cfg = _Cfg()
    s   = _store_mock(recent=_records(60, 120, activity_fraction=0.5))
    agent = SessionBoundaryDetectorAgent(cfg, s)

    verdict, reason = agent.evaluate(now_monotonic=1000.0)
    assert verdict == "FIRE", f"expected FIRE, got SKIP: {reason}"
    assert "session-end detected" in reason

    # Now actually fire — this is what the poll loop does in production
    event_id = agent.fire_trigger("DEV", now_monotonic=1000.0)
    assert event_id == 99

    s.write_agent_event.assert_called_once()
    call_kwargs = s.write_agent_event.call_args.kwargs
    assert call_kwargs["event_type"] == "ruling_request"
    assert call_kwargs["source"]     == "session_boundary_detector_agent"
    assert call_kwargs["target"]     == "session_adjudicator"
    assert call_kwargs["device_id"]  == "DEV"
    # Payload is JSON
    import json
    payload = json.loads(call_kwargs["payload"])
    assert payload["device_id"] == "DEV"


# ---------------------------------------------------------------------------
# T235-AT-5: throttle blocks rapid-fire — second cycle within 300s skipped
# ---------------------------------------------------------------------------

def test_t235_at_5_throttle_enforced():
    cfg = _Cfg()
    s   = _store_mock(recent=_records(60, 120, activity_fraction=0.5))
    agent = SessionBoundaryDetectorAgent(cfg, s)

    # First fire
    verdict1, _ = agent.evaluate(now_monotonic=1000.0)
    assert verdict1 == "FIRE"
    agent.fire_trigger("DEV", now_monotonic=1000.0)

    # Reset the call-history so we can verify NO new write happens on cycle 2
    s.write_agent_event.reset_mock()

    # Second cycle 60s later — well inside 300s throttle
    verdict2, reason2 = agent.evaluate(now_monotonic=1060.0)
    assert verdict2 == "SKIP"
    assert "since last fire" in reason2

    # Third cycle 350s later — past throttle, should fire again
    verdict3, _ = agent.evaluate(now_monotonic=1350.0)
    assert verdict3 == "FIRE"

    # Verify the throttled cycle did not write anything
    assert s.write_agent_event.call_count == 0  # nothing in between


# ---------------------------------------------------------------------------
# T235-AT-6: self-stops when chain_length >= grind_target
# ---------------------------------------------------------------------------

def test_t235_at_6_self_stops_at_target():
    cfg = _Cfg(grind_target=100)
    s   = _store_mock(chain_length=100,  # at target
                      recent=_records(60, 120, activity_fraction=0.5))
    agent = SessionBoundaryDetectorAgent(cfg, s)

    verdict, reason = agent.evaluate(now_monotonic=1000.0)

    assert verdict == "SKIP"
    assert "GIC_100 reached" in reason
    assert "self-stop" in reason
    assert agent._stopped is True
    s.write_agent_event.assert_not_called()


# ---------------------------------------------------------------------------
# T235-AT-7: quiescence violated — even one trigger_active=1 in tail blocks
# ---------------------------------------------------------------------------

def test_t235_at_7_partial_quiescence_skips():
    """Calibration test: NCAA CFB 26 has ~30s quiescence between plays.
    The detector must NOT fire if any record in the trailing quiescence
    window has trigger_active=1 — that means the player is still mid-play
    and just paused briefly between snaps."""
    cfg = _Cfg()
    # Build records where the tail has ONE active record mid-window
    tail = [{"trigger_active": 0, "device_id": "DEV"}] * 30
    tail.append({"trigger_active": 1, "device_id": "DEV"})  # mid-tail snap
    tail.extend([{"trigger_active": 0, "device_id": "DEV"}] * 29)
    head = (
        [{"trigger_active": 1, "device_id": "DEV"}] * 60
        + [{"trigger_active": 0, "device_id": "DEV"}] * 60
    )
    s = _store_mock(recent=tail + head)
    agent = SessionBoundaryDetectorAgent(cfg, s)

    verdict, reason = agent.evaluate(now_monotonic=1000.0)

    assert verdict == "SKIP"
    assert "quiescence not yet" in reason
    s.write_agent_event.assert_not_called()
