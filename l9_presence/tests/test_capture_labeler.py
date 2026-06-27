"""Tests for the capture-session labeler core (start/stop/relabel/validate).

Manifest format must match what run_consistency_experiment.py --real consumes.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT))

import capture_session_labeler as lab  # noqa: E402
from l9_presence.adversarial.real_sessions import load_labels_from_json  # noqa: E402

_DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"


def _mf():
    return os.path.join(tempfile.mkdtemp(prefix="vapi_labeler_"), "sessions.json")


def test_start_stop_appends_entry():
    mf = _mf()
    lab.start_session(mf, _DEV, "HUMAN_INPUT_MACRO", now=1000.0)
    entry = lab.stop_session(mf, now=1120.0)
    assert entry["class_label"] == "HUMAN_INPUT_MACRO"
    assert entry["t_start"] == 1000.0 and entry["t_end"] == 1120.0
    assert entry["device_id"] == _DEV
    # marker cleared
    assert not os.path.exists(mf + ".open")


def test_double_start_refused():
    mf = _mf()
    lab.start_session(mf, _DEV, "BOT_FULL", now=1.0)
    try:
        lab.start_session(mf, _DEV, "BOT_FULL", now=2.0)
        assert False, "expected RuntimeError on double start"
    except RuntimeError:
        pass


def test_stop_without_start_refused():
    mf = _mf()
    try:
        lab.stop_session(mf)
        assert False, "expected RuntimeError on stop with no open session"
    except RuntimeError:
        pass


def test_pending_then_relabel():
    mf = _mf()
    lab.start_session(mf, _DEV, "PENDING", now=10.0)
    lab.stop_session(mf, now=200.0)
    # PENDING flagged by validate
    assert any("PENDING" in i for i in lab.validate(mf))
    lab.relabel(mf, 0, "PRO_SKILL")
    assert lab.validate(mf) == []  # now run-ready


def test_validate_catches_bad_duration():
    mf = _mf()
    lab.start_session(mf, _DEV, "HUMAN_CLEAN", now=500.0)
    lab.stop_session(mf, now=500.0)  # t_end == t_start
    assert any("t_end <= t_start" in i for i in lab.validate(mf))


def test_manifest_is_consumable_by_real_loader():
    """The labeler's output must parse as SessionLabels for the --real runner."""
    mf = _mf()
    lab.start_session(mf, _DEV, "HUMAN_INPUT_MACRO", now=1000.0)
    lab.stop_session(mf, now=1100.0)
    labels = load_labels_from_json(mf)
    assert len(labels) == 1
    assert labels[0].device_id == _DEV
    assert labels[0].class_label.value == "HUMAN_INPUT_MACRO"
