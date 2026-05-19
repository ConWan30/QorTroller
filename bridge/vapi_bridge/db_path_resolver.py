"""Canonical DB path resolver — matches bridge runtime's actual path.

Born 2026-05-19 after Path 2 verification surfaced a silent path-discovery
bug: scripts + Mythos variants defaulted to `bridge/vapi_store.db` (a
stale sandbox file), while the bridge process writes to the production
DB at `cfg.db_path` (~/.vapi/bridge.db on Unix, %USERPROFILE%/.vapi/
bridge.db on Windows). All verification work against the wrong path
silently produced false-clean signals.

This helper resolves the canonical path identically to the bridge
runtime: reads `DB_PATH` env var if set, otherwise uses ~/.vapi/bridge.db
(matching Config.db_path default_factory at config.py L419-424).

Use everywhere a tool needs to read or audit the bridge's production
state. Do NOT use `bridge/vapi_store.db` as a default in any script
or Mythos variant going forward — that path is a stale sandbox and
will produce misleading results.
"""
from __future__ import annotations

import os
from pathlib import Path


def resolve_canonical_db_path() -> str:
    """Return the absolute path to the bridge's production SQLite DB.

    Resolution order:
      1. DB_PATH environment variable (matches Config.db_path env override)
      2. ~/.vapi/bridge.db (matches Config.db_path default)

    Returns a stringified absolute path. Never raises; never returns
    empty string."""
    env_override = os.environ.get("DB_PATH")
    if env_override:
        return env_override
    return str(Path.home() / ".vapi" / "bridge.db")
