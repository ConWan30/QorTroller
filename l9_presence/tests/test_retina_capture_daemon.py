"""Test the daemon-specific glue in scripts/retina_capture_daemon.py (harvest + state cleanup).

The detached-launch / process management is integration-only (needs a real bridge), but cmd_stop's
harvest -> corpus -> summary -> state-cleanup path is pure enough to test with a synthetic log + state
(the kill on a non-existent PID is a caught no-op).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_REPO, "scripts"))

import retina_capture_daemon as dmn  # noqa: E402

_DIAG = ("2026-06-28 19:00:00 INFO RGC diag: {'coupling_score': 0.42, 'negative_control': 0.03, "
         "'lag_ms': 145.0, 'th_coupling': 0.38, 'th_null': 0.04, 'th_lag_ms': 150.0, "
         "'th2_coupling': 0.31, 'th2_null': 0.02, 'th2_lag_ms': 148.0, 'ts_source': 'timespan'}")


def test_cmd_stop_harvests_corpus_and_cleans_state(tmp_path, monkeypatch):
    monkeypatch.setattr(dmn, "_REPO", tmp_path)
    monkeypatch.setattr(dmn, "_STATE", tmp_path / "retina_daemon.state.json")
    log = tmp_path / "retina_daemon_genuine_111.log"
    log.write_text("\n".join([_DIAG, _DIAG, _DIAG]), encoding="utf-8")
    dmn._STATE.write_text(json.dumps({
        "pid": 999999, "port": 8080, "log": log.name, "label": "genuine",
        "monitor": 1, "diag_every": 4, "started_at": 111,
    }), encoding="utf-8")

    rc = dmn.cmd_stop(argparse.Namespace(label=None))      # kill of fake PID is a caught no-op
    assert rc == 0
    corpus = tmp_path / "genuine_111.jsonl"
    assert corpus.exists()                                  # harvested corpus written
    assert not dmn._STATE.exists()                          # state cleaned up
    rows = [json.loads(x) for x in corpus.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 3 and len(rows[0]) == 3             # 3 dense samples, each 3 channels (geo+B1+B2)


def test_cmd_status_no_session_returns_1(tmp_path, monkeypatch):
    monkeypatch.setattr(dmn, "_STATE", tmp_path / "nope.json")
    assert dmn.cmd_status(argparse.Namespace()) == 1
