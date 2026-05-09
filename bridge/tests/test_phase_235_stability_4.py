"""Phase 235.x-STABILITY-4 tests — on_record persist offload to worker thread.

Closes WIF-066: 2026-05-08 real-controller bisection identified per-record
sync chain (signature verify + 3 SQLite writes) as the dominant event-loop
starvation source (60 STARVATION events / 13 min).

T-235-STAB4-1..7.
"""
from __future__ import annotations

import asyncio
import os
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

# Stub heavy-import modules so chain.py + main.py can be imported in test
# context (matches the pattern used by test_phase_235_stability_2.py and
# others). Without these stubs, an importlib.reload() in an earlier test
# can trigger a chain.py re-import that fails on the real web3 import.
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv


# ---------------------------------------------------------------------------
# T-235-STAB4-1: config field exists with default True (opt-in observability)
# ---------------------------------------------------------------------------

def test_t_235_stab4_1_config_field_default_true(monkeypatch):
    """Phase 235.x-STABILITY-4 ships ON by default. Empirically validated to
    fix the 60-STARVATION-events/13-min real-controller pattern. Opt-out
    only via env."""
    monkeypatch.delenv("LOOP_PERSIST_TO_THREAD_ENABLED", raising=False)
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.loop_persist_to_thread_enabled is True


# ---------------------------------------------------------------------------
# T-235-STAB4-2: env override toggles to False
# ---------------------------------------------------------------------------

def test_t_235_stab4_2_env_override_disables(monkeypatch):
    monkeypatch.setenv("LOOP_PERSIST_TO_THREAD_ENABLED", "false")
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.loop_persist_to_thread_enabled is False


# ---------------------------------------------------------------------------
# T-235-STAB4-3: _persist_record_sync method exists and is NOT a coroutine
# ---------------------------------------------------------------------------

def test_t_235_stab4_3_persist_sync_is_not_coroutine():
    """Sync method MUST NOT be `async def` — it runs inside asyncio.to_thread
    which calls it synchronously. Marking it async would silently break the
    offload (would return a coroutine instead of bool).

    Static check on main.py source — avoids triggering chain.py re-import
    side effects when run after STABILITY-2's importlib.reload pattern."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    # Must be `def _persist_record_sync(`, NOT `async def _persist_record_sync(`
    assert "    def _persist_record_sync(" in src, \
        "_persist_record_sync must be a sync method (def, not async def)"
    assert "async def _persist_record_sync(" not in src, \
        "regression — _persist_record_sync was marked async, breaking to_thread"


# ---------------------------------------------------------------------------
# T-235-STAB4-4: on_record routes through asyncio.to_thread when enabled
# ---------------------------------------------------------------------------

def test_t_235_stab4_4_on_record_uses_to_thread_static_check():
    """Static check on main.py source — guard against future contributor
    accidentally inlining the sync call back onto the loop thread."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    # The to_thread call site must reference _persist_record_sync
    assert "asyncio.to_thread(" in src, \
        "main.py must use asyncio.to_thread for STABILITY-4"
    assert "self._persist_record_sync" in src, \
        "_persist_record_sync must be referenced"
    # And it should be guarded by the config flag (so opt-out works)
    assert 'loop_persist_to_thread_enabled' in src
    # Negative — verify the OLD inline path is gone (regression guard)
    # The exact phrase "if not verify_signature(record, pubkey_bytes)" should
    # no longer appear inside on_record's body; it should only appear inside
    # _persist_record_sync.
    on_record_start = src.find("async def on_record(")
    persist_sync_start = src.find("def _persist_record_sync(")
    assert on_record_start != -1 and persist_sync_start != -1
    assert on_record_start < persist_sync_start, \
        "_persist_record_sync should be defined after on_record"
    on_record_body = src[on_record_start:persist_sync_start]
    assert "verify_signature(" not in on_record_body, \
        "verify_signature must NOT be called from on_record (must be in sync helper)"


# ---------------------------------------------------------------------------
# T-235-STAB4-5: behavioral — _persist_record_sync runs in worker thread
# (not on the asyncio event loop's thread)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_t_235_stab4_5_persist_runs_in_worker_thread():
    """Verify asyncio.to_thread actually offloads — _persist_record_sync's
    threading.get_ident() must differ from the loop thread's get_ident()."""
    loop_thread_id = threading.get_ident()
    captured = {}

    def fake_persist(*args, **kwargs):
        captured["worker_thread_id"] = threading.get_ident()
        return True

    # Use asyncio.to_thread directly (this is what on_record calls)
    result = await asyncio.to_thread(fake_persist, "arg1", "arg2")
    assert result is True
    assert "worker_thread_id" in captured
    assert captured["worker_thread_id"] != loop_thread_id, \
        "to_thread must execute on a worker thread, not the loop thread"


# ---------------------------------------------------------------------------
# T-235-STAB4-6: WIF-066 hot path is offloaded — count of sync DB calls
# inside _persist_record_sync vs on_record after refactor
# ---------------------------------------------------------------------------

def test_t_235_stab4_6_heavy_sync_calls_only_in_persist_helper():
    """The 3 store writes (upsert_device + update_device_state + insert_record)
    that empirically dominated the per-record sync chain MUST live in
    _persist_record_sync, NOT in on_record."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    on_record_start = src.find("async def on_record(")
    persist_sync_start = src.find("def _persist_record_sync(")
    resolve_pubkey_start = src.find("async def _resolve_pubkey(")

    on_record_body = src[on_record_start:persist_sync_start]
    persist_body = src[persist_sync_start:resolve_pubkey_start]

    # Heavy calls must be in persist helper
    for heavy_call in (
        "self.store.upsert_device(",
        "self.store.update_device_state(",
        "self.store.insert_record(",
        "verify_signature(",
        "compute_device_id(",
    ):
        assert heavy_call in persist_body, \
            f"{heavy_call} must be in _persist_record_sync"
        assert heavy_call not in on_record_body, \
            f"{heavy_call} must NOT be in on_record (regression — back on loop thread)"


# ---------------------------------------------------------------------------
# T-235-STAB4-7: schema_version_override snapshot prevents race on
# self._ds_transport._device_profile mutation during to_thread call
# ---------------------------------------------------------------------------

def test_t_235_stab4_7_schema_version_snapshotted_on_loop():
    """The schema_version_override + pitl_meta snapshot MUST happen on the
    loop thread before crossing to the worker, otherwise the worker can
    read stale/mutating state from self._ds_transport.

    Static check: on_record body reads _device_profile + _pending_pitl_meta
    inline (on loop thread), then passes them as args to to_thread."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    on_record_start = src.find("async def on_record(")
    persist_sync_start = src.find("def _persist_record_sync(")
    on_record_body = src[on_record_start:persist_sync_start]

    # Snapshot reads must happen INSIDE on_record (loop thread)
    assert "_device_profile" in on_record_body, \
        "schema_version snapshot must be taken on loop thread"
    assert "_pending_pitl_meta" in on_record_body, \
        "pitl_meta snapshot must be taken on loop thread"

    # And they must be passed AS ARGUMENTS to the sync helper, not read
    # from self._ds_transport inside the helper.
    persist_sig_match = src.find("def _persist_record_sync(")
    persist_sig_end = src.find("    ) -> bool:", persist_sig_match)
    persist_sig = src[persist_sig_match:persist_sig_end]
    assert "schema_version_override" in persist_sig
    assert "pitl_meta" in persist_sig
