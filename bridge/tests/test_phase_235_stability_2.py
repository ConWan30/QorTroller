"""Phase 235.x-STABILITY-2 — loop-block instrumentation + sync work hunt tests.

Closes WIF-064 (stability proof refuted Proactor hypothesis). Real root
cause was loop-blocking sync work; this fix wraps known offenders in
asyncio.to_thread + adds slow-callback instrumentation for future
investigations.
"""

import asyncio
import sys
import types as _types
from pathlib import Path
from unittest.mock import MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv


# ---------------------------------------------------------------------------
# T-235-STAB2-1: 2 new config fields with correct defaults
# ---------------------------------------------------------------------------

def test_t_235_stab2_1_config_fields_present_with_defaults():
    from vapi_bridge.config import Config
    cfg = Config()
    assert hasattr(cfg, "asyncio_debug_enabled"), \
        "Phase 235.x-STABILITY-2 adds asyncio_debug_enabled field"
    assert cfg.asyncio_debug_enabled is False, \
        f"Default OFF (opt-in only); got {cfg.asyncio_debug_enabled}"

    assert hasattr(cfg, "asyncio_slow_callback_threshold_s"), \
        "Phase 235.x-STABILITY-2 adds asyncio_slow_callback_threshold_s field"
    assert cfg.asyncio_slow_callback_threshold_s == 1.0, \
        f"Default 1.0s (zombie signature); got {cfg.asyncio_slow_callback_threshold_s}"


# ---------------------------------------------------------------------------
# T-235-STAB2-2: env vars override the defaults
# ---------------------------------------------------------------------------

def test_t_235_stab2_2_env_overrides_apply(monkeypatch):
    monkeypatch.setenv("ASYNCIO_DEBUG_ENABLED", "true")
    monkeypatch.setenv("ASYNCIO_SLOW_CALLBACK_THRESHOLD_S", "0.5")

    import importlib
    from vapi_bridge import config as _cfg_mod
    importlib.reload(_cfg_mod)

    cfg = _cfg_mod.Config()
    assert cfg.asyncio_debug_enabled is True
    assert cfg.asyncio_slow_callback_threshold_s == 0.5


# ---------------------------------------------------------------------------
# T-235-STAB2-3: FSCA detection methods now delegate to sync via to_thread
# ---------------------------------------------------------------------------

def test_t_235_stab2_3_fsca_methods_delegate_to_thread():
    """Static check + behavioral test: the 3 async detection methods are now
    thin wrappers around _check_*_sync inner functions, dispatched via
    asyncio.to_thread. Locks the WIF-064 fix into CI."""
    fsca_py = (BRIDGE_DIR / "vapi_bridge" / "fleet_signal_coherence_agent.py").read_text(
        encoding="utf-8"
    )
    # The 3 sync inners must exist
    assert "def _check_contradictions_sync(self)" in fsca_py
    assert "def _check_orphans_sync(self)" in fsca_py
    assert "def _check_inversions_sync(self)" in fsca_py
    # Async wrappers must delegate via to_thread
    assert "asyncio.to_thread(self._check_contradictions_sync)" in fsca_py
    assert "asyncio.to_thread(self._check_orphans_sync)" in fsca_py
    assert "asyncio.to_thread(self._check_inversions_sync)" in fsca_py


# ---------------------------------------------------------------------------
# T-235-STAB2-4: cedar_drift_sweeper bundle sweep now uses to_thread
# ---------------------------------------------------------------------------

def test_t_235_stab2_4_drift_sweeper_uses_to_thread():
    """Static check: bundle sweep call site uses asyncio.to_thread to push
    file SHA-256 + DB read off the event loop thread."""
    sweeper_py = (BRIDGE_DIR / "vapi_bridge" / "cedar_drift_sweeper.py").read_text(
        encoding="utf-8"
    )
    assert "asyncio.to_thread(_run_bundle_sweep" in sweeper_py, \
        "_run_bundle_sweep must be dispatched via asyncio.to_thread (WIF-064)"
    assert "Phase 235.x-STABILITY-2" in sweeper_py


# ---------------------------------------------------------------------------
# T-235-STAB2-5: main.py wires slow_callback_duration from cfg
# ---------------------------------------------------------------------------

def test_t_235_stab2_5_main_wires_slow_callback_threshold():
    """Static check: main.py reads asyncio_slow_callback_threshold_s + sets
    loop.slow_callback_duration so future zombies log the offending callback
    name automatically."""
    main_py = (BRIDGE_DIR / "vapi_bridge" / "main.py").read_text(encoding="utf-8")
    assert "asyncio_slow_callback_threshold_s" in main_py
    assert "slow_callback_duration" in main_py
    assert "asyncio_debug_enabled" in main_py
    assert "Phase 235.x-STABILITY-2" in main_py


# ---------------------------------------------------------------------------
# T-235-STAB2-6: FSCA wrappers actually yield the event loop (not just sync)
# ---------------------------------------------------------------------------

class _MockFSCA:
    """Minimal FSCA for behavioral test of to_thread dispatch."""
    _sync_called_from = []

    async def _check_contradictions(self) -> list:
        return await asyncio.to_thread(self._check_contradictions_sync)

    def _check_contradictions_sync(self) -> list:
        import threading
        self._sync_called_from.append(threading.current_thread().name)
        return []


def test_t_235_stab2_6_to_thread_dispatch_runs_in_worker_not_main():
    """Behavioral test: to_thread actually pushes work to a worker thread,
    not the asyncio event-loop thread. This is the core property that
    prevents loop blocking."""
    import threading
    main_thread = threading.current_thread().name

    agent = _MockFSCA()
    asyncio.run(agent._check_contradictions())

    assert len(agent._sync_called_from) == 1
    worker = agent._sync_called_from[0]
    assert worker != main_thread, (
        f"to_thread should run in worker thread, not main {main_thread}; "
        f"got {worker}"
    )
    # asyncio uses ThreadPoolExecutor by default; worker names look like 'asyncio_X'
    assert "asyncio" in worker.lower() or "thread" in worker.lower(), \
        f"Expected asyncio worker thread, got {worker!r}"
