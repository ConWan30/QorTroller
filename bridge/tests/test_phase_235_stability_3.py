"""Phase 235.x-STABILITY-3 — loop health monitor tests (WIF-065 closure).

Verifies the independent heartbeat task that detects asyncio event loop
starvation regardless of asyncio's debug mode.
"""

import asyncio
import logging
import sys
import time
import types as _types
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv


def _make_cfg(enabled=True, check_s=0.5, threshold_s=0.3):
    cfg = MagicMock()
    cfg.loop_health_monitor_enabled = enabled
    cfg.loop_health_check_interval_s = check_s
    cfg.loop_health_starvation_threshold_s = threshold_s
    return cfg


# ---------------------------------------------------------------------------
# T-235-STAB3-1: 3 new config fields with correct defaults
# ---------------------------------------------------------------------------

def test_t_235_stab3_1_config_fields_present_with_defaults():
    from vapi_bridge.config import Config
    cfg = Config()
    assert hasattr(cfg, "loop_health_monitor_enabled")
    assert cfg.loop_health_monitor_enabled is True, \
        "Default ON (opt-out via env); got " + repr(cfg.loop_health_monitor_enabled)
    assert hasattr(cfg, "loop_health_check_interval_s")
    assert cfg.loop_health_check_interval_s == 2.0
    assert hasattr(cfg, "loop_health_starvation_threshold_s")
    assert cfg.loop_health_starvation_threshold_s == 1.0


# ---------------------------------------------------------------------------
# T-235-STAB3-2: env vars override defaults
# ---------------------------------------------------------------------------

def test_t_235_stab3_2_env_overrides_apply(monkeypatch):
    monkeypatch.setenv("LOOP_HEALTH_MONITOR_ENABLED", "false")
    monkeypatch.setenv("LOOP_HEALTH_CHECK_INTERVAL_S", "5.0")
    monkeypatch.setenv("LOOP_HEALTH_STARVATION_THRESHOLD_S", "2.5")
    import importlib
    from vapi_bridge import config as _cfg_mod
    importlib.reload(_cfg_mod)
    cfg = _cfg_mod.Config()
    assert cfg.loop_health_monitor_enabled is False
    assert cfg.loop_health_check_interval_s == 5.0
    assert cfg.loop_health_starvation_threshold_s == 2.5


# ---------------------------------------------------------------------------
# T-235-STAB3-3: monitor disabled returns immediately
# ---------------------------------------------------------------------------

class TestDisabledShortCircuit(unittest := __import__("unittest").IsolatedAsyncioTestCase):
    async def test_t_235_stab3_3_disabled_returns_immediately(self):
        from vapi_bridge.loop_health_monitor import run_loop_health_monitor
        cfg = _make_cfg(enabled=False)
        # Should return within ms — never enter monitoring loop
        await asyncio.wait_for(run_loop_health_monitor(cfg=cfg), timeout=1.0)


# ---------------------------------------------------------------------------
# T-235-STAB3-4: monitor logs WARNING when loop is starved
# ---------------------------------------------------------------------------

class TestStarvationDetection(__import__("unittest").IsolatedAsyncioTestCase):
    async def test_t_235_stab3_4_starvation_logs_warning(self):
        from vapi_bridge import loop_health_monitor as _lhm
        # Short intervals + low threshold to make test fast
        cfg = _make_cfg(enabled=True, check_s=0.2, threshold_s=0.1)

        # Capture WARNING logs from the loop_health_monitor module
        captured = []

        class _Capture(logging.Handler):
            def emit(self, record):
                if record.levelno == logging.WARNING:
                    captured.append(record.getMessage())

        cap = _Capture()
        _lhm.log.addHandler(cap)
        _lhm.log.setLevel(logging.WARNING)

        try:
            task = asyncio.create_task(_lhm.run_loop_health_monitor(cfg=cfg))

            # Block the event loop intentionally for 1 full second to simulate
            # a sync-blocker (this is what zombies look like to the monitor).
            await asyncio.sleep(0.1)
            time.sleep(1.0)  # NOT asyncio.sleep — blocks the event loop
            await asyncio.sleep(0.4)

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        finally:
            _lhm.log.removeHandler(cap)

        # At least one STARVATION warning should have fired during the
        # synchronous time.sleep block
        starvation_warns = [m for m in captured if "STARVATION" in m]
        self.assertGreaterEqual(
            len(starvation_warns), 1,
            f"Expected ≥1 STARVATION warning when event loop blocked 1s; "
            f"got {len(starvation_warns)} (all warnings: {captured})"
        )


# ---------------------------------------------------------------------------
# T-235-STAB3-5: monitor cancellation propagates cleanly
# ---------------------------------------------------------------------------

class TestGracefulCancellation(__import__("unittest").IsolatedAsyncioTestCase):
    async def test_t_235_stab3_5_cancellation_exits_cleanly(self):
        from vapi_bridge.loop_health_monitor import run_loop_health_monitor
        cfg = _make_cfg(enabled=True, check_s=0.2, threshold_s=0.1)
        task = asyncio.create_task(run_loop_health_monitor(cfg=cfg))
        await asyncio.sleep(0.5)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# T-235-STAB3-6: main.py wires the monitor task when enabled
# ---------------------------------------------------------------------------

def test_t_235_stab3_6_main_wires_monitor_task():
    """Static check: main.py imports + creates the loop_health_monitor task."""
    main_py = (BRIDGE_DIR / "vapi_bridge" / "main.py").read_text(encoding="utf-8")
    assert "from .loop_health_monitor import run_loop_health_monitor" in main_py
    assert "loop_health_monitor_enabled" in main_py
    assert "Phase 235.x-STABILITY-3" in main_py
    assert 'set_name("LoopHealthMonitor")' in main_py
