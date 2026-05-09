"""Phase 235.x-STABILITY-5 tests — _resolve_pubkey miss path offload.

Closes residual STARVATION source identified in STABILITY-4 validation:
the cache-miss path of _resolve_pubkey runs store.list_devices() (SQLite
scan) on the event loop thread.

V-checks during STABILITY-5 design also confirmed that the originally-
planned 5b (capture-health endpoint) and 5c (ws_broadcast / JSON
serialization) surfaces were either already addressed (Phase 235-BRIDGE-
WEDGE-FIX wrapped capture-health DB calls) or not actually heavy
(ws_broadcast is properly async; _record_to_ws_msg is microsecond-fast).
Only 5a (this fix) is a legitimate residual.

T-235-STAB5-1..5.
"""
from __future__ import annotations

import asyncio
import sys
import threading
import types as _types
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Match other STABILITY-N tests' import-stub pattern
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv


# ---------------------------------------------------------------------------
# T-235-STAB5-1: config field exists with default True
# ---------------------------------------------------------------------------

def test_t_235_stab5_1_config_field_default_true(monkeypatch):
    monkeypatch.delenv("LOOP_RESOLVE_PUBKEY_TO_THREAD_ENABLED", raising=False)
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.loop_resolve_pubkey_to_thread_enabled is True


# ---------------------------------------------------------------------------
# T-235-STAB5-2: env override toggles to False
# ---------------------------------------------------------------------------

def test_t_235_stab5_2_env_override_disables(monkeypatch):
    monkeypatch.setenv("LOOP_RESOLVE_PUBKEY_TO_THREAD_ENABLED", "false")
    import importlib
    from vapi_bridge import config as _cfg_mod
    importlib.reload(_cfg_mod)
    cfg = _cfg_mod.Config()
    assert cfg.loop_resolve_pubkey_to_thread_enabled is False


# ---------------------------------------------------------------------------
# T-235-STAB5-3: _resolve_pubkey_miss_sync exists and is sync (not async)
# ---------------------------------------------------------------------------

def test_t_235_stab5_3_miss_sync_helper_is_not_coroutine():
    """Static check on main.py source — guards against future contributor
    accidentally marking the sync helper async (would silently break the
    asyncio.to_thread offload)."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    assert "    def _resolve_pubkey_miss_sync(" in src, \
        "_resolve_pubkey_miss_sync must be a sync method (def, not async def)"
    assert "async def _resolve_pubkey_miss_sync(" not in src, \
        "regression — _resolve_pubkey_miss_sync was marked async, breaking to_thread"


# ---------------------------------------------------------------------------
# T-235-STAB5-4: _resolve_pubkey routes miss path through asyncio.to_thread
# ---------------------------------------------------------------------------

def test_t_235_stab5_4_miss_path_uses_to_thread():
    """Static check + regression guard. The miss path must call
    asyncio.to_thread(self._resolve_pubkey_miss_sync, ...) when the
    config flag is True."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    # The _resolve_pubkey body (between the cache-hit return and the
    # _resolve_pubkey_miss_sync definition) must contain the to_thread call.
    rp_start = src.find("async def _resolve_pubkey(")
    miss_sync_start = src.find("def _resolve_pubkey_miss_sync(")
    assert rp_start != -1 and miss_sync_start != -1
    rp_body = src[rp_start:miss_sync_start]
    assert "asyncio.to_thread(self._resolve_pubkey_miss_sync" in rp_body, \
        "miss path must offload to worker thread"
    assert "loop_resolve_pubkey_to_thread_enabled" in rp_body, \
        "miss path must check config flag for opt-out"
    # Regression guard: heavy sync calls must NOT live in _resolve_pubkey
    # (they belong in _resolve_pubkey_miss_sync now)
    assert "self.store.list_devices()" not in rp_body, \
        "list_devices() scan must be in miss_sync helper, not _resolve_pubkey"


# ---------------------------------------------------------------------------
# T-235-STAB5-5: cache-hit path stays synchronous (no thread-hop overhead
# for the steady-state branch handling every record after the first)
# ---------------------------------------------------------------------------

def test_t_235_stab5_5_cache_hit_stays_synchronous():
    """The cache hit branch must NOT cross a worker thread — that's a
    hot path executed for every record after the first and would add
    unnecessary overhead. Only the cache MISS path is offloaded."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    rp_start = src.find("async def _resolve_pubkey(")
    miss_sync_start = src.find("def _resolve_pubkey_miss_sync(")
    rp_body = src[rp_start:miss_sync_start]

    # Find the cache-hit branch: between "if prev_hex in self._pubkey_cache:"
    # and "# Slow path:"
    hit_start = rp_body.find("if prev_hex in self._pubkey_cache:")
    slow_start = rp_body.find("# Slow path:")
    assert hit_start != -1 and slow_start != -1 and hit_start < slow_start
    hit_branch = rp_body[hit_start:slow_start]

    # Cache hit MUST NOT use to_thread or await any heavy work
    assert "asyncio.to_thread(" not in hit_branch, \
        "cache-hit path must NOT cross worker thread (steady-state hot path)"
    # And it MUST contain the direct return for the hit case
    assert "return pk" in hit_branch
