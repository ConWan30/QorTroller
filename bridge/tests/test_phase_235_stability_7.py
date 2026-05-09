"""Phase 235.x-STABILITY-7 tests — bus listener hardening + ThreadPoolExecutor sizing.

Two parts:

Part A: extends STABILITY-6's defensive backoff pattern to the 5 residual
`_listen_*_bus` subscriber methods identified in
session_adjudicator.py + ruling_enforcement_agent.py. Each had the same
tight-loop bug shape (no backoff in the `except Exception` handler).

Part B: explicit asyncio default ThreadPoolExecutor sizing
(max_workers=64, thread_name_prefix="vapi-persist") wired at bridge
startup. Closes worker-pool saturation observed in STABILITY-5 smoke
testing (1 watchdog restart / 90s).

T-235-STAB7-1..9.
"""
from __future__ import annotations

import sys
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


# ---------------------------------------------------------------------------
# Part A — bus listener hardening
# ---------------------------------------------------------------------------

# (file, listener_method_name, agent_name) for static checks.
HARDENED_BUS_LISTENERS = [
    ("session_adjudicator.py",       "_listen_ceremony_bus",   "SessionAdjudicator"),
    ("session_adjudicator.py",       "_listen_class_j_bus",    "SessionAdjudicator"),
    ("session_adjudicator.py",       "_listen_triage_bus",     "SessionAdjudicator"),
    ("session_adjudicator.py",       "_listen_live_mode_bus",  "SessionAdjudicator"),
    ("ruling_enforcement_agent.py",  "_listen_live_mode_bus",  "RulingEnforcementAgent"),
]


def _read_agent_source(filename: str) -> str:
    return (PROJECT_ROOT / "bridge" / "vapi_bridge" / filename).read_text(encoding="utf-8")


def _extract_listener_body(filename: str, listener_name: str) -> str:
    """Return the source between `async def <listener_name>(` and the next
    method definition. Used so static checks scope to the listener body."""
    src = _read_agent_source(filename)
    start = src.find(f"async def {listener_name}(")
    assert start != -1, f"{filename}: {listener_name} not found"
    # Find the next method def at the same indent (4 spaces) after start
    after = src[start + 1:]
    # Look for the next `\n    async def ` or `\n    def `
    next_method_marker = None
    for marker in ("\n    async def ", "\n    def "):
        idx = after.find(marker)
        if idx != -1:
            if next_method_marker is None or idx < next_method_marker:
                next_method_marker = idx
    if next_method_marker is None:
        return src[start:]
    return src[start:start + 1 + next_method_marker]


# ---------------------------------------------------------------------------
# T-235-STAB7-1: every bus listener has the STABILITY-7 marker comment
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,listener,agent_name", HARDENED_BUS_LISTENERS)
def test_t_235_stab7_1_marker_present(filename, listener, agent_name):
    body = _extract_listener_body(filename, listener)
    assert "Phase 235.x-STABILITY-7" in body, (
        f"{filename}::{listener}: STABILITY-7 marker comment missing — "
        "fix not applied to this bus listener"
    )


# ---------------------------------------------------------------------------
# T-235-STAB7-2: every bus listener has the "backoff sleep failed" structure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,listener,agent_name", HARDENED_BUS_LISTENERS)
def test_t_235_stab7_2_backoff_in_except(filename, listener, agent_name):
    body = _extract_listener_body(filename, listener)
    assert "backoff sleep failed" in body, (
        f"{filename}::{listener}: defensive backoff structure missing — "
        "the inner `try: await asyncio.sleep(...) except: return` block "
        "is the load-bearing part of STABILITY-7"
    )


# ---------------------------------------------------------------------------
# T-235-STAB7-3: backoff is bounded to 5s
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,listener,agent_name", HARDENED_BUS_LISTENERS)
def test_t_235_stab7_3_backoff_bounded_to_5s(filename, listener, agent_name):
    body = _extract_listener_body(filename, listener)
    assert "min(300.0, 5.0)" in body or "min(300, 5.0)" in body, (
        f"{filename}::{listener}: backoff should use `min(300.0, 5.0)` to "
        "bound recovery time on transient errors (5min poll interval is "
        "the listener's wait_for timeout)"
    )


