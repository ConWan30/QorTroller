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

    rc = dmn.cmd_stop(argparse.Namespace(label=None, no_archive_ring=True, kas=False))
    assert rc == 0
    corpus = tmp_path / "genuine_111.jsonl"
    assert corpus.exists()                                  # harvested corpus written
    assert not dmn._STATE.exists()                          # state cleaned up
    rows = [json.loads(x) for x in corpus.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) == 3 and len(rows[0]) == 3             # 3 dense samples, each 3 channels (geo+B1+B2)


def test_issue_session_continuum_fail_open_no_manifest(tmp_path, monkeypatch):
    """Continuum skip without L0 is silent success path (no raise)."""
    monkeypatch.setattr(dmn, "_REPO", tmp_path)
    empty = tmp_path / "empty_arch"
    empty.mkdir()
    dmn._issue_session_continuum("lab", 123, empty)  # no rwm_manifest — no-op
    dmn._issue_session_continuum("lab", 123, None)   # no archive — no-op


def test_issue_session_continuum_after_seeded_l0(tmp_path, monkeypatch):
    """Daemon continuum helper writes sidecar when L0 manifest re-verifies."""
    import numpy as np
    import cv2

    monkeypatch.setattr(dmn, "_REPO", tmp_path)
    arch = tmp_path / "retina_kf_archive" / "lab_99"
    arch.mkdir(parents=True)
    for i in range(4):
        img = np.full((64, 64, 3), (i * 40) % 256, dtype=np.uint8)
        cv2.imwrite(str(arch / f"panel_{i:04d}.png"), img)
    os.environ["RWM_L0_DAEMON_ENABLED"] = "true"
    os.environ["RWM_DEVICE_ID_HEX"] = "ab" * 32
    os.environ.pop("RWM_CONTINUUM_DAEMON_ENABLED", None)  # default-ON
    dmn._issue_rwm_l0("lab", 99, arch)
    assert (arch / "rwm_manifest_chain.json").is_file()
    dmn._issue_session_continuum("lab", 99, arch)
    assert (arch / "session_continuum.json").is_file()
    cont = json.loads((arch / "session_continuum.json").read_text(encoding="utf-8"))
    assert cont["optical_rwm"] is True
    assert cont["verdict"] in (
        "OPTICAL_SESSION", "OPTICAL_IDENTITY", "PARTIAL", "STACK_WITHOUT_OPTICAL",
        "SYNCHRONIZED_CONTINUUM", "OPTICAL_PRESENCE",
    )


def test_cmd_status_no_session_returns_1(tmp_path, monkeypatch):
    monkeypatch.setattr(dmn, "_STATE", tmp_path / "nope.json")
    assert dmn.cmd_status(argparse.Namespace()) == 1
