"""Tests for the canonical DB path resolver (2026-05-19 path-discovery fix).

T-DB-PATH-1  resolve_canonical_db_path returns Config.db_path default when no env override
T-DB-PATH-2  DB_PATH env override is honored (takes precedence over default)
T-DB-PATH-3  resolver never returns empty string
T-DB-PATH-4  resolver matches Config.db_path field semantics (cross-consistency)
T-DB-PATH-5  resolver default is OS home-relative (not project-relative)
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ----- T-DB-PATH-1 --------------------------------------------------------

def test_t_db_path_1_default_matches_config():
    """When DB_PATH env var not set, resolver returns ~/.vapi/bridge.db
    (matching Config.db_path default_factory at config.py L419-424)."""
    from vapi_bridge.db_path_resolver import resolve_canonical_db_path

    # Ensure env override is NOT set
    old_db_path = os.environ.pop("DB_PATH", None)
    try:
        resolved = resolve_canonical_db_path()
        expected = str(Path.home() / ".vapi" / "bridge.db")
        assert resolved == expected, f"resolver={resolved} vs expected={expected}"
    finally:
        if old_db_path is not None:
            os.environ["DB_PATH"] = old_db_path


# ----- T-DB-PATH-2 --------------------------------------------------------

def test_t_db_path_2_env_override_honored():
    """DB_PATH env var takes precedence over default."""
    from vapi_bridge.db_path_resolver import resolve_canonical_db_path

    old_db_path = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = "/tmp/test_db_override.db"
    try:
        resolved = resolve_canonical_db_path()
        assert resolved == "/tmp/test_db_override.db"
    finally:
        if old_db_path is None:
            os.environ.pop("DB_PATH", None)
        else:
            os.environ["DB_PATH"] = old_db_path


# ----- T-DB-PATH-3 --------------------------------------------------------

def test_t_db_path_3_never_returns_empty():
    """Resolver always returns non-empty string."""
    from vapi_bridge.db_path_resolver import resolve_canonical_db_path
    resolved = resolve_canonical_db_path()
    assert resolved
    assert isinstance(resolved, str)


# ----- T-DB-PATH-4 --------------------------------------------------------

def test_t_db_path_4_matches_config_field_semantics():
    """resolve_canonical_db_path() returns the same value Config().db_path
    would resolve to in the same env. This is the load-bearing invariant —
    if these drift, scripts will silently audit the wrong DB."""
    from vapi_bridge.db_path_resolver import resolve_canonical_db_path

    old_db_path = os.environ.pop("DB_PATH", None)
    try:
        from importlib import reload
        from vapi_bridge import config as cfg_mod
        reload(cfg_mod)
        cfg = cfg_mod.Config()
        cfg_db = cfg.db_path
        resolver_db = resolve_canonical_db_path()
        assert resolver_db == cfg_db, \
            f"DRIFT: resolver={resolver_db} vs cfg.db_path={cfg_db}"
    finally:
        if old_db_path is not None:
            os.environ["DB_PATH"] = old_db_path


# ----- T-DB-PATH-5 --------------------------------------------------------

def test_t_db_path_5_default_is_home_relative_not_project_relative():
    """The default MUST be home-relative (~/.vapi/bridge.db), NOT
    project-relative (bridge/vapi_store.db). This is the load-bearing
    fix from the 2026-05-19 path-discovery investigation."""
    from vapi_bridge.db_path_resolver import resolve_canonical_db_path

    old_db_path = os.environ.pop("DB_PATH", None)
    try:
        resolved = resolve_canonical_db_path()
        # Must contain .vapi directory
        assert ".vapi" in resolved, f"resolved path missing .vapi: {resolved}"
        # Must NOT default to the stale sandbox path
        assert "vapi_store.db" not in resolved, \
            f"resolver should never default to stale bridge/vapi_store.db: {resolved}"
        # Must be home-relative
        home_str = str(Path.home())
        assert resolved.startswith(home_str), \
            f"default must be home-relative ({home_str}/...): {resolved}"
    finally:
        if old_db_path is not None:
            os.environ["DB_PATH"] = old_db_path