# ---------------------------------------------------------------------------
# T-235-STAB7-4: backoff failure handler exits cleanly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,listener,agent_name", HARDENED_BUS_LISTENERS)
def test_t_235_stab7_4_backoff_failure_returns(filename, listener, agent_name):
    body = _extract_listener_body(filename, listener)
    idx = body.find("backoff sleep failed")
    assert idx != -1
    tail = body[idx:idx + 400]
    assert "return" in tail, (
        f"{filename}::{listener}: backoff failure handler must `return` to "
        "exit the listener cleanly"
    )


# ---------------------------------------------------------------------------
# T-235-STAB7-5: CancelledError preserved in backoff
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename,listener,agent_name", HARDENED_BUS_LISTENERS)
def test_t_235_stab7_5_cancelled_error_preserved(filename, listener, agent_name):
    body = _extract_listener_body(filename, listener)
    idx = body.find("backoff sleep failed")
    assert idx != -1
    head = body[max(0, idx - 600):idx]
    assert "CancelledError" in head, (
        f"{filename}::{listener}: backoff block must explicitly handle "
        "asyncio.CancelledError"
    )


# ---------------------------------------------------------------------------
# Part B — ThreadPoolExecutor sizing
# ---------------------------------------------------------------------------

# T-235-STAB7-6: config field exists with default 64
def test_t_235_stab7_6_config_field_default_64(monkeypatch):
    monkeypatch.delenv("THREAD_POOL_MAX_WORKERS", raising=False)
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.thread_pool_max_workers == 64


# T-235-STAB7-7: env override toggles to custom value (incl 0 rollback)
def test_t_235_stab7_7_env_override_zero_rollback(monkeypatch):
    monkeypatch.setenv("THREAD_POOL_MAX_WORKERS", "0")
    import importlib
    from vapi_bridge import config as _cfg_mod
    importlib.reload(_cfg_mod)
    cfg = _cfg_mod.Config()
    assert cfg.thread_pool_max_workers == 0


# T-235-STAB7-7b: env override to non-default positive value
def test_t_235_stab7_7b_env_override_positive(monkeypatch):
    monkeypatch.setenv("THREAD_POOL_MAX_WORKERS", "128")
    import importlib
    from vapi_bridge import config as _cfg_mod
    importlib.reload(_cfg_mod)
    cfg = _cfg_mod.Config()
    assert cfg.thread_pool_max_workers == 128


# T-235-STAB7-8: main.py wires ThreadPoolExecutor with set_default_executor
def test_t_235_stab7_8_main_wires_executor():
    """Static check on main.py source — guards against future contributor
    accidentally removing the executor wiring or replacing
    set_default_executor with a different mechanism."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    # Marker comment must be present
    assert "Phase 235.x-STABILITY-7: explicit ThreadPoolExecutor sizing" in src
    # Must instantiate concurrent.futures.ThreadPoolExecutor
    assert "ThreadPoolExecutor(" in src
    # Must use the chosen thread_name_prefix
    assert 'thread_name_prefix="vapi-persist"' in src
    # Must wire via set_default_executor
    assert ".set_default_executor(" in src
    # Must read max_workers from config
    assert "thread_pool_max_workers" in src
    # Must support 0 = rollback path (asyncio default kept)
    assert "if _tpool_workers > 0:" in src or "if _tpool_workers >= 1:" in src


# T-235-STAB7-9: Bridge.__init__ initializes _thread_pool_executor to None
def test_t_235_stab7_9_init_attribute_safe():
    """Static check that Bridge.__init__ initializes the attribute to None
    so attribute access before run() doesn't AttributeError."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "main.py").read_text(
        encoding="utf-8"
    )
    # Find __init__ body
    init_start = src.find("    def __init__(self, cfg:")
    on_record_start = src.find("    async def on_record(")
    assert init_start != -1 and on_record_start != -1
    init_body = src[init_start:on_record_start]
    assert "self._thread_pool_executor = None" in init_body, (
        "Bridge.__init__ must initialize _thread_pool_executor=None for "
        "attribute safety before run() wires the executor"
    )
