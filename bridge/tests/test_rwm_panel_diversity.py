"""Panel diversity helper + RWM_BLOCK_PX env resolution."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "bridge"))
sys.path.insert(0, str(_REPO / "scripts"))


def test_panel_content_stats_frozen(tmp_path):
    from vapi_bridge.rwm_panel_diversity import panel_content_stats

    for i in range(5):
        p = tmp_path / f"panel_{i:04d}.png"
        p.write_bytes(b"same-bytes")
    stats = panel_content_stats(tmp_path.glob("panel_*.png"))
    assert stats["n"] == 5
    assert stats["unique"] == 1
    assert stats["frozen"] is True
    assert stats["label"] == "FROZEN_RING"


def test_panel_content_stats_diverse(tmp_path):
    from vapi_bridge.rwm_panel_diversity import panel_content_stats

    for i in range(5):
        p = tmp_path / f"panel_{i:04d}.png"
        p.write_bytes(f"bytes-{i}".encode())
    stats = panel_content_stats(tmp_path.glob("panel_*.png"))
    assert stats["unique"] == 5
    assert stats["frozen"] is False
    assert stats["label"] == "OK"


def test_panel_sample_limit_uses_recent(tmp_path):
    from vapi_bridge.rwm_panel_diversity import panel_content_stats
    import time

    for i in range(10):
        p = tmp_path / f"panel_{i:04d}.png"
        p.write_bytes(b"old" if i < 8 else f"new-{i}".encode())
        time.sleep(0.01)
    stats = panel_content_stats(tmp_path.glob("panel_*.png"), sample_limit=2)
    assert stats["n"] == 2
    assert stats["unique"] == 2


def test_rwm_block_px_default(monkeypatch):
    import retina_capture_daemon as d

    monkeypatch.delenv("RWM_BLOCK_PX", raising=False)
    # avoid reading real bridge/.env for this key
    monkeypatch.setattr(d, "_env_or_bridge_dotenv", lambda k: "")
    assert d._rwm_block_px() == 32


def test_rwm_block_px_env_override(monkeypatch):
    import retina_capture_daemon as d

    monkeypatch.setattr(d, "_env_or_bridge_dotenv", lambda k: "48" if k == "RWM_BLOCK_PX" else "")
    assert d._rwm_block_px() == 48


def test_rwm_block_px_invalid_falls_back(monkeypatch):
    import retina_capture_daemon as d

    monkeypatch.setattr(d, "_env_or_bridge_dotenv", lambda k: "nope" if k == "RWM_BLOCK_PX" else "")
    assert d._rwm_block_px() == 32
    monkeypatch.setattr(d, "_env_or_bridge_dotenv", lambda k: "0" if k == "RWM_BLOCK_PX" else "")
    assert d._rwm_block_px() == 32


def test_watcher_argparse_defaults():
    """Import watcher CLI helpers without requiring an active daemon state."""
    import importlib.util

    path = _REPO / "scripts" / "rwm_live_session_watch.py"
    spec = importlib.util.spec_from_file_location("rwm_live_session_watch", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # no active session → exit 2 with structured event (not a crash)
    rc = mod.main(["--diversity-alert-at", "10", "--sample-limit", "20"])
    assert rc == 2


def test_watcher_newest_panel(tmp_path, monkeypatch):
    import importlib.util
    import time

    path = _REPO / "scripts" / "rwm_live_session_watch.py"
    spec = importlib.util.spec_from_file_location("rwm_live_session_watch2", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    monkeypatch.setattr(mod, "_CROPS", tmp_path)
    assert mod._newest_panel() is None
    (tmp_path / "panel_0001.png").write_bytes(b"a")
    time.sleep(0.02)
    (tmp_path / "panel_0002.png").write_bytes(b"b")
    newest = mod._newest_panel()
    assert newest is not None
    assert newest.name == "panel_0002.png"
